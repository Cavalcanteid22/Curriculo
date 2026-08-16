"""Estrutura de tabela em memoria (substitui o pandas, sem dependencias)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

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
        linhas = []
        for bruta in matriz[indice + 1:]:
            registro = {}
            for i, nome in enumerate(cabecalho):
                registro[nome] = _valor_bruto(bruta[i]) if i < len(bruta) else ""
            if any(tx.limpar(valor) for valor in registro.values()):
                linhas.append(registro)
        return cls(cabecalho, linhas, origem=origem, aba=aba)

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

    Planilhas exportadas costumam trazer titulo, data de emissao e linhas em
    branco antes do cabecalho real; por isso a linha 0 nem sempre serve.
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
        numericos = sum(1 for c in preenchidas if tx.para_numero(c) is not None)
        nota -= numericos * 2.0
        nota -= sum(1 for c in preenchidas if len(c) > 60) * 2.0
        nota -= (len(preenchidas) - len({tx.chave_cabecalho(c) for c in preenchidas})) * 1.5
        nota -= indice * 0.4  # em caso de empate, prefere a linha de cima
        # ganha pontos se as linhas seguintes tiverem a mesma largura
        seguintes = matriz[indice + 1: indice + 6]
        if seguintes:
            iguais = sum(
                1 for s in seguintes
                if abs(len([c for c in s if tx.limpar(c)]) - len(preenchidas)) <= 1
            )
            nota += iguais * 1.5
        if nota > melhor_nota:
            melhor_indice, melhor_nota = indice, nota
    return melhor_indice


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
