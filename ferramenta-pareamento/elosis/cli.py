# -*- coding: utf-8 -*-
"""
Interface de linha de comando do ELO-SIS.

Destina-se à execução em lote e ao agendamento periódico. A interface gráfica
(`python -m elosis`) é a via recomendada para o uso cotidiano.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .leitura import FORMATOS_SUPORTADOS, ErroLeitura
from .perfis import PERSPECTIVAS
from .pipeline import Configuracao, executar
from .planilha import gerar_planilha
from .relatorio import gerar_relatorio


def construir_analisador() -> argparse.ArgumentParser:
    analisador = argparse.ArgumentParser(
        prog="elosis",
        description=(
            "ELO-SIS — Qualificação, harmonização e pareamento de bases dos "
            "sistemas de informação em saúde (SIM, SINAN e SINASC). "
            "Processamento integralmente local: nenhum dado é enviado para "
            "fora da estação de trabalho."),
        epilog=(
            "Exemplo: elosis analisar sim.dbf sinan.dbf sinasc.dbf "
            "-s resultados/"),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    analisador.add_argument("--versao", action="version",
                            version=f"ELO-SIS {__version__}")

    subcomandos = analisador.add_subparsers(dest="comando", required=True)

    analisar = subcomandos.add_parser(
        "analisar", help="Executa a análise completa sobre as bases indicadas.")
    analisar.add_argument("arquivos", nargs="+", type=Path,
                          help=f"Bases a analisar. Formatos aceitos: "
                               f"{', '.join(sorted(FORMATOS_SUPORTADOS))}.")
    analisar.add_argument("-s", "--saida", type=Path,
                          default=Path("resultados_elosis"),
                          help="Diretório de saída (padrão: resultados_elosis).")
    analisar.add_argument("--limiar", type=float, default=0.90,
                          help="Limiar de pareamento (padrão: 0.90).")
    analisar.add_argument("--limiar-revisao", type=float, default=0.85,
                          help="Limiar da faixa de revisão manual (padrão: 0.85).")
    analisar.add_argument("--limiar-duplicidade", type=float, default=0.92,
                          help="Limiar de duplicidade provável (padrão: 0.92).")
    analisar.add_argument("--ano", type=int, default=2024,
                          help="Ano de referência das análises (padrão: 2024).")
    analisar.add_argument("--populacao", type=int, default=2_418_005,
                          help="População de referência para os coeficientes.")
    analisar.add_argument("--horizonte", type=int, default=6,
                          help="Meses a projetar (padrão: 6).")
    analisar.add_argument("--referencia", type=Path, default=None,
                          help=("Amostra de referência para aferir "
                                "sensibilidade e valor preditivo positivo. "
                                "Deve conter as colunas SISTEMA, ID_PESSOA e "
                                "REGISTRO."))
    analisar.add_argument("--perspectiva-sinasc", default=None,
                          choices=sorted(PERSPECTIVAS),
                          help=("Fixa a perspectiva de identidade do SINASC. "
                                "Sem esta opção, a perspectiva é escolhida "
                                "conforme o par de bases em relacionamento."))
    analisar.add_argument("--pseudonimizar", action="store_true",
                          help="Substitui identificadores diretos por "
                               "pseudônimos na planilha de saída.")
    analisar.add_argument("--limite", type=int, default=None,
                          help="Lê no máximo N registros por base (para teste).")
    analisar.add_argument("--sem-relatorio", action="store_true",
                          help="Não gera o relatório em formato Word.")
    analisar.add_argument("--sem-planilha", action="store_true",
                          help="Não gera a planilha de resultados.")
    analisar.add_argument("--permitir-rede", action="store_true",
                          help=("Desativa o modo cofre. Não recomendado: o "
                                "modo cofre é a garantia técnica de que "
                                "nenhum dado sai da estação."))

    exemplo = subcomandos.add_parser(
        "gerar-exemplo",
        help=("Gera bases fictícias do SIM, SINAN e SINASC para treinamento e "
              "para o piloto, com defeitos conhecidos e gabarito de "
              "pareamento."))
    exemplo.add_argument("-s", "--saida", type=Path,
                         default=Path("bases_ficticias"),
                         help="Diretório de destino.")
    exemplo.add_argument("--formato", default="csv",
                         choices=["csv", "dbf", "xlsx"],
                         help="Formato das bases geradas (padrão: csv).")
    exemplo.add_argument("--sinan", type=int, default=3000,
                         help="Registros do SINAN (padrão: 3000).")
    exemplo.add_argument("--sim", type=int, default=1200,
                         help="Registros do SIM (padrão: 1200).")
    exemplo.add_argument("--sinasc", type=int, default=2000,
                         help="Registros do SINASC (padrão: 2000).")

    subcomandos.add_parser("interface",
                           help="Abre a interface gráfica do ELO-SIS.")
    return analisador


def _executar_analise(argumentos) -> int:
    ausentes = [a for a in argumentos.arquivos if not Path(a).exists()]
    if ausentes:
        print("Arquivos não encontrados:", file=sys.stderr)
        for arquivo in ausentes:
            print(f"  {arquivo}", file=sys.stderr)
        return 2

    perspectivas = ({"SINASC": argumentos.perspectiva_sinasc}
                    if argumentos.perspectiva_sinasc else {})

    configuracao = Configuracao(
        arquivos=[Path(a) for a in argumentos.arquivos],
        diretorio_saida=argumentos.saida,
        limiar_pareamento=argumentos.limiar,
        limiar_revisao=argumentos.limiar_revisao,
        limiar_duplicidade=argumentos.limiar_duplicidade,
        ano_referencia=argumentos.ano,
        populacao_referencia=argumentos.populacao,
        horizonte_projecao=argumentos.horizonte,
        pseudonimizar_saida=argumentos.pseudonimizar,
        gerar_relatorio=not argumentos.sem_relatorio,
        gerar_planilha=not argumentos.sem_planilha,
        limite_registros=argumentos.limite,
        arquivo_referencia=argumentos.referencia,
        perspectivas=perspectivas,
        modo_cofre=not argumentos.permitir_rede,
    )

    def progresso(passo: str, fracao: float) -> None:
        largura = 28
        preenchido = int(largura * fracao)
        barra = "█" * preenchido + "░" * (largura - preenchido)
        print(f"\r  [{barra}] {fracao * 100:3.0f}%  {passo[:52]:<52}",
              end="", flush=True)

    print(f"\nELO-SIS {__version__} — análise de "
          f"{len(configuracao.arquivos)} base(s)\n")
    try:
        resultado = executar(configuracao, progresso)
    except ErroLeitura as erro:
        print(f"\n\nErro: {erro}", file=sys.stderr)
        return 1
    print()

    produtos = []
    if configuracao.gerar_planilha:
        progresso("Gerando planilha de resultados...", 0.88)
        produtos.append(gerar_planilha(resultado))
    if configuracao.gerar_relatorio:
        progresso("Gerando relatório analítico...", 0.94)
        produtos.append(gerar_relatorio(resultado))
    produtos.append(resultado.trilha.salvar())
    progresso("Concluído.", 1.0)
    print("\n")

    _imprimir_resumo(resultado, produtos)
    return 0


def _imprimir_resumo(resultado, produtos) -> None:
    print("  RESUMO DA ANÁLISE")
    print("  " + "─" * 74)
    cabecalho = (f"  {'Base':<10}{'Registros':>10}{'Escore':>9}"
                 f"{'Verdes':>9}{'Amarelas':>10}{'Vermelhas':>11}")
    print(cabecalho)
    for linha in resultado.resumo_executivo():
        print(f"  {linha['BASE']:<10}{linha['REGISTROS']:>10,}"
              f"{linha['ESCORE_DE_QUALIDADE']:>9.2f}"
              f"{linha['LINHAS_VERDES']:>9,}{linha['LINHAS_AMARELAS']:>10,}"
              f"{linha['LINHAS_VERMELHAS']:>11,}".replace(",", "."))

    if resultado.pareamentos:
        print("\n  PAREAMENTOS")
        print("  " + "─" * 74)
        print(f"  {'Relacionamento':<18}{'Determ.':>9}{'Probab.':>9}"
              f"{'Total':>8}{'Revisão':>9}{'Taxa (%)':>10}")
        for pareamento in resultado.pareamentos:
            r = pareamento.resumo()
            print(f"  {r['RELACIONAMENTO']:<18}"
                  f"{r['PARES_DETERMINISTICOS']:>9,}"
                  f"{r['PARES_PROBABILISTICOS']:>9,}"
                  f"{r['PARES_TOTAIS']:>8,}"
                  f"{r['PARES_PARA_REVISAO_MANUAL']:>9,}"
                  f"{r['TAXA_DE_PAREAMENTO_%']:>10.2f}".replace(",", "."))

    if resultado.validacoes:
        print("\n  DESEMPENHO CONTRA A AMOSTRA DE REFERÊNCIA")
        print("  " + "─" * 74)
        for validacao in resultado.validacoes:
            print(f"  {validacao.relacionamento:<18}"
                  f"sensibilidade {100 * validacao.sensibilidade:5.1f}%   "
                  f"VPP {100 * validacao.valor_preditivo_positivo:5.1f}%   "
                  f"medida F {100 * validacao.medida_f:5.1f}%")

    if resultado.avisos:
        print("\n  AVISOS")
        print("  " + "─" * 74)
        for aviso in resultado.avisos:
            print(f"  • {aviso}")

    print("\n  PRODUTOS GERADOS")
    print("  " + "─" * 74)
    for produto in produtos:
        print(f"  • {Path(produto).resolve()}")
    print(f"\n  Tempo total: {resultado.tempo_total:.1f} segundos.")
    print("  Processamento local: nenhum dado foi enviado para fora "
          "desta estação.\n")


def _gerar_exemplo(argumentos) -> int:
    from .dados_ficticios import salvar_bases
    print(f"\nGerando bases fictícias em {argumentos.saida.resolve()}...\n")
    caminhos = salvar_bases(argumentos.saida, formato=argumentos.formato,
                            n_sinan=argumentos.sinan, n_sim=argumentos.sim,
                            n_sinasc=argumentos.sinasc)
    for sigla, caminho in caminhos.items():
        print(f"  • {sigla:<10} {caminho.resolve()}")
    print("\n  As bases contêm defeitos deliberados — duplicidades, "
          "incompletude,\n  códigos fora de domínio, datas impossíveis e erros "
          "de digitação —\n  para que a capacidade de detecção da ferramenta "
          "possa ser aferida.")
    print("  O arquivo de gabarito permite calcular sensibilidade e valor "
          "preditivo\n  positivo: informe-o com a opção --referencia.")
    print("\n  Nenhum dado real é utilizado: os nomes são combinações "
          "aleatórias\n  sem correspondência com pessoas.\n")
    return 0


def principal(argumentos=None) -> int:
    analisador = construir_analisador()
    opcoes = analisador.parse_args(argumentos)

    if opcoes.comando == "analisar":
        return _executar_analise(opcoes)
    if opcoes.comando == "gerar-exemplo":
        return _gerar_exemplo(opcoes)
    if opcoes.comando == "interface":
        from .gui import abrir_interface
        return abrir_interface()
    analisador.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(principal())
