"""Reconhecimento automatico de qual arquivo pertence a qual sistema.

Duas estrategias, nesta ordem:

1. Perfil configurado - usa padroes de nome de arquivo, nomes de aba e as
   colunas esperadas de cada sistema.
2. Modo automatico - agrupa as tabelas lidas por semelhanca de cabecalho
   (indice de Jaccard) e por semelhanca do nome do arquivo, formando dois
   grupos. Serve quando o usuario ainda nao criou um perfil.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import texto as tx
from .config import Perfil, SistemaConfig
from .tabela import Tabela

_PALAVRAS_IGNORADAS = {
    "relatorio", "relatorios", "export", "exportacao", "extracao", "dados",
    "planilha", "arquivo", "base", "lista", "listagem", "consulta", "geral",
    "final", "novo", "nova", "copia", "backup", "sistema", "mensal", "anual",
}
_MESES = {
    "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out",
    "nov", "dez", "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
}


@dataclass
class TabelaDetectada:
    tabela: Tabela
    sistema_id: str = ""
    confianca: float = 0.0
    justificativa: str = ""

    @property
    def arquivo(self) -> str:
        return os.path.basename(self.tabela.origem)


@dataclass
class ResultadoDeteccao:
    detectadas: List[TabelaDetectada] = field(default_factory=list)
    nomes_sistemas: Dict[str, str] = field(default_factory=dict)
    modo: str = "automatico"
    avisos: List[str] = field(default_factory=list)

    def por_sistema(self, identificador: str) -> List[TabelaDetectada]:
        return [d for d in self.detectadas if d.sistema_id == identificador]


# --------------------------------------------------------------------------
# Entrada principal
# --------------------------------------------------------------------------


def detectar(
    tabelas: List[Tabela],
    perfil: Perfil,
    atribuicoes_manuais: Optional[Dict[str, str]] = None,
) -> ResultadoDeteccao:
    """Classifica cada tabela como pertencente ao sistema A ou B.

    ``atribuicoes_manuais`` mapeia caminho do arquivo -> id do sistema e tem
    prioridade sobre qualquer deteccao (e o que a tela permite ajustar).
    """
    atribuicoes_manuais = atribuicoes_manuais or {}
    resultado = ResultadoDeteccao()
    tem_regras = any(
        s.padroes_arquivo or s.colunas_esperadas or s.mapeamento or s.padroes_aba
        for s in perfil.sistemas
    )
    if tem_regras:
        resultado.modo = "perfil"
        for tabela in tabelas:
            identificador, confianca, motivo = _classificar_por_perfil(tabela, perfil)
            resultado.detectadas.append(TabelaDetectada(tabela, identificador, confianca, motivo))
        indefinidas = [d for d in resultado.detectadas if not d.sistema_id or d.confianca < 0.30]
        if indefinidas:
            resultado.avisos.append(
                f"{len(indefinidas)} tabela(s) nao casaram com o perfil; "
                "foram classificadas por semelhanca de cabecalho."
            )
            _classificar_por_agrupamento(indefinidas, resultado.detectadas, perfil)
        resultado.nomes_sistemas = {s.id: s.nome for s in perfil.sistemas}
    else:
        resultado.modo = "automatico"
        detectadas = [TabelaDetectada(t) for t in tabelas]
        resultado.detectadas = detectadas
        _agrupar_em_dois(detectadas)
        resultado.nomes_sistemas = _nomear_sistemas(detectadas, perfil)

    for detectada in resultado.detectadas:
        forcado = atribuicoes_manuais.get(detectada.tabela.origem)
        if forcado and forcado in ("A", "B"):
            detectada.sistema_id = forcado
            detectada.confianca = 1.0
            detectada.justificativa = "Definido manualmente pelo usuario."

    for identificador in ("A", "B"):
        if not resultado.por_sistema(identificador):
            resultado.avisos.append(
                f"Nenhum arquivo foi identificado como '{resultado.nomes_sistemas.get(identificador, identificador)}'."
            )
    return resultado


# --------------------------------------------------------------------------
# Classificacao usando o perfil
# --------------------------------------------------------------------------


def _classificar_por_perfil(tabela: Tabela, perfil: Perfil) -> Tuple[str, float, str]:
    melhor_id, melhor_nota, melhor_motivo = "", 0.0, ""
    for sistema in perfil.sistemas:
        nota, motivos = _pontuar_sistema(tabela, sistema)
        if nota > melhor_nota:
            melhor_id, melhor_nota, melhor_motivo = sistema.id, nota, "; ".join(motivos)
    if not melhor_id:
        return "", 0.0, "Nenhuma regra do perfil correspondeu a este arquivo."
    return melhor_id, min(melhor_nota, 1.0), melhor_motivo


def _pontuar_sistema(tabela: Tabela, sistema: SistemaConfig) -> Tuple[float, List[str]]:
    nota = 0.0
    motivos: List[str] = []
    nome_arquivo = os.path.basename(tabela.origem)
    alvo_arquivo = tx.normalizar(nome_arquivo)
    for padrao in sistema.padroes_arquivo:
        if _casa(padrao, alvo_arquivo) or _casa(padrao, nome_arquivo):
            nota += 0.55
            motivos.append(f"nome do arquivo casa com '{padrao}'")
            break
    for padrao in sistema.padroes_aba:
        if _casa(padrao, tabela.aba):
            nota += 0.15
            motivos.append(f"aba casa com '{padrao}'")
            break
    cabecalhos = {tx.chave_cabecalho(c) for c in tabela.colunas}
    esperadas = {tx.chave_cabecalho(c) for c in sistema.colunas_esperadas}
    for aliases in sistema.mapeamento.values():
        esperadas.update(tx.chave_cabecalho(a) for a in aliases)
    if esperadas:
        cobertura = len(cabecalhos & esperadas) / len(esperadas)
        nota += 0.60 * cobertura
        if cobertura:
            motivos.append(
                f"{len(cabecalhos & esperadas)} de {len(esperadas)} colunas esperadas presentes"
            )
    return nota, motivos


def _casa(padrao: str, alvo: str) -> bool:
    alvo = alvo or ""
    try:
        if re.search(padrao, alvo, re.IGNORECASE):
            return True
    except re.error:
        pass
    return tx.normalizar(padrao) in tx.normalizar(alvo)


# --------------------------------------------------------------------------
# Classificacao automatica por semelhanca
# --------------------------------------------------------------------------


def _assinatura(detectada: TabelaDetectada) -> set:
    return {tx.chave_cabecalho(c) for c in detectada.tabela.colunas if tx.limpar(c)}


def _tokens_arquivo(detectada: TabelaDetectada) -> set:
    base = os.path.splitext(detectada.arquivo)[0]
    tokens = {t for t in tx.normalizar(base).split() if len(t) > 2}
    return {t for t in tokens if not t.isdigit() and t not in _MESES and t not in _PALAVRAS_IGNORADAS}


def _semelhanca(a: TabelaDetectada, b: TabelaDetectada) -> float:
    nota = 0.75 * tx.similaridade_conjuntos(_assinatura(a), _assinatura(b))
    nota += 0.25 * tx.similaridade_conjuntos(_tokens_arquivo(a), _tokens_arquivo(b))
    if a.tabela.origem == b.tabela.origem:
        nota = max(nota, 0.85)  # abas do mesmo arquivo pertencem ao mesmo sistema
    return nota


def _agrupar_em_dois(detectadas: List[TabelaDetectada]) -> None:
    if not detectadas:
        return
    if len(detectadas) == 1:
        detectadas[0].sistema_id = "A"
        detectadas[0].confianca = 0.4
        detectadas[0].justificativa = (
            "Unico arquivo enviado: atribuido ao primeiro sistema. "
            "Envie tambem os arquivos do outro sistema para a comparacao."
        )
        return
    grupos: List[List[int]] = [[i] for i in range(len(detectadas))]
    while len(grupos) > 2:
        melhor_par, melhor_nota = None, -1.0
        for i in range(len(grupos)):
            for j in range(i + 1, len(grupos)):
                notas = [
                    _semelhanca(detectadas[a], detectadas[b])
                    for a in grupos[i] for b in grupos[j]
                ]
                media = sum(notas) / len(notas)
                if media > melhor_nota:
                    melhor_par, melhor_nota = (i, j), media
        i, j = melhor_par
        grupos[i].extend(grupos[j])
        grupos.pop(j)
    grupos.sort(key=min)  # o grupo do primeiro arquivo enviado vira o sistema A
    for identificador, grupo in zip(("A", "B"), grupos):
        for indice in grupo:
            detectada = detectadas[indice]
            detectada.sistema_id = identificador
            internas = [
                _semelhanca(detectada, detectadas[outro]) for outro in grupo if outro != indice
            ]
            externas = [
                _semelhanca(detectada, outra)
                for k, outra in enumerate(detectadas) if k not in grupo
            ]
            media_interna = sum(internas) / len(internas) if internas else 1.0
            media_externa = sum(externas) / len(externas) if externas else 0.0
            detectada.confianca = round(max(0.0, min(1.0, 0.5 + (media_interna - media_externa) / 2)), 2)
            detectada.justificativa = (
                f"Agrupado por semelhanca de cabecalho e de nome "
                f"(semelhanca interna {media_interna:.0%}, externa {media_externa:.0%})."
            )


def _classificar_por_agrupamento(
    indefinidas: List[TabelaDetectada],
    todas: List[TabelaDetectada],
    perfil: Perfil,
) -> None:
    """Encaixa tabelas nao reconhecidas pelo perfil no sistema mais parecido."""
    referencias = [d for d in todas if d.sistema_id and d.confianca >= 0.30]
    for detectada in indefinidas:
        if not referencias:
            detectada.sistema_id = detectada.sistema_id or "A"
            detectada.confianca = 0.2
            continue
        melhor = max(referencias, key=lambda r: _semelhanca(detectada, r))
        nota = _semelhanca(detectada, melhor)
        detectada.sistema_id = melhor.sistema_id
        detectada.confianca = round(min(0.6, nota), 2)
        detectada.justificativa = (
            f"Nao casou com o perfil; classificado por semelhanca com '{melhor.arquivo}' "
            f"({nota:.0%})."
        )


def _nomear_sistemas(detectadas: List[TabelaDetectada], perfil: Perfil) -> Dict[str, str]:
    nomes: Dict[str, str] = {}
    for identificador in ("A", "B"):
        do_grupo = [d for d in detectadas if d.sistema_id == identificador]
        configurado = perfil.sistema(identificador)
        padrao = configurado.nome if configurado else f"Sistema {identificador}"
        # Nome escolhido pelo usuario tem prioridade sobre o deduzido dos arquivos.
        if padrao not in (f"Sistema {identificador}", "Sistema", ""):
            nomes[identificador] = padrao
            continue
        if not do_grupo:
            nomes[identificador] = padrao
            continue
        outros = [d for d in detectadas if d.sistema_id != identificador]
        tokens_outros = set()
        for detectada in outros:
            tokens_outros |= _tokens_arquivo(detectada)
        contagem: Dict[str, int] = {}
        for detectada in do_grupo:
            for token in _tokens_arquivo(detectada) - tokens_outros:
                contagem[token] = contagem.get(token, 0) + 1
        if contagem:
            melhor = max(contagem.items(), key=lambda item: (item[1], len(item[0])))
            if melhor[1] >= max(1, len(do_grupo) // 2):
                nomes[identificador] = melhor[0].upper()
                continue
        if padrao in (f"Sistema {identificador}", "Sistema"):
            nomes[identificador] = f"Sistema {identificador}"
        else:
            nomes[identificador] = padrao
    if nomes.get("A") == nomes.get("B"):
        nomes = {"A": "Sistema A", "B": "Sistema B"}
    return nomes
