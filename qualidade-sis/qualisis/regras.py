"""Motor de regras: transforma a configuração de um sistema em críticas.

Todas as inconsistências previstas na rotina do setor são produzidas aqui:
campo em branco, ignorado, código fora do domínio, data impossível, incoerência
entre campos, formato inválido, valor fora de faixa, fora do prazo e
duplicidade. Cada ocorrência sai identificada por **campo**, **tipo** e **regra**,
que é o que permite pintar a célula certa no Excel e agregar por atributo de
qualidade no relatório.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime

from . import tipos as T

RE_NAO_ALNUM = re.compile(r"[^A-Z0-9]+")
RE_CID10 = re.compile(r"^[A-Z]\d{2}(\.?\d)?$")
RE_SO_DIGITOS = re.compile(r"^\d+$")


# --------------------------------------------------------------------------- #
# Normalizações e validadores reutilizáveis
# --------------------------------------------------------------------------- #

def sem_acento(texto):
    txt = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in txt if not unicodedata.combining(c))


def normalizar_texto(valor):
    """'José  da Silva ' -> 'JOSEDASILVA' (para pareamento de duplicidade)."""
    return RE_NAO_ALNUM.sub("", sem_acento(valor).upper())


def normalizar_nome(valor):
    """'José  da Silva ' -> 'JOSE DA SILVA' (para exibição e blocagem)."""
    return re.sub(r"\s+", " ", sem_acento(valor).upper()).strip()


def so_digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))


def valido_cpf(valor):
    num = so_digitos(valor)
    if len(num) != 11 or num == num[0] * 11:
        return False
    for tam in (9, 10):
        soma = sum(int(num[i]) * (tam + 1 - i) for i in range(tam))
        dig = (soma * 10) % 11 % 10
        if dig != int(num[tam]):
            return False
    return True


def valido_cns(valor):
    """Cartão Nacional de Saúde (regra dos 11 — Portaria/Datasus)."""
    num = so_digitos(valor)
    if len(num) != 15:
        return False
    if num[0] in "12":
        soma = sum(int(num[i]) * (15 - i) for i in range(15))
        return soma % 11 == 0
    if num[0] in "789":
        soma = sum(int(num[i]) * (15 - i) for i in range(15))
        return soma % 11 == 0
    return False


def valido_cid10(valor):
    return bool(RE_CID10.match(str(valor).strip().upper()))


def valido_ibge(valor):
    num = so_digitos(valor)
    return len(num) in (6, 7)


def valido_cnes(valor):
    num = so_digitos(valor)
    return len(num) == 7


def valido_cep(valor):
    return len(so_digitos(valor)) == 8


VALIDADORES = {
    "cpf": valido_cpf,
    "cns": valido_cns,
    "cid10": valido_cid10,
    "ibge": valido_ibge,
    "cnes": valido_cnes,
    "cep": valido_cep,
}


def converter_data(valor, formatos):
    """Devolve ``date`` ou ``None`` se o valor não for uma data válida."""
    txt = str(valor).strip()
    if not txt:
        return None
    if len(txt) > 10 and " " in txt:
        txt_curto = txt.split(" ")[0]
    else:
        txt_curto = txt
    for fmt in formatos:
        try:
            return datetime.strptime(txt, fmt).date()
        except ValueError:
            pass
        if txt_curto is not txt:
            try:
                return datetime.strptime(txt_curto, fmt).date()
            except ValueError:
                pass
    return None


def converter_numero(valor):
    txt = str(valor).strip().replace(".", "").replace(",", ".")
    if not txt:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Ocorrência
# --------------------------------------------------------------------------- #

class Ocorrencia:
    """Uma inconsistência encontrada em um campo de um registro."""

    __slots__ = ("campo", "tipo", "regra", "descricao", "valor")

    def __init__(self, campo, tipo, regra, descricao, valor=""):
        self.campo = campo
        self.tipo = tipo
        self.regra = regra
        self.descricao = descricao
        self.valor = valor

    def __repr__(self):  # pragma: no cover
        return f"<Ocorrencia {self.campo} {self.tipo} {self.regra}>"


# --------------------------------------------------------------------------- #
# Motor
# --------------------------------------------------------------------------- #

class MotorRegras:
    def __init__(self, cfg, data_extracao=None, colunas=None):
        self.cfg = cfg
        self.data_extracao = data_extracao or date.today()
        self.colunas = set(colunas or [])
        self.campos_ativos = {
            c: s for c, s in cfg.campos.items() if not self.colunas or c in self.colunas
        }
        self.chaves_dup = [
            ch for ch in cfg.chaves_duplicidade
            if all((not self.colunas) or (c in self.colunas) for c in ch["campos"])
        ]
        self.regras_ativas = [r for r in cfg.regras_cruzadas if self._regra_aplicavel(r)]
        self.tempestividade = [
            t for t in cfg.tempestividade
            if (not self.colunas) or (
                t["data_inicial"].upper() in self.colunas and t["data_final"].upper() in self.colunas
            )
        ]
        self.data_minima = self._data_cfg("data_minima_plausivel", date(1900, 1, 1))
        self.data_maxima = self._data_cfg("data_maxima_plausivel", None) or self.data_extracao

    def _data_cfg(self, chave, padrao):
        valor = self.cfg.parametros.get(chave)
        if not valor:
            return padrao
        return converter_data(valor, ["%Y-%m-%d", "%d/%m/%Y"]) or padrao

    def _regra_aplicavel(self, regra):
        if not self.colunas:
            return True
        usados = set()
        for chave in ("campos", "entao_preenchido"):
            usados |= {c.upper() for c in regra.get(chave, [])}
        for chave in ("campo", "campo_a", "campo_b", "entao_campo"):
            if regra.get(chave):
                usados.add(regra[chave].upper())
        for cond in self._condicoes(regra.get("se")):
            if cond.get("campo"):
                usados.add(cond["campo"].upper())
        return usados.issubset(self.colunas)

    # -- chaves ---------------------------------------------------------- #
    def chave_registro(self, linha):
        """Identificador estável do registro, usado para comparar envios."""
        campos = self.cfg.chave_registro or list(self.campos_ativos)[:3]
        partes = [normalizar_texto(linha.get(c, "")) for c in campos]
        bruto = "|".join(partes)
        if not bruto.replace("|", ""):
            return ""
        return bruto[:120]

    def hashes_duplicidade(self, linha):
        """Hash de 8 bytes por chave de duplicidade configurada."""
        saida = []
        for idx, ch in enumerate(self.chaves_dup):
            partes = []
            faltou = False
            for campo in ch["campos"]:
                valor = linha.get(campo, "")
                spec = self.cfg.campos.get(campo, {})
                if spec.get("tipo") == "data":
                    dt = converter_data(valor, spec.get("formatos") or ["%d/%m/%Y", "%Y-%m-%d"])
                    valor = dt.isoformat() if dt else str(valor)
                norm = normalizar_texto(valor)
                if ch.get("prefixo_nome") and campo in ch.get("campos_nome", []):
                    # blocagem por iniciais: reduz falso negativo por erro de digitação
                    norm = norm[: int(ch["prefixo_nome"])]
                if not norm:
                    faltou = True
                    break
                partes.append(norm)
            if faltou or not partes:
                continue
            bruto = "\x1f".join(partes).encode("utf-8")
            saida.append((idx, int.from_bytes(hashlib.blake2b(bruto, digest_size=8).digest(), "big")))
        return saida

    # -- avaliação de um registro ---------------------------------------- #
    def avaliar(self, linha, duplicados=None):
        """Avalia um registro. Devolve ``(ocorrencias, contexto)``."""
        ocorrencias = []
        datas = {}
        numeros = {}

        for campo, spec in self.campos_ativos.items():
            valor = (linha.get(campo) or "").strip()
            vupper = valor.upper()
            tipo_campo = spec.get("tipo")

            if valor == "":
                if spec.get("obrigatorio") or spec.get("essencial"):
                    ocorrencias.append(Ocorrencia(
                        campo, T.EM_BRANCO, "CAMPO_OBRIGATORIO",
                        f"'{spec['rotulo']}' é campo essencial e está em branco.", valor))
                continue

            if vupper in spec["ignorado"]:
                ocorrencias.append(Ocorrencia(
                    campo, T.IGNORADO, "CODIGO_IGNORADO",
                    f"'{spec['rotulo']}' preenchido como ignorado/não informado ('{valor}').", valor))
                continue

            if tipo_campo == "data":
                dt = converter_data(valor, spec["formatos"])
                if dt is None:
                    ocorrencias.append(Ocorrencia(
                        campo, T.DATA_INVALIDA, "DATA_NAO_RECONHECIDA",
                        f"'{spec['rotulo']}' não é uma data válida ('{valor}').", valor))
                else:
                    datas[campo] = dt
                    limite_max = spec.get("_data_maxima") or self.data_maxima
                    limite_min = spec.get("_data_minima") or self.data_minima
                    if dt > limite_max:
                        ocorrencias.append(Ocorrencia(
                            campo, T.DATA_INVALIDA, "DATA_FUTURA",
                            f"'{spec['rotulo']}' posterior ao limite aceito "
                            f"({limite_max.strftime('%d/%m/%Y')}).", valor))
                    elif dt < limite_min:
                        ocorrencias.append(Ocorrencia(
                            campo, T.DATA_INVALIDA, "DATA_IMPLAUSIVEL",
                            f"'{spec['rotulo']}' anterior ao limite plausível "
                            f"({limite_min.strftime('%d/%m/%Y')}).", valor))
                continue

            if tipo_campo in ("inteiro", "decimal"):
                num = converter_numero(valor)
                if num is None:
                    ocorrencias.append(Ocorrencia(
                        campo, T.FORMATO_INVALIDO, "NUMERO_INVALIDO",
                        f"'{spec['rotulo']}' deveria ser numérico ('{valor}').", valor))
                    continue
                if tipo_campo == "inteiro" and num != int(num):
                    ocorrencias.append(Ocorrencia(
                        campo, T.FORMATO_INVALIDO, "NUMERO_NAO_INTEIRO",
                        f"'{spec['rotulo']}' deveria ser inteiro ('{valor}').", valor))
                numeros[campo] = num
                minimo, maximo = spec.get("min"), spec.get("max")
                if (minimo is not None and num < minimo) or (maximo is not None and num > maximo):
                    ocorrencias.append(Ocorrencia(
                        campo, T.FORA_DE_FAIXA, "FORA_DE_FAIXA",
                        f"'{spec['rotulo']}' = {valor} fora da faixa plausível "
                        f"[{minimo}, {maximo}].", valor))
                continue

            dominio = spec.get("dominio")
            if dominio and vupper not in dominio:
                ocorrencias.append(Ocorrencia(
                    campo, T.CODIGO_INVALIDO, "FORA_DO_DOMINIO",
                    f"'{spec['rotulo']}' = '{valor}' não consta no dicionário de dados "
                    f"(valores válidos: {', '.join(sorted(dominio)[:8])}...).", valor))
                continue

            validador = spec.get("validador")
            if validador and validador in VALIDADORES and not VALIDADORES[validador](valor):
                tipo_erro = T.CODIGO_INVALIDO if validador in ("cid10", "ibge", "cnes") \
                    else T.FORMATO_INVALIDO
                ocorrencias.append(Ocorrencia(
                    campo, tipo_erro, f"VALIDADOR_{validador.upper()}",
                    f"'{spec['rotulo']}' = '{valor}' não passa na validação de {validador.upper()}.",
                    valor))
                continue

            regex = spec.get("_regex")
            if regex and not regex.match(valor):
                ocorrencias.append(Ocorrencia(
                    campo, T.FORMATO_INVALIDO, "FORMATO",
                    f"'{spec['rotulo']}' = '{valor}' não obedece ao formato esperado "
                    f"({spec.get('formato_descricao', spec.get('regex'))}).", valor))
                continue

            tamanho = spec.get("tamanho")
            if tamanho and len(so_digitos(valor) if spec.get("so_digitos") else valor) != tamanho:
                ocorrencias.append(Ocorrencia(
                    campo, T.FORMATO_INVALIDO, "TAMANHO",
                    f"'{spec['rotulo']}' deveria ter {tamanho} caracteres.", valor))

        # -- regras cruzadas --------------------------------------------- #
        for regra in self.regras_ativas:
            ocorrencias.extend(self._aplicar_regra(regra, linha, datas, numeros))

        # -- tempestividade ---------------------------------------------- #
        atrasos = {}
        for tp in self.tempestividade:
            ini = datas.get(tp["data_inicial"].upper())
            fim = datas.get(tp["data_final"].upper())
            if not ini or not fim:
                continue
            dias = (fim - ini).days
            atrasos[tp["id"]] = dias
            prazo = tp.get("prazo_dias")
            if prazo is not None and dias > prazo:
                ocorrencias.append(Ocorrencia(
                    tp["data_final"].upper(), T.FORA_DO_PRAZO, tp["id"],
                    f"{tp['rotulo']}: {dias} dias (prazo de {prazo} dias).", str(dias)))
            if dias < 0:
                ocorrencias.append(Ocorrencia(
                    tp["data_final"].upper(), T.DATA_INVALIDA, tp["id"] + "_NEGATIVO",
                    f"{tp['rotulo']}: intervalo negativo ({dias} dias).", str(dias)))

        # -- duplicidade -------------------------------------------------- #
        if duplicados:
            for idx, h in self.hashes_duplicidade(linha):
                if h in duplicados[idx]:
                    ch = self.chaves_dup[idx]
                    for campo in ch["campos"]:
                        ocorrencias.append(Ocorrencia(
                            campo, T.DUPLICIDADE, ch.get("id", f"DUP{idx}"),
                            f"{ch.get('nome', 'Chave duplicada')}: "
                            f"registro repetido por {', '.join(ch['campos'])}.",
                            linha.get(campo, "")))

        contexto = {
            "datas": datas,
            "numeros": numeros,
            "atrasos": atrasos,
            "data_referencia": datas.get(self.cfg.data_referencia) if self.cfg.data_referencia else None,
        }
        return ocorrencias, contexto

    # -- tipos de regra cruzada ------------------------------------------ #
    @staticmethod
    def _condicoes(se):
        if not se:
            return []
        if isinstance(se, dict):
            return [se]
        return list(se)

    def _condicao_satisfeita(self, se, linha):
        conds = self._condicoes(se)
        if not conds:
            return True
        modo = "todas"
        if isinstance(se, dict) and se.get("modo"):
            modo = se["modo"]
        resultados = []
        for cond in conds:
            campo = cond.get("campo", "").upper()
            valor = (linha.get(campo) or "").strip().upper()
            ok = True
            if "valores" in cond:
                ok = valor in {str(v).upper() for v in cond["valores"]}
            if "valores_diferentes_de" in cond:
                ok = ok and valor not in {str(v).upper() for v in cond["valores_diferentes_de"]}
            if cond.get("preenchido") is True:
                ok = ok and valor != ""
            if cond.get("preenchido") is False:
                ok = ok and valor == ""
            resultados.append(ok)
        return all(resultados) if modo == "todas" else any(resultados)

    def _aplicar_regra(self, regra, linha, datas, numeros):
        saida = []
        tipo_regra = regra.get("tipo")
        rid = regra.get("id", tipo_regra)
        desc = regra.get("descricao", rid)
        tipo_inc = regra.get("tipo_inconsistencia")

        if tipo_regra == "ordem_datas":
            a, b = [c.upper() for c in regra["campos"][:2]]
            da, db = datas.get(a), datas.get(b)
            if da and db:
                delta = (db - da).days
                limite_min = regra.get("min_dias", 0)
                limite_max = regra.get("max_dias")
                fora = delta < limite_min or (limite_max is not None and delta > limite_max)
                if fora:
                    saida.append(Ocorrencia(
                        b, tipo_inc or T.DATA_INVALIDA, rid,
                        f"{desc} (diferença observada: {delta} dias).", linha.get(b, "")))

        elif tipo_regra == "condicional_obrigatorio":
            if self._condicao_satisfeita(regra.get("se"), linha):
                for campo in [c.upper() for c in regra.get("entao_preenchido", [])]:
                    valor = (linha.get(campo) or "").strip()
                    spec = self.cfg.campos.get(campo, {})
                    if valor == "" or valor.upper() in spec.get("ignorado", set()):
                        saida.append(Ocorrencia(
                            campo, tipo_inc or T.INCOERENCIA, rid, desc, valor))

        elif tipo_regra == "condicional_proibido":
            if self._condicao_satisfeita(regra.get("se"), linha):
                campo = regra["entao_campo"].upper()
                valor = (linha.get(campo) or "").strip().upper()
                proibidos = {str(v).upper() for v in regra.get("valores_proibidos", [])}
                if (valor in proibidos) or (regra.get("proibido_preenchido") and valor):
                    saida.append(Ocorrencia(
                        campo, tipo_inc or T.INCOERENCIA, rid, desc, linha.get(campo, "")))

        elif tipo_regra == "condicional_valores":
            if self._condicao_satisfeita(regra.get("se"), linha):
                campo = regra["entao_campo"].upper()
                valor = (linha.get(campo) or "").strip().upper()
                esperados = {str(v).upper() for v in regra.get("valores_esperados", [])}
                if valor and valor not in esperados:
                    saida.append(Ocorrencia(
                        campo, tipo_inc or T.INCOERENCIA, rid, desc, linha.get(campo, "")))

        elif tipo_regra == "faixa_condicional":
            if self._condicao_satisfeita(regra.get("se"), linha):
                campo = regra["campo"].upper()
                num = numeros.get(campo, converter_numero(linha.get(campo, "")))
                if num is not None:
                    minimo, maximo = regra.get("min"), regra.get("max")
                    if (minimo is not None and num < minimo) or \
                       (maximo is not None and num > maximo):
                        saida.append(Ocorrencia(
                            campo, tipo_inc or T.FORA_DE_FAIXA, rid,
                            f"{desc} (valor: {linha.get(campo, '')}).", linha.get(campo, "")))

        elif tipo_regra == "comparacao_numerica":
            a, b = regra["campo_a"].upper(), regra["campo_b"].upper()
            na = numeros.get(a, converter_numero(linha.get(a, "")))
            nb = numeros.get(b, converter_numero(linha.get(b, "")))
            if na is not None and nb is not None:
                op = regra.get("operador", "<=")
                ok = {"<=": na <= nb, "<": na < nb, ">=": na >= nb,
                      ">": na > nb, "==": na == nb, "!=": na != nb}.get(op, True)
                if not ok:
                    saida.append(Ocorrencia(
                        a, tipo_inc or T.INCOERENCIA, rid, desc, linha.get(a, "")))

        elif tipo_regra == "coerencia_valores":
            # combinações proibidas explícitas: [{"CAMPO_A": "1", "CAMPO_B": "2"}, ...]
            for combinacao in regra.get("combinacoes_proibidas", []):
                if all((linha.get(k.upper()) or "").strip().upper() == str(v).upper()
                       for k, v in combinacao.items()):
                    for campo in combinacao:
                        saida.append(Ocorrencia(
                            campo.upper(), tipo_inc or T.INCOERENCIA, rid, desc,
                            linha.get(campo.upper(), "")))

        return saida
