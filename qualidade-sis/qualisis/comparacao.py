"""Comparação entre envios: quanto foi resolvido desde a última análise.

Como a base é acumulativa, o mesmo registro reaparece em todos os envios. O que
interessa ao setor é a **resolutividade**: das inconsistências apontadas no
envio anterior, quantas foram efetivamente corrigidas até o envio atual,
quantas persistem e quantas surgiram.

Classificação de cada ocorrência:

    corrigida    -> existia no envio anterior, o registro continua na base e a
                    inconsistência desapareceu
    persistente  -> existia no envio anterior e continua existindo
    nova         -> não existia no envio anterior
    sem registro -> existia antes, mas o registro sumiu da base (expurgo,
                    exclusão ou mudança de chave) — exige verificação
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import datetime

from . import tipos as T


def _h(texto):
    return hashlib.blake2b(texto.encode("utf-8"), digest_size=8).hexdigest()


def _pct(num, den):
    if not den:
        return None
    return round(100.0 * num / den, 2)


class Historico:
    """Persistência das execuções de um sistema (pasta ``historico/<sigla>``)."""

    def __init__(self, pasta, sigla):
        self.pasta = os.path.join(pasta, sigla.lower())
        os.makedirs(self.pasta, exist_ok=True)
        self.arquivo_execucoes = os.path.join(self.pasta, "execucoes.json")

    # -- gravação -------------------------------------------------------- #
    def caminhos(self, carimbo):
        return (os.path.join(self.pasta, f"{carimbo}_ocorrencias.csv.gz"),
                os.path.join(self.pasta, f"{carimbo}_chaves.txt.gz"))

    def execucoes(self):
        if not os.path.exists(self.arquivo_execucoes):
            return []
        try:
            with open(self.arquivo_execucoes, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return []

    def ultima_execucao(self, ignorar_carimbo=None):
        execs = [e for e in self.execucoes() if e.get("carimbo") != ignorar_carimbo]
        if not execs:
            return None
        return sorted(execs, key=lambda e: e["carimbo"])[-1]

    def registrar_execucao(self, dados):
        execs = [e for e in self.execucoes() if e.get("carimbo") != dados.get("carimbo")]
        execs.append(dados)
        execs.sort(key=lambda e: e["carimbo"])
        with open(self.arquivo_execucoes, "w", encoding="utf-8") as fh:
            json.dump(execs, fh, ensure_ascii=False, indent=2)

    def limpar_antigas(self, manter=12):
        """Mantém apenas as N execuções mais recentes (arquivos de assinatura)."""
        execs = sorted(self.execucoes(), key=lambda e: e["carimbo"])
        for e in execs[:-manter] if len(execs) > manter else []:
            for caminho in self.caminhos(e["carimbo"]):
                if os.path.exists(caminho):
                    try:
                        os.remove(caminho)
                    except OSError:
                        pass


class GravadorAssinatura:
    """Grava, em fluxo, a assinatura das ocorrências e das chaves do envio atual."""

    def __init__(self, historico, carimbo):
        self.arq_ocor, self.arq_chaves = historico.caminhos(carimbo)
        self._fo = gzip.open(self.arq_ocor, "wt", encoding="utf-8", newline="")
        self._fc = gzip.open(self.arq_chaves, "wt", encoding="utf-8", newline="")
        self._fo.write("chave;campo;tipo;regra\n")

    def escrever(self, chave_hash, ocorrencias):
        self._fc.write(chave_hash + "\n")
        for oc in ocorrencias:
            self._fo.write(f"{chave_hash};{oc.campo};{oc.tipo};{oc.regra}\n")

    def fechar(self):
        self._fo.close()
        self._fc.close()


class Comparador:
    """Compara o envio atual com o envio anterior, ocorrência a ocorrência."""

    def __init__(self, historico, execucao_anterior):
        self.historico = historico
        self.anterior = execucao_anterior
        self.arq_ocor_ant, self.arq_chaves_ant = historico.caminhos(execucao_anterior["carimbo"])
        self.hashes_ant = set()
        self.chaves_ant = set()
        self.chaves_atuais = set()
        self.hashes_atuais = set()

        self.novas = Counter()
        self.persistentes = Counter()
        self.corrigidas = Counter()
        self.sem_registro = Counter()
        self.novas_campo = Counter()
        self.persistentes_campo = Counter()
        self.corrigidas_campo = Counter()
        self.tipo_do_campo = defaultdict(Counter)

        self.registros_novos = 0
        self.registros_mantidos = 0
        self.registros_ausentes = 0
        self.n_ocorrencias_atuais = 0
        self.disponivel = (os.path.exists(self.arq_ocor_ant)
                           and os.path.exists(self.arq_chaves_ant))

    # ------------------------------------------------------------------ #
    def carregar_anterior(self):
        if not self.disponivel:
            return False
        with gzip.open(self.arq_chaves_ant, "rt", encoding="utf-8") as fh:
            for linha in fh:
                linha = linha.strip()
                if linha:
                    self.chaves_ant.add(linha)
        with gzip.open(self.arq_ocor_ant, "rt", encoding="utf-8") as fh:
            next(fh, None)
            for linha in fh:
                partes = linha.rstrip("\n").split(";")
                if len(partes) < 4:
                    continue
                self.hashes_ant.add(_h("|".join(partes[:4])))
        return True

    # ------------------------------------------------------------------ #
    def observar(self, chave_hash, ocorrencias):
        """Chamado uma vez por registro durante a leitura do envio atual."""
        if not self.disponivel:
            return
        self.chaves_atuais.add(chave_hash)
        if chave_hash in self.chaves_ant:
            self.registros_mantidos += 1
        else:
            self.registros_novos += 1
        for oc in ocorrencias:
            self.n_ocorrencias_atuais += 1
            assinatura = _h(f"{chave_hash}|{oc.campo}|{oc.tipo}|{oc.regra}")
            self.hashes_atuais.add(assinatura)
            if assinatura in self.hashes_ant:
                self.persistentes[oc.tipo] += 1
                self.persistentes_campo[oc.campo] += 1
            else:
                self.novas[oc.tipo] += 1
                self.novas_campo[oc.campo] += 1
            self.tipo_do_campo[oc.campo][oc.tipo] += 1

    # ------------------------------------------------------------------ #
    def finalizar(self):
        """Reprocessa a assinatura anterior para achar o que foi corrigido."""
        if not self.disponivel:
            return self
        with gzip.open(self.arq_ocor_ant, "rt", encoding="utf-8") as fh:
            next(fh, None)
            for linha in fh:
                partes = linha.rstrip("\n").split(";")
                if len(partes) < 4:
                    continue
                chave, campo, tipo, _regra = partes[0], partes[1], partes[2], partes[3]
                assinatura = _h("|".join(partes[:4]))
                if assinatura in self.hashes_atuais:
                    continue  # persistente, já contabilizada
                if chave in self.chaves_atuais:
                    self.corrigidas[tipo] += 1
                    self.corrigidas_campo[campo] += 1
                else:
                    self.sem_registro[tipo] += 1
        self.registros_ausentes = len(self.chaves_ant - self.chaves_atuais)
        return self

    # ------------------------------------------------------------------ #
    @property
    def total_corrigidas(self):
        return sum(self.corrigidas.values())

    @property
    def total_persistentes(self):
        return sum(self.persistentes.values())

    @property
    def total_novas(self):
        return sum(self.novas.values())

    @property
    def total_sem_registro(self):
        return sum(self.sem_registro.values())

    @property
    def taxa_resolutividade(self):
        base = self.total_corrigidas + self.total_persistentes
        return _pct(self.total_corrigidas, base)

    def por_tipo(self):
        saida = []
        for codigo in T.ORDEM_TIPOS:
            corr = self.corrigidas.get(codigo, 0)
            pers = self.persistentes.get(codigo, 0)
            novas = self.novas.get(codigo, 0)
            anteriores = corr + pers + self.sem_registro.get(codigo, 0)
            if not (anteriores or novas):
                continue
            saida.append({
                "tipo": codigo,
                "anteriores": anteriores,
                "corrigidas": corr,
                "persistentes": pers,
                "novas": novas,
                "sem_registro": self.sem_registro.get(codigo, 0),
                "pct_resolvido": _pct(corr, corr + pers),
            })
        return saida

    def por_campo(self, top=20):
        campos = set(self.corrigidas_campo) | set(self.persistentes_campo) | set(self.novas_campo)
        linhas = []
        for campo in campos:
            corr = self.corrigidas_campo.get(campo, 0)
            pers = self.persistentes_campo.get(campo, 0)
            novas = self.novas_campo.get(campo, 0)
            linhas.append({
                "campo": campo,
                "anteriores": corr + pers,
                "corrigidas": corr,
                "persistentes": pers,
                "novas": novas,
                "pct_resolvido": _pct(corr, corr + pers),
            })
        linhas.sort(key=lambda l: -(l["persistentes"] + l["novas"]))
        return linhas[:top]

    def linhas_resumo(self):
        ant = self.anterior or {}
        data_ant = ant.get("data_processamento", ant.get("carimbo", ""))
        return [
            {"rotulo": "Envio anterior (referência)", "valor": data_ant,
             "leitura": f"arquivo: {ant.get('arquivo', '')}"},
            {"rotulo": "Registros no envio anterior", "valor": ant.get("registros", len(self.chaves_ant)),
             "leitura": "base acumulada anterior"},
            {"rotulo": "Registros no envio atual", "valor": len(self.chaves_atuais),
             "leitura": "base acumulada atual"},
            {"rotulo": "Registros novos", "valor": self.registros_novos,
             "leitura": "entraram na base desde o último envio"},
            {"rotulo": "Registros mantidos", "valor": self.registros_mantidos,
             "leitura": "já existiam no envio anterior"},
            {"rotulo": "Registros que sumiram da base", "valor": self.registros_ausentes,
             "leitura": "verificar expurgo, exclusão ou mudança de chave"},
            {"rotulo": "Ocorrências corrigidas", "valor": self.total_corrigidas,
             "leitura": "apontadas antes e resolvidas até agora"},
            {"rotulo": "Ocorrências persistentes", "valor": self.total_persistentes,
             "leitura": "apontadas antes e ainda não resolvidas"},
            {"rotulo": "Ocorrências novas", "valor": self.total_novas,
             "leitura": "surgiram neste envio (registros novos ou edição)"},
            {"rotulo": "Ocorrências sem registro correspondente", "valor": self.total_sem_registro,
             "leitura": "o registro saiu da base — conferir antes de considerar resolvido"},
            {"rotulo": "TAXA DE RESOLUTIVIDADE (%)", "valor": self.taxa_resolutividade,
             "leitura": "corrigidas ÷ (corrigidas + persistentes)"},
            {"rotulo": "Ocorrências novas por 100 registros novos",
             "valor": _pct(self.total_novas, max(self.registros_novos, 1)),
             "leitura": "pressão de entrada de novas inconsistências"},
        ]

    def evolucao_indicadores(self, indicadores_atuais):
        """Compara indicador a indicador com a execução anterior."""
        ant = (self.anterior or {}).get("indicadores", {})
        saida = []
        for nome, atual in indicadores_atuais.items():
            valor_ant = (ant.get(nome) or {}).get("valor") if isinstance(ant.get(nome), dict) \
                else ant.get(nome)
            delta = None
            if atual["valor"] is not None and valor_ant is not None:
                delta = round(atual["valor"] - valor_ant, 2)
            saida.append({
                "atributo": nome,
                "anterior": valor_ant,
                "atual": atual["valor"],
                "delta": delta,
                "classificacao": atual["classificacao"],
            })
        return saida


def carimbo_agora():
    return datetime.now().strftime("%Y%m%d_%H%M%S")
