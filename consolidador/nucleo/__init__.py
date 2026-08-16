"""Nucleo do consolidador: leitura, consolidacao, qualidade, pareamento e saidas.

Uso rapido:

    from nucleo.pipeline import executar
    resultado = executar(["C:/entradas"], "C:/saidas")
    print(resultado.caminho_planilha, resultado.caminho_relatorio)
"""

VERSAO = "1.0.0"

__all__ = ["VERSAO"]
