"""QualiSIS — avaliação da qualidade dos sistemas de informação em saúde.

Subcoordenadoria de Informação em Saúde — Secretaria Municipal da Saúde de Salvador.
"""

from .processamento import VERSAO, executar  # noqa: F401

__all__ = ["executar", "VERSAO"]
__version__ = VERSAO
