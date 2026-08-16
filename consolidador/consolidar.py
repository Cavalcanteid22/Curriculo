#!/usr/bin/env python3
"""Linha de comando do consolidador.

Exemplos:

    python consolidar.py entradas
    python consolidar.py entradas -s saidas
    python consolidar.py arq1.csv arq2.html arq3.dbf -s saidas
    python consolidar.py entradas -p perfis/meu_perfil.json
    python consolidar.py entradas --sistema-a "SIGA_*.csv" --sistema-b "RHNET*"

O comando aceita arquivos e pastas. Sem perfil, os dois sistemas sao
reconhecidos automaticamente pela semelhanca entre os arquivos.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nucleo.config import carregar_perfil, perfil_padrao  # noqa: E402
from nucleo.pipeline import executar, expandir_entradas, gerar_perfil  # noqa: E402


def montar_argumentos() -> argparse.ArgumentParser:
    analisador = argparse.ArgumentParser(
        prog="consolidar",
        description="Consolida, analisa a qualidade e pareia as bases de dois sistemas.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    analisador.add_argument("entradas", nargs="+", help="arquivos e/ou pastas de entrada")
    analisador.add_argument("-s", "--saida", default="saidas",
                            help="pasta onde gravar a planilha e o relatorio (padrao: saidas)")
    analisador.add_argument("-p", "--perfil", default="",
                            help="arquivo .json de perfil com as regras dos dois sistemas")
    analisador.add_argument("--sistema-a", default="",
                            help="padrao de nome de arquivo do primeiro sistema (ex.: 'SIGA*')")
    analisador.add_argument("--sistema-b", default="",
                            help="padrao de nome de arquivo do segundo sistema")
    analisador.add_argument("--nome-a", default="", help="nome do primeiro sistema no relatorio")
    analisador.add_argument("--nome-b", default="", help="nome do segundo sistema no relatorio")
    analisador.add_argument("--prefixo", default="",
                            help="prefixo dos arquivos gerados (padrao: nomes + data e hora)")
    analisador.add_argument("--salvar-perfil", default="",
                            help="grava um perfil .json com as regras deduzidas nesta execucao")
    analisador.add_argument("-q", "--silencioso", action="store_true", help="nao exibir o andamento")
    return analisador


def main(argumentos=None) -> int:
    opcoes = montar_argumentos().parse_args(argumentos)
    perfil = carregar_perfil(opcoes.perfil) if opcoes.perfil else perfil_padrao()
    if opcoes.nome_a:
        perfil.sistemas[0].nome = opcoes.nome_a
    if opcoes.nome_b:
        perfil.sistemas[1].nome = opcoes.nome_b

    atribuicoes = {}
    if opcoes.sistema_a or opcoes.sistema_b:
        for caminho in expandir_entradas(opcoes.entradas):
            nome = os.path.basename(caminho)
            if opcoes.sistema_a and fnmatch.fnmatch(nome.lower(), opcoes.sistema_a.lower()):
                atribuicoes[caminho] = "A"
            elif opcoes.sistema_b and fnmatch.fnmatch(nome.lower(), opcoes.sistema_b.lower()):
                atribuicoes[caminho] = "B"

    progresso = None if opcoes.silencioso else (lambda mensagem: print(mensagem, flush=True))
    resultado = executar(
        opcoes.entradas, opcoes.saida, perfil=perfil,
        atribuicoes_manuais=atribuicoes, prefixo_saida=opcoes.prefixo, progresso=progresso,
    )

    if opcoes.salvar_perfil and resultado.consolidado_a:
        gerar_perfil(resultado).salvar(opcoes.salvar_perfil)
        if not opcoes.silencioso:
            print(f"Perfil gravado em: {opcoes.salvar_perfil}")

    if resultado.erros and not resultado.caminho_planilha:
        for erro in resultado.erros:
            print(f"ERRO: {erro}", file=sys.stderr)
        return 1
    if not opcoes.silencioso:
        estatisticas = resultado.estatisticas()
        print()
        print(f"Planilha : {resultado.caminho_planilha}")
        print(f"Relatorio: {resultado.caminho_relatorio}")
        print(
            f"{resultado.nome_a}: {estatisticas['registros_a']} registros | "
            f"{resultado.nome_b}: {estatisticas['registros_b']} registros | "
            f"pares: {estatisticas['pares']} | so em {resultado.nome_a}: "
            f"{estatisticas['somente_a']} | so em {resultado.nome_b}: {estatisticas['somente_b']}"
        )
        for erro in resultado.erros:
            print(f"AVISO: {erro}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
