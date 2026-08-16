"""Consolidacao dos arquivos de um sistema em uma unica tabela canonica.

Faz o de-para de nomes de coluna, empilha os arquivos, deduz o tipo de cada
campo e identifica as colunas candidatas a chave.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import texto as tx
from .config import CampoConfig, Perfil
from .deteccao import TabelaDetectada
from .tabela import Tabela, concatenar

COL_ID = "ID_Registro"
COL_ARQUIVO = "Arquivo_Origem"
COL_ABA = "Aba_Origem"
COL_LINHA = "Linha_Origem"
COLUNAS_CONTROLE = (COL_ID, COL_ARQUIVO, COL_ABA, COL_LINHA)

# Padroes de nome que sugerem o tipo do campo
_PADROES_TIPO = (
    ("cpf_cnpj", r"cpf.?cnpj|cnpj.?cpf|documento|doc(umento)?$|ni$"),
    ("cpf", r"\bcpf\b|cpf"),
    ("cnpj", r"\bcnpj\b|cnpj"),
    ("email", r"e.?mail"),
    ("cep", r"\bcep\b"),
    ("telefone", r"telefone|celular|fone|contato"),
    ("data", r"\bdata\b|\bdt\b|nascimento|emissao|vencimento|admissao|cadastro|competencia|periodo"),
    ("numero", r"valor|preco|salario|quantidade|qtd|total|saldo|montante|percentual|aliquota"),
    ("codigo", r"codigo|matricula|protocolo|processo|identificador|\bid\b|registro|inscricao|contrato|empenho"),
)
_PADROES_CHAVE = re.compile(
    r"cpf|cnpj|matricula|codigo|protocolo|processo|identificador|^id$|inscricao|"
    r"contrato|empenho|chave|nis|pis|rg|documento|nota|numero"
)


@dataclass
class Consolidado:
    """Resultado da consolidacao de um sistema."""

    sistema_id: str
    nome: str
    tabela: Tabela = field(default_factory=Tabela)
    campos: List[CampoConfig] = field(default_factory=list)
    colunas_dados: List[str] = field(default_factory=list)
    arquivos: List[Dict[str, Any]] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)

    def campo(self, nome: str) -> Optional[CampoConfig]:
        for item in self.campos:
            if item.nome == nome:
                return item
        return None

    @property
    def chaves(self) -> List[str]:
        return [c.nome for c in self.campos if c.chave]


# --------------------------------------------------------------------------
# Consolidacao
# --------------------------------------------------------------------------


def consolidar(
    detectadas: List[TabelaDetectada],
    perfil: Perfil,
    sistema_id: str,
    nome_sistema: str,
) -> Consolidado:
    consolidado = Consolidado(sistema_id=sistema_id, nome=nome_sistema)
    sistema_cfg = perfil.sistema(sistema_id)
    preparadas: List[Tabela] = []
    for detectada in detectadas:
        tabela = detectada.tabela.copiar()
        de_para = _mapa_de_colunas(tabela.colunas, perfil, sistema_cfg)
        tabela.renomear(de_para)
        if sistema_cfg and sistema_cfg.ignorar_colunas:
            descartar = {tx.chave_cabecalho(c) for c in sistema_cfg.ignorar_colunas}
            tabela.colunas = [c for c in tabela.colunas if tx.chave_cabecalho(c) not in descartar]
        arquivo = os.path.basename(tabela.origem)
        for numero, linha in enumerate(tabela.linhas, start=2):
            linha[COL_ARQUIVO] = arquivo
            linha[COL_ABA] = tabela.aba
            linha[COL_LINHA] = numero
        tabela.colunas.extend([COL_ARQUIVO, COL_ABA, COL_LINHA])
        preparadas.append(tabela)
        consolidado.arquivos.append({
            "arquivo": arquivo,
            "caminho": tabela.origem,
            "aba": tabela.aba,
            "registros": len(tabela.linhas),
            "colunas": len(tabela.colunas) - 3,
            "confianca": detectada.confianca,
            "justificativa": detectada.justificativa,
        })
    if not preparadas:
        return consolidado

    unida = concatenar(preparadas, nome=nome_sistema)
    _fundir_colunas_equivalentes(unida, consolidado)
    colunas_dados = [c for c in unida.colunas if c not in COLUNAS_CONTROLE]
    colunas_dados = [c for c in colunas_dados if _coluna_tem_conteudo(unida, c)]
    unida.colunas = [COL_ID] + colunas_dados + [COL_ARQUIVO, COL_ABA, COL_LINHA]
    for numero, linha in enumerate(unida.linhas, start=1):
        linha[COL_ID] = f"{sistema_id}{numero:06d}"
        for coluna in unida.colunas:
            linha.setdefault(coluna, "")

    consolidado.tabela = unida
    consolidado.colunas_dados = colunas_dados
    consolidado.campos = _deduzir_campos(unida, colunas_dados, perfil)
    if len(consolidado.arquivos) > 1:
        consolidado.avisos.append(
            f"{len(consolidado.arquivos)} arquivos/abas empilhados em {len(unida.linhas)} registros."
        )
    return consolidado


def _coluna_tem_conteudo(tabela: Tabela, coluna: str) -> bool:
    return any(tx.limpar(linha.get(coluna)) for linha in tabela.linhas)


def _fundir_colunas_equivalentes(tabela: Tabela, consolidado: Consolidado) -> None:
    """Funde colunas que sao o mesmo campo escrito de formas diferentes.

    So funde quando as duas colunas nunca aparecem preenchidas na mesma linha
    (ou seja, vieram de arquivos diferentes do mesmo sistema) e os nomes sao
    reconhecidamente equivalentes - caso tipico do DBF, que corta o nome do
    campo em 10 caracteres, contra o relatorio que traz o nome por extenso.
    """
    colunas = [c for c in tabela.colunas if c not in COLUNAS_CONTROLE]
    if len(colunas) < 2:
        return
    preenchidas = {
        coluna: {i for i, linha in enumerate(tabela.linhas) if tx.limpar(linha.get(coluna))}
        for coluna in colunas
    }
    candidatos: List[Tuple[float, str, str]] = []
    for i, coluna_a in enumerate(colunas):
        for coluna_b in colunas[i + 1:]:
            if not preenchidas[coluna_a] or not preenchidas[coluna_b]:
                continue
            if preenchidas[coluna_a] & preenchidas[coluna_b]:
                continue
            nota = tx.similaridade_nomes(coluna_a, coluna_b)
            if nota >= 0.78:
                candidatos.append((nota, coluna_a, coluna_b))
    if not candidatos:
        return

    grupo_de: Dict[str, str] = {c: c for c in colunas}

    def raiz(nome: str) -> str:
        while grupo_de[nome] != nome:
            nome = grupo_de[nome]
        return nome

    for _nota, coluna_a, coluna_b in sorted(candidatos, key=lambda item: -item[0]):
        raiz_a, raiz_b = raiz(coluna_a), raiz(coluna_b)
        if raiz_a == raiz_b:
            continue
        grupo_de[raiz_b] = raiz_a

    grupos: Dict[str, List[str]] = {}
    for coluna in colunas:
        grupos.setdefault(raiz(coluna), []).append(coluna)
    for membros in grupos.values():
        if len(membros) < 2:
            continue
        principal = max(membros, key=lambda c: (len(c.split()), len(c)))
        for linha in tabela.linhas:
            valor = ""
            for membro in membros:
                bruto = tx.limpar(linha.get(membro))
                if bruto:
                    valor = bruto
                    break
            for membro in membros:
                linha.pop(membro, None)
            linha[principal] = valor
        posicao = min(tabela.colunas.index(m) for m in membros)
        tabela.colunas = [c for c in tabela.colunas if c not in membros]
        tabela.colunas.insert(posicao, principal)
        consolidado.avisos.append(
            "Colunas tratadas como o mesmo campo: "
            + ", ".join(f"'{m}'" for m in membros)
            + f" -> '{principal}'."
        )


def _mapa_de_colunas(colunas: List[str], perfil: Perfil, sistema_cfg) -> Dict[str, str]:
    """Traduz os nomes de coluna do arquivo para os nomes canonicos do perfil."""
    de_para: Dict[str, str] = {}
    aliases: Dict[str, str] = {}
    if sistema_cfg:
        for canonico, lista in sistema_cfg.mapeamento.items():
            for alias in lista:
                aliases[tx.chave_cabecalho(alias)] = canonico
            aliases.setdefault(tx.chave_cabecalho(canonico), canonico)
    for campo in perfil.campos:
        aliases.setdefault(tx.chave_cabecalho(campo.nome), campo.nome)
    for coluna in colunas:
        canonico = aliases.get(tx.chave_cabecalho(coluna))
        if canonico and canonico != coluna:
            de_para[coluna] = canonico
    return de_para


# --------------------------------------------------------------------------
# Deducao de tipo e de chaves
# --------------------------------------------------------------------------


def _deduzir_campos(tabela: Tabela, colunas: List[str], perfil: Perfil) -> List[CampoConfig]:
    campos: List[CampoConfig] = []
    for coluna in colunas:
        valores = [tx.limpar(v) for v in tabela.coluna(coluna)]
        preenchidos = [v for v in valores if v]
        configurado = perfil.campo(coluna)
        if configurado:
            campo = CampoConfig(**{**configurado.__dict__})
            if campo.tipo == "texto":
                campo.tipo = inferir_tipo(coluna, preenchidos)
        else:
            campo = CampoConfig(nome=coluna, tipo=inferir_tipo(coluna, preenchidos))
            campo.chave = _parece_chave(coluna, valores, preenchidos)
            campo.unico = campo.chave
            if campo.tipo == "categoria":
                campo.dominio = sorted({v for v in preenchidos})[:perfil.qualidade.limite_categorias]
        campos.append(campo)
    if not any(c.chave for c in campos):
        candidato = _melhor_candidato_chave(tabela, campos)
        if candidato:
            candidato.chave = True
            candidato.unico = True
    return campos


def inferir_tipo(nome_coluna: str, valores: List[str]) -> str:
    """Deduz o tipo pelo nome da coluna e, principalmente, pelo conteudo."""
    amostra = [v for v in valores if v][:400]
    if not amostra:
        return "texto"
    total = len(amostra)

    def proporcao(funcao) -> float:
        return sum(1 for v in amostra if funcao(v)) / total

    if proporcao(lambda v: len(tx.so_digitos(v)) == 11 and tx.cpf_valido(v)) > 0.80:
        return "cpf"
    if proporcao(lambda v: len(tx.so_digitos(v)) == 14 and tx.cnpj_valido(v)) > 0.80:
        return "cnpj"
    if proporcao(tx.email_valido) > 0.80:
        return "email"
    if proporcao(lambda v: tx.para_data(v) is not None) > 0.80:
        return "data"
    if proporcao(lambda v: tx.para_numero(v) is not None) > 0.85:
        nome = tx.normalizar(nome_coluna)
        if re.search(r"cep", nome) and proporcao(lambda v: len(tx.so_digitos(v)) == 8) > 0.7:
            return "cep"
        return "numero"
    distintos = len({tx.normalizar(v) for v in amostra})
    if distintos <= max(2, min(25, total // 8)) and total >= 8:
        return "categoria"
    nome = tx.normalizar(nome_coluna)
    for tipo, padrao in _PADROES_TIPO:
        if re.search(padrao, nome):
            if tipo in ("cpf", "cnpj", "cpf_cnpj") and proporcao(lambda v: tx.so_digitos(v)) < 0.5:
                continue
            return tipo
    return "texto"


def _parece_chave(coluna: str, valores: List[str], preenchidos: List[str]) -> bool:
    if not preenchidos or len(valores) < 3:
        return False
    completude = len(preenchidos) / len(valores)
    unicidade = len({tx.normalizar(v) for v in preenchidos}) / len(preenchidos)
    nome = tx.normalizar(coluna)
    parece_pelo_nome = bool(_PADROES_CHAVE.search(nome))
    return unicidade >= 0.98 and completude >= 0.95 and (parece_pelo_nome or unicidade == 1.0)


def _melhor_candidato_chave(tabela: Tabela, campos: List[CampoConfig]) -> Optional[CampoConfig]:
    melhor, melhor_nota = None, 0.0
    for campo in campos:
        valores = [tx.limpar(v) for v in tabela.coluna(campo.nome)]
        preenchidos = [v for v in valores if v]
        if not preenchidos:
            continue
        completude = len(preenchidos) / len(valores)
        unicidade = len({tx.normalizar(v) for v in preenchidos}) / len(preenchidos)
        nota = unicidade * 0.6 + completude * 0.4
        if _PADROES_CHAVE.search(tx.normalizar(campo.nome)):
            nota += 0.25
        if campo.tipo in ("cpf", "cnpj", "cpf_cnpj", "codigo"):
            nota += 0.15
        if nota > melhor_nota and unicidade >= 0.85:
            melhor, melhor_nota = campo, nota
    return melhor


# --------------------------------------------------------------------------
# Correspondencia de campos entre os dois sistemas
# --------------------------------------------------------------------------


@dataclass
class ParDeCampos:
    campo_a: str
    campo_b: str
    tipo: str
    nota: float
    motivo: str


def mapear_campos_entre_sistemas(
    consolidado_a: Consolidado,
    consolidado_b: Consolidado,
    perfil: Perfil,
) -> List[ParDeCampos]:
    """Descobre quais colunas de A correspondem a quais colunas de B."""
    pares: List[ParDeCampos] = []
    usadas_b = set()
    valores_a = {c: _amostra_normalizada(consolidado_a, c) for c in consolidado_a.colunas_dados}
    valores_b = {c: _amostra_normalizada(consolidado_b, c) for c in consolidado_b.colunas_dados}

    candidatos: List[Tuple[float, str, str, str]] = []
    for coluna_a in consolidado_a.colunas_dados:
        for coluna_b in consolidado_b.colunas_dados:
            nota, motivo = _pontuar_par(
                coluna_a, coluna_b, consolidado_a, consolidado_b, valores_a, valores_b
            )
            if nota > 0:
                candidatos.append((nota, coluna_a, coluna_b, motivo))
    candidatos.sort(key=lambda item: -item[0])
    usadas_a = set()
    for nota, coluna_a, coluna_b, motivo in candidatos:
        if coluna_a in usadas_a or coluna_b in usadas_b or nota < 0.55:
            continue
        usadas_a.add(coluna_a)
        usadas_b.add(coluna_b)
        campo = consolidado_a.campo(coluna_a)
        pares.append(ParDeCampos(
            campo_a=coluna_a,
            campo_b=coluna_b,
            tipo=campo.tipo if campo else "texto",
            nota=round(nota, 3),
            motivo=motivo,
        ))
    return pares


def _amostra_normalizada(consolidado: Consolidado, coluna: str) -> set:
    valores = set()
    for linha in consolidado.tabela.linhas[:800]:
        valor = tx.normalizar(linha.get(coluna))
        if valor:
            valores.add(valor)
    return valores


def _pontuar_par(
    coluna_a: str,
    coluna_b: str,
    consolidado_a: Consolidado,
    consolidado_b: Consolidado,
    valores_a: Dict[str, set],
    valores_b: Dict[str, set],
) -> Tuple[float, str]:
    chave_a, chave_b = tx.chave_cabecalho(coluna_a), tx.chave_cabecalho(coluna_b)
    if chave_a == chave_b:
        return 1.0, "mesmo nome de coluna"
    campo_a = consolidado_a.campo(coluna_a)
    campo_b = consolidado_b.campo(coluna_b)
    tipo_a = campo_a.tipo if campo_a else "texto"
    tipo_b = campo_b.tipo if campo_b else "texto"
    nota_nome = tx.similaridade_nomes(coluna_a, coluna_b)
    sobreposicao = tx.similaridade_conjuntos(valores_a.get(coluna_a, set()), valores_b.get(coluna_b, set()))
    nota = 0.55 * nota_nome + 0.45 * sobreposicao
    if tipo_a == tipo_b and tipo_a != "texto":
        nota += 0.10
    elif tipo_a != tipo_b and "texto" not in (tipo_a, tipo_b):
        nota -= 0.20
    motivos = []
    if nota_nome >= 0.80:
        motivos.append(f"nomes parecidos ({nota_nome:.0%})")
    if sobreposicao >= 0.30:
        motivos.append(f"valores coincidentes ({sobreposicao:.0%})")
    if tipo_a == tipo_b and tipo_a != "texto":
        motivos.append(f"mesmo tipo ({tipo_a})")
    return min(nota, 0.99), "; ".join(motivos) or "semelhanca geral"
