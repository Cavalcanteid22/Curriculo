"""Estrutura de tabela em memoria (substitui o pandas, sem dependencias)."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import texto as tx


class Tabela:
    """Tabela simples: lista ordenada de colunas + lista de registros (dict)."""

    def __init__(
        self,
        colunas: Optional[Iterable[str]] = None,
        linhas: Optional[List[Dict[str, Any]]] = None,
        origem: str = "",
        aba: str = "",
    ) -> None:
        self.colunas: List[str] = list(colunas or [])
        self.linhas: List[Dict[str, Any]] = list(linhas or [])
        self.origem = origem  # caminho do arquivo de onde veio
        self.aba = aba        # aba/tabela dentro do arquivo

    # -- construcao --------------------------------------------------------

    @classmethod
    def de_matriz(cls, matriz: List[List[Any]], origem: str = "", aba: str = "") -> "Tabela":
        """Cria a tabela a partir de uma matriz crua, achando a linha de cabecalho."""
        matriz = [linha for linha in matriz if any(tx.limpar(c) for c in linha)]
        if not matriz:
            return cls(origem=origem, aba=aba)
        indice = _achar_cabecalho(matriz)
        cabecalho = _nomes_unicos(matriz[indice])
        chaves_cabecalho = {tx.chave_cabecalho(c) for c in cabecalho if tx.limpar(c)}

        # Identificacao que vem antes da tabela ("Nome do usuario: FULANO")
        # vale para todos os registros do relatorio.
        contexto_fixo = _contexto_de_rotulos(matriz[:indice])
        contexto_corrente: Dict[str, str] = {}
        colunas_contexto: List[str] = list(contexto_fixo)
        linhas = []
        for bruta in matriz[indice + 1:]:
            celulas = [tx.limpar(c) for c in bruta]
            if _repete_cabecalho(celulas, chaves_cabecalho):
                continue  # cabecalho repetido a cada quebra de pagina
            if _linha_de_contexto(celulas, len(cabecalho)):
                novos = _contexto_de_rotulos([bruta])
                if novos:
                    contexto_corrente = {**contexto_corrente, **novos}
                    for nome in novos:
                        if nome not in colunas_contexto:
                            colunas_contexto.append(nome)
                    continue
            registro = {}
            for i, nome in enumerate(cabecalho):
                registro[nome] = _valor_bruto(bruta[i]) if i < len(bruta) else ""
            if not any(tx.limpar(valor) for valor in registro.values()):
                continue
            registro.update(contexto_fixo)
            registro.update(contexto_corrente)
            linhas.append(registro)

        colunas = cabecalho + [c for c in colunas_contexto if c not in cabecalho]
        for linha in linhas:
            for coluna in colunas:
                linha.setdefault(coluna, "")
        return cls(colunas, linhas, origem=origem, aba=aba)

    # -- acesso ------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.linhas)

    def __iter__(self):
        return iter(self.linhas)

    def coluna(self, nome: str) -> List[Any]:
        return [linha.get(nome, "") for linha in self.linhas]

    def vazia(self) -> bool:
        return not self.linhas or not self.colunas

    def acrescentar_coluna(self, nome: str, valor_padrao: Any = "") -> None:
        if nome not in self.colunas:
            self.colunas.append(nome)
        for linha in self.linhas:
            linha.setdefault(nome, valor_padrao)

    def renomear(self, de_para: Dict[str, str]) -> None:
        self.colunas = [de_para.get(c, c) for c in self.colunas]
        for linha in self.linhas:
            for antigo, novo in de_para.items():
                if antigo in linha and antigo != novo:
                    linha[novo] = linha.pop(antigo)

    def matriz(self, colunas: Optional[List[str]] = None) -> List[List[Any]]:
        colunas = colunas or self.colunas
        return [[linha.get(c, "") for c in colunas] for linha in self.linhas]

    def copiar(self) -> "Tabela":
        return Tabela(
            list(self.colunas),
            [dict(linha) for linha in self.linhas],
            origem=self.origem,
            aba=self.aba,
        )

    def __repr__(self) -> str:  # pragma: no cover - apoio a depuracao
        return f"<Tabela {len(self.linhas)}x{len(self.colunas)} {self.origem}:{self.aba}>"


def concatenar(tabelas: List[Tabela], nome: str = "") -> Tabela:
    """Empilha varias tabelas alinhando colunas equivalentes pelo nome canonico."""
    resultado = Tabela(origem=nome)
    mapa_canonico: Dict[str, str] = {}
    for tabela in tabelas:
        for coluna in tabela.colunas:
            canonica = tx.chave_cabecalho(coluna)
            if canonica not in mapa_canonico:
                mapa_canonico[canonica] = coluna
                resultado.colunas.append(coluna)
    for tabela in tabelas:
        for linha in tabela.linhas:
            registro = {coluna: "" for coluna in resultado.colunas}
            for coluna, valor in linha.items():
                destino = mapa_canonico.get(tx.chave_cabecalho(coluna), coluna)
                if destino not in registro:
                    resultado.colunas.append(destino)
                    for antiga in resultado.linhas:
                        antiga.setdefault(destino, "")
                    registro[destino] = ""
                registro[destino] = valor
            resultado.linhas.append(registro)
    return resultado


# --------------------------------------------------------------------------
# Apoio interno
# --------------------------------------------------------------------------


_LIMITE_CONTEXTO = 12
_TAMANHO_ROTULO = 40


def _valores_distintos_em_ordem(celulas: List[str]) -> List[str]:
    """Remove repeticoes vizinhas geradas por celulas mescladas (colspan)."""
    distintos: List[str] = []
    for celula in celulas:
        if celula and (not distintos or distintos[-1] != celula):
            distintos.append(celula)
    return distintos


def _repete_cabecalho(celulas: List[str], chaves_cabecalho: set) -> bool:
    preenchidas = {tx.chave_cabecalho(c) for c in celulas if c}
    if len(preenchidas) < 2 or not chaves_cabecalho:
        return False
    return preenchidas <= chaves_cabecalho and len(preenchidas) >= len(chaves_cabecalho) * 0.6


def _linha_de_contexto(celulas: List[str], largura: int) -> bool:
    """Linha de agrupamento, como 'DISPENSADOR: ... | DATA DISPENSA: ...'."""
    preenchidas = [c for c in celulas if c]
    if len(preenchidas) < 2 or largura < 2:
        return False
    distintos = _valores_distintos_em_ordem(celulas)
    if len(distintos) > 4:
        return False
    tem_rotulo = any(":" in valor for valor in distintos)
    mesclada = len(preenchidas) >= max(2, largura * 0.6) and len(distintos) < largura * 0.6
    return tem_rotulo and mesclada


_ROTULO = r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9º°./ _-]{1,38}?"
_RE_ROTULO_VALOR = re.compile(rf"\s*({_ROTULO})\s*:\s*(.*?)(?=\s*{_ROTULO}\s*:|$)")
_TAMANHO_TRECHO = 120


def _pares_do_trecho(texto: str) -> List[Tuple[str, str]]:
    """Le 'Rotulo: valor' em sequencia, sem deixar o rotulo comecar no meio.

    Uma mesma celula pode trazer varios pares, como
    'DATA DISPENSA: 11/08/2026 TEMPO DE TRATAMENTO: 180 Dias'.
    """
    pares: List[Tuple[str, str]] = []
    posicao = 0
    while posicao < len(texto):
        casamento = _RE_ROTULO_VALOR.match(texto, posicao)
        if not casamento or casamento.end() == posicao:
            proximo = texto.find(":", posicao)
            if proximo < 0:
                break
            posicao = proximo + 1
            continue
        pares.append((casamento.group(1), casamento.group(2)))
        posicao = casamento.end()
    return pares


def _contexto_de_rotulos(linhas: List[List[Any]]) -> Dict[str, str]:
    """Extrai a identificacao que acompanha a tabela (cabecalho do relatorio)."""
    contexto: Dict[str, str] = {}
    for bruta in linhas:
        trechos: List[str] = []
        for celula in bruta:
            for pedaco in str(celula or "").split("\n"):
                pedaco = tx.limpar(pedaco)
                if pedaco and len(pedaco) <= _TAMANHO_TRECHO:
                    trechos.append(pedaco)
        for trecho in _juntar_rotulos_soltos(_valores_distintos_em_ordem(trechos)):
            for rotulo, valor in _pares_do_trecho(trecho):
                rotulo, valor = rotulo.strip(" .-_"), valor.strip()
                if not rotulo or not valor or len(rotulo) > _TAMANHO_ROTULO:
                    continue
                if rotulo[-1].isdigit():  # evita quebrar horarios como '11:30'
                    continue
                if len(contexto) >= _LIMITE_CONTEXTO:
                    return contexto
                contexto.setdefault(rotulo, valor)
    return contexto


def _juntar_rotulos_soltos(trechos: List[str]) -> List[str]:
    """Junta 'Rotulo:' que ficou em uma celula com o valor da celula seguinte."""
    juntos: List[str] = []
    for trecho in trechos:
        if juntos and juntos[-1].endswith(":"):
            juntos[-1] = f"{juntos[-1]} {trecho}"
        else:
            juntos.append(trecho)
    return juntos


def _valor_bruto(valor: Any) -> Any:
    """Mantem o valor como veio do arquivo.

    Espacos duplicados e sobras de digitacao sao informacao para a analise de
    padronizacao, entao nao podem ser removidos na leitura; numeros e datas
    tambem preservam o tipo original. A limpeza acontece em cada uso.
    """
    if valor is None:
        return ""
    if isinstance(valor, str):
        return valor.replace("\xa0", " ").replace("\r", " ").replace("\n", " ")
    return valor


def _achar_cabecalho(matriz: List[List[Any]], limite: int = 15) -> int:
    """Escolhe a linha que melhor se parece com um cabecalho de tabela.

    Relatorios de sistema costumam trazer brasao, titulo, unidade e data de
    emissao antes do cabecalho real; por isso a linha 0 quase nunca serve.
    O sinal mais confiavel e a mudanca de tipo: o cabecalho e texto onde as
    linhas de baixo trazem datas, numeros ou documentos.
    """
    melhor_indice, melhor_nota = 0, float("-inf")
    largura_max = max((len(l) for l in matriz[:limite]), default=0)
    for indice, linha in enumerate(matriz[:limite]):
        celulas = [tx.limpar(c) for c in linha]
        preenchidas = [c for c in celulas if c]
        if len(preenchidas) < 2:
            continue
        nota = len(preenchidas) / max(largura_max, 1) * 10
        # cabecalhos sao textos curtos, sem numeros puros e sem repeticao
        nota -= sum(1 for c in preenchidas if _tipo_celula(c) != "texto") * 2.0
        nota -= sum(1 for c in preenchidas if len(c) > 60) * 2.0
        nota -= (len(preenchidas) - len({tx.chave_cabecalho(c) for c in preenchidas})) * 1.5
        nota -= indice * 0.4  # em caso de empate, prefere a linha de cima
        seguintes = matriz[indice + 1: indice + 8]
        if seguintes:
            iguais = sum(1 for s in seguintes if abs(len(s) - len(celulas)) <= 1)
            nota += iguais * 1.0
            nota += 8.0 * _mudanca_de_tipo(celulas, seguintes)
        if nota > melhor_nota:
            melhor_indice, melhor_nota = indice, nota
    return melhor_indice


def _tipo_celula(valor: str) -> str:
    if not valor:
        return "vazio"
    if tx.para_data(valor) is not None:
        return "data"
    if tx.para_numero(valor) is not None:
        return "numero"
    if len(tx.so_digitos(valor)) in (11, 14) and not any(c.isalpha() for c in valor):
        return "documento"
    return "texto"


def _mudanca_de_tipo(candidata: List[str], seguintes: List[List[Any]]) -> float:
    """Fracao de colunas em que a linha e texto e as de baixo nao sao."""
    if not candidata:
        return 0.0
    divergentes = 0
    consideradas = 0
    for coluna, valor in enumerate(candidata):
        if _tipo_celula(valor) != "texto":
            continue
        abaixo = [
            _tipo_celula(tx.limpar(s[coluna]))
            for s in seguintes if coluna < len(s) and tx.limpar(s[coluna])
        ]
        if not abaixo:
            continue
        consideradas += 1
        nao_texto = sum(1 for t in abaixo if t != "texto")
        if nao_texto >= max(1, len(abaixo) * 0.6):
            divergentes += 1
    if not consideradas:
        return 0.0
    return divergentes / len(candidata)


def _nomes_unicos(linha: List[Any]) -> List[str]:
    nomes, vistos = [], {}
    for i, celula in enumerate(linha):
        nome = tx.limpar(celula) or f"Coluna_{i + 1}"
        base = nome
        contador = vistos.get(tx.chave_cabecalho(base), 0)
        if contador:
            nome = f"{base}_{contador + 1}"
        vistos[tx.chave_cabecalho(base)] = contador + 1
        nomes.append(nome)
    return nomes
