"""Estrutura com todo o resultado de uma execucao."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import Perfil
from .deteccao import ResultadoDeteccao
from .normalizacao import Consolidado
from .pareamento import ResultadoPareamento
from .qualidade import ResultadoQualidade


@dataclass
class ArquivoLido:
    caminho: str
    nome: str
    extensao: str
    tabelas: int = 0
    registros: int = 0
    sistema: str = ""
    confianca: float = 0.0
    justificativa: str = ""
    erro: str = ""


@dataclass
class ResultadoGeral:
    perfil: Perfil
    deteccao: Optional[ResultadoDeteccao] = None
    consolidado_a: Optional[Consolidado] = None
    consolidado_b: Optional[Consolidado] = None
    qualidade_a: Optional[ResultadoQualidade] = None
    qualidade_b: Optional[ResultadoQualidade] = None
    pareamento: Optional[ResultadoPareamento] = None
    arquivos: List[ArquivoLido] = field(default_factory=list)
    erros: List[str] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    inicio: _dt.datetime = field(default_factory=_dt.datetime.now)
    fim: Optional[_dt.datetime] = None
    caminho_planilha: str = ""
    caminho_relatorio: str = ""

    @property
    def duracao_segundos(self) -> float:
        fim = self.fim or _dt.datetime.now()
        return (fim - self.inicio).total_seconds()

    @property
    def nome_a(self) -> str:
        return self.consolidado_a.nome if self.consolidado_a else "Sistema A"

    @property
    def nome_b(self) -> str:
        return self.consolidado_b.nome if self.consolidado_b else "Sistema B"

    def estatisticas(self) -> Dict[str, Any]:
        total_a = len(self.consolidado_a.tabela.linhas) if self.consolidado_a else 0
        total_b = len(self.consolidado_b.tabela.linhas) if self.consolidado_b else 0
        pares = self.pareamento.total_pares if self.pareamento else 0
        so_a = len(self.pareamento.somente_a) if self.pareamento else total_a
        so_b = len(self.pareamento.somente_b) if self.pareamento else total_b
        return {
            "registros_a": total_a,
            "registros_b": total_b,
            "pares": pares,
            "somente_a": so_a,
            "somente_b": so_b,
            "divergentes": self.pareamento.pares_divergentes if self.pareamento else 0,
            "cobertura_a": (100.0 * (total_a - so_a) / total_a) if total_a else 0.0,
            "cobertura_b": (100.0 * (total_b - so_b) / total_b) if total_b else 0.0,
        }
