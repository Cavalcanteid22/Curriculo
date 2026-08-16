"""Perfis de configuracao do consolidador.

Um perfil descreve os dois sistemas, como reconhecer os arquivos de cada um,
como os campos se chamam em cada sistema e quais regras de qualidade e de
pareamento aplicar. O perfil e opcional: sem ele o aplicativo trabalha em
modo automatico e ainda assim produz todos os resultados.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

TIPOS_CONHECIDOS = (
    "texto", "numero", "data", "cpf", "cnpj", "cpf_cnpj", "email",
    "cep", "telefone", "categoria", "codigo", "booleano",
)


@dataclass
class CampoConfig:
    """Regras de um campo canonico (nome usado nas duas planilhas)."""

    nome: str
    tipo: str = "texto"
    obrigatorio: bool = False
    chave: bool = False
    unico: bool = False
    dominio: List[str] = field(default_factory=list)
    minimo: Optional[float] = None
    maximo: Optional[float] = None
    tamanho_minimo: Optional[int] = None
    tamanho_maximo: Optional[int] = None
    descricao: str = ""


@dataclass
class SistemaConfig:
    """Como reconhecer e interpretar os arquivos de um dos sistemas."""

    id: str
    nome: str
    padroes_arquivo: List[str] = field(default_factory=list)
    padroes_aba: List[str] = field(default_factory=list)
    colunas_esperadas: List[str] = field(default_factory=list)
    # campo canonico -> nomes que aparecem nos arquivos deste sistema
    mapeamento: Dict[str, List[str]] = field(default_factory=dict)
    ignorar_colunas: List[str] = field(default_factory=list)


@dataclass
class PareamentoConfig:
    chaves_primarias: List[str] = field(default_factory=list)
    chaves_alternativas: List[List[str]] = field(default_factory=list)
    campos_similaridade: List[str] = field(default_factory=list)
    campos_comparacao: List[str] = field(default_factory=list)
    limiar_provavel: float = 0.90
    limiar_duvidoso: float = 0.78
    bloqueio: str = "auto"  # "auto" | nome de campo usado para reduzir comparacoes


@dataclass
class RegraConsistencia:
    """Regra entre campos, ex.: data final nao pode ser menor que a inicial."""

    nome: str
    campo_a: str
    operador: str  # >=, <=, >, <, ==, !=, obrigatorio_se_preenchido
    campo_b: str = ""
    valor: str = ""
    descricao: str = ""


@dataclass
class QualidadeConfig:
    regras_consistencia: List[RegraConsistencia] = field(default_factory=list)
    data_minima: str = "1900-01-01"
    data_maxima: str = ""  # vazio = hoje
    detectar_outliers: bool = True
    limite_categorias: int = 30


@dataclass
class Perfil:
    nome: str = "Perfil automatico"
    sistemas: List[SistemaConfig] = field(default_factory=list)
    campos: List[CampoConfig] = field(default_factory=list)
    pareamento: PareamentoConfig = field(default_factory=PareamentoConfig)
    qualidade: QualidadeConfig = field(default_factory=QualidadeConfig)
    observacoes: str = ""

    # -- acesso ------------------------------------------------------------

    def campo(self, nome: str) -> Optional[CampoConfig]:
        for item in self.campos:
            if item.nome == nome:
                return item
        return None

    def sistema(self, identificador: str) -> Optional[SistemaConfig]:
        for item in self.sistemas:
            if item.id == identificador:
                return item
        return None

    # -- persistencia ------------------------------------------------------

    def para_dicionario(self) -> Dict[str, Any]:
        return {
            "nome": self.nome,
            "sistemas": [asdict(s) for s in self.sistemas],
            "campos": [asdict(c) for c in self.campos],
            "pareamento": asdict(self.pareamento),
            "qualidade": {
                "regras_consistencia": [asdict(r) for r in self.qualidade.regras_consistencia],
                "data_minima": self.qualidade.data_minima,
                "data_maxima": self.qualidade.data_maxima,
                "detectar_outliers": self.qualidade.detectar_outliers,
                "limite_categorias": self.qualidade.limite_categorias,
            },
            "observacoes": self.observacoes,
        }

    def salvar(self, caminho: str) -> str:
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(self.para_dicionario(), arquivo, ensure_ascii=False, indent=2)
        return caminho


def carregar_perfil(caminho: str) -> Perfil:
    with open(caminho, "r", encoding="utf-8-sig") as arquivo:
        dados = json.load(arquivo)
    return perfil_de_dicionario(dados)


def perfil_de_dicionario(dados: Dict[str, Any]) -> Perfil:
    perfil = Perfil(nome=dados.get("nome", "Perfil"))
    for bruto in dados.get("sistemas", []):
        perfil.sistemas.append(SistemaConfig(
            id=str(bruto.get("id") or bruto.get("nome", "A"))[:2].upper(),
            nome=bruto.get("nome", "Sistema"),
            padroes_arquivo=list(bruto.get("padroes_arquivo", [])),
            padroes_aba=list(bruto.get("padroes_aba", [])),
            colunas_esperadas=list(bruto.get("colunas_esperadas", [])),
            mapeamento={k: list(v) if isinstance(v, list) else [v]
                        for k, v in (bruto.get("mapeamento") or {}).items()},
            ignorar_colunas=list(bruto.get("ignorar_colunas", [])),
        ))
    for bruto in dados.get("campos", []):
        perfil.campos.append(CampoConfig(
            nome=bruto["nome"],
            tipo=bruto.get("tipo", "texto"),
            obrigatorio=bool(bruto.get("obrigatorio", False)),
            chave=bool(bruto.get("chave", False)),
            unico=bool(bruto.get("unico", False)),
            dominio=list(bruto.get("dominio", [])),
            minimo=bruto.get("minimo"),
            maximo=bruto.get("maximo"),
            tamanho_minimo=bruto.get("tamanho_minimo"),
            tamanho_maximo=bruto.get("tamanho_maximo"),
            descricao=bruto.get("descricao", ""),
        ))
    bruto_par = dados.get("pareamento", {})
    perfil.pareamento = PareamentoConfig(
        chaves_primarias=list(bruto_par.get("chaves_primarias", [])),
        chaves_alternativas=[list(c) for c in bruto_par.get("chaves_alternativas", [])],
        campos_similaridade=list(bruto_par.get("campos_similaridade", [])),
        campos_comparacao=list(bruto_par.get("campos_comparacao", [])),
        limiar_provavel=float(bruto_par.get("limiar_provavel", 0.90)),
        limiar_duvidoso=float(bruto_par.get("limiar_duvidoso", 0.78)),
        bloqueio=bruto_par.get("bloqueio", "auto"),
    )
    bruto_qual = dados.get("qualidade", {})
    perfil.qualidade = QualidadeConfig(
        regras_consistencia=[
            RegraConsistencia(
                nome=r.get("nome", "regra"),
                campo_a=r.get("campo_a", ""),
                operador=r.get("operador", ">="),
                campo_b=r.get("campo_b", ""),
                valor=str(r.get("valor", "")),
                descricao=r.get("descricao", ""),
            )
            for r in bruto_qual.get("regras_consistencia", [])
        ],
        data_minima=bruto_qual.get("data_minima", "1900-01-01"),
        data_maxima=bruto_qual.get("data_maxima", ""),
        detectar_outliers=bool(bruto_qual.get("detectar_outliers", True)),
        limite_categorias=int(bruto_qual.get("limite_categorias", 30)),
    )
    perfil.observacoes = dados.get("observacoes", "")
    return perfil


def perfil_padrao() -> Perfil:
    """Perfil vazio: os dois sistemas serao reconhecidos automaticamente."""
    return Perfil(
        nome="Perfil automatico",
        sistemas=[
            SistemaConfig(id="A", nome="Sistema A"),
            SistemaConfig(id="B", nome="Sistema B"),
        ],
    )


def localizar_perfil(pasta: str) -> Optional[str]:
    """Procura um perfil .json na pasta indicada (o mais recente vence)."""
    if not os.path.isdir(pasta):
        return None
    candidatos = [
        os.path.join(pasta, nome)
        for nome in os.listdir(pasta)
        if nome.lower().endswith(".json")
    ]
    if not candidatos:
        return None
    return max(candidatos, key=os.path.getmtime)
