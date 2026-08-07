"""Interface de linha de comando (e menu interativo) do QualiSIS."""

from __future__ import annotations

import argparse
import os
import sys

from . import config as config_mod
from . import consolidado as consolidado_mod
from . import processamento
from .instrumento import gerar_instrumento
from .leitura import LeitorCSV
from .comparacao import Historico

BANNER = r"""
  ___              _ _ ____ ___ ____
 / _ \ _   _  __ _| (_) ___|_ _/ ___|   Avaliação da qualidade dos
| | | | | | |/ _` | | \___ \| |\___ \   sistemas de informação em saúde
| |_| | |_| | (_| | | |___) | | ___) |  Subcoordenadoria de Informação em Saúde
 \__\_\\__,_|\__,_|_|_|____/___|____/   SMS Salvador
"""


def _parser():
    p = argparse.ArgumentParser(
        prog="qualisis",
        description="Avalia a qualidade das bases dos sistemas de informação em saúde "
                    "(SIM, SINAN, SINASC, e-SUS SINAN, SINAN Online).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exemplos:\n"
               "  python executar.py analisar -s sim -b bases/SIM_2026.csv\n"
               "  python executar.py analisar -s sinan -b bases/SINAN.csv --pintar-linha-inteira\n"
               "  python executar.py consolidar\n"
               "  python executar.py instrumento -s sinasc\n")
    sub = p.add_subparsers(dest="comando")

    a = sub.add_parser("analisar", help="analisa a base CSV de um sistema")
    a.add_argument("-s", "--sistema", required=True,
                   help="sigla do sistema (sim, sinan, sinasc, esus_sinan, sinan_online) "
                        "ou caminho de um arquivo de configuração .json")
    a.add_argument("-b", "--base", required=True, help="arquivo CSV (aceita .csv e .csv.gz)")
    a.add_argument("-o", "--saida", default="saida", help="pasta de saída (padrão: saida)")
    a.add_argument("--data-extracao", help="data da extração da base (AAAA-MM-DD ou DD/MM/AAAA)")
    a.add_argument("--limite", type=int, help="processa apenas as N primeiras linhas (teste)")
    a.add_argument("--historico", default="historico", help="pasta do histórico de execuções")
    a.add_argument("--max-linhas-excel", type=int, default=200_000,
                   help="máximo de linhas inconsistentes exportadas para o Excel "
                        "(padrão: 200000; use 0 para não limitar)")
    a.add_argument("--pintar-linha-inteira", action="store_true",
                   help="pinta a linha toda com a cor da inconsistência mais grave")
    a.add_argument("--sem-excel", action="store_true", help="não gerar a planilha")
    a.add_argument("--sem-html", action="store_true", help="não gerar o relatório HTML")
    a.add_argument("--sem-csv", action="store_true", help="não gerar os CSV de apoio")
    a.add_argument("--sem-comparacao", action="store_true",
                   help="não comparar com o envio anterior")
    a.add_argument("--instrumento", action="store_true",
                   help="gerar também a planilha do instrumento qualitativo")
    a.add_argument("--silencioso", action="store_true", help="não imprimir o progresso")

    c = sub.add_parser("consolidar", help="painel comparativo entre todos os sistemas")
    c.add_argument("--historico", default="historico")
    c.add_argument("-o", "--saida", default=os.path.join("saida", "painel_consolidado.html"))
    c.add_argument("-s", "--sistemas", nargs="*", help="limitar a estes sistemas")

    i = sub.add_parser("instrumento", help="gera a planilha de avaliação qualitativa")
    i.add_argument("-s", "--sistema", required=True)
    i.add_argument("-o", "--saida")

    v = sub.add_parser("validar", help="confere o layout da base contra o dicionário de dados")
    v.add_argument("-s", "--sistema", required=True)
    v.add_argument("-b", "--base", required=True)

    h = sub.add_parser("historico", help="lista as execuções já realizadas")
    h.add_argument("-s", "--sistema", required=True)
    h.add_argument("--historico", default="historico")

    sub.add_parser("listar", help="lista os sistemas configurados")
    return p


# --------------------------------------------------------------------------- #
def cmd_analisar(args):
    resultado = processamento.executar(
        args.sistema, args.base, pasta_saida=args.saida,
        data_extracao=args.data_extracao, limite=args.limite,
        gerar_excel=not args.sem_excel, gerar_html=not args.sem_html,
        gerar_csv=not args.sem_csv, comparar=not args.sem_comparacao,
        pintar_linha_inteira=args.pintar_linha_inteira,
        max_linhas_excel=(None if args.max_linhas_excel == 0 else args.max_linhas_excel),
        pasta_historico=args.historico, silencioso=args.silencioso,
    )
    if args.instrumento:
        caminho = os.path.join(resultado["destino"],
                               f"{resultado['sistema']}_instrumento_qualitativo.xlsx")
        gerar_instrumento(resultado["config"], caminho,
                          indicadores=resultado["indicadores"], escore_automatico=resultado["escore"])
        print(f"  instrumento .. {caminho}", file=sys.stderr)
    print(f"\nProdutos em: {os.path.abspath(resultado['destino'])}")
    return 0


def cmd_consolidar(args):
    caminho = consolidado_mod.gerar_consolidado(args.historico, args.saida, siglas=args.sistemas)
    print(f"Painel consolidado: {os.path.abspath(caminho)}")
    return 0


def cmd_instrumento(args):
    cfg = config_mod.carregar(args.sistema)
    saida = args.saida or os.path.join("saida", f"{cfg.sigla}_instrumento_qualitativo.xlsx")
    os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
    hist = Historico("historico", cfg.sigla)
    ultima = hist.ultima_execucao()
    indicadores = None
    escore = None
    if ultima:
        indicadores = {k: {"valor": v.get("valor"), "classificacao": "", "formula": ""}
                       for k, v in (ultima.get("indicadores") or {}).items()}
        escore = ultima.get("escore")
    gerar_instrumento(cfg, saida, indicadores=indicadores, escore_automatico=escore)
    print(f"Instrumento gerado: {os.path.abspath(saida)}")
    return 0


def cmd_validar(args):
    cfg = config_mod.carregar(args.sistema)
    with LeitorCSV(args.base, encoding=cfg.encoding, separador=cfg.separador,
                   mapa_colunas=cfg.mapa_colunas) as leitor:
        colunas = leitor.colunas
        amostra = []
        for i, (_n, linha) in enumerate(leitor):
            amostra.append(linha)
            if i >= 4:
                break
    cobertura = cfg.validar_contra_base(colunas)
    print(f"\nSistema ............ {cfg.sigla} — {cfg.nome}")
    print(f"Arquivo ............ {args.base}")
    print(f"Codificação ........ {leitor.encoding}")
    print(f"Separador .......... {leitor.separador!r}")
    print(f"Colunas na base .... {len(colunas)}")
    print(f"Campos do dicionário {len(cfg.campos)}")
    print(f"  reconhecidos ..... {len(cobertura['cobertas'])}")
    print(f"  ausentes ......... {len(cobertura['ausentes'])}: "
          f"{', '.join(cobertura['ausentes']) or '—'}")
    print(f"  fora do dicionário {len(cobertura['nao_previstas'])}: "
          f"{', '.join(cobertura['nao_previstas'][:25]) or '—'}")
    if cobertura["ausentes"]:
        print("\nAtenção: campos ausentes não serão avaliados. Se a exportação usa outro "
              "nome para eles, cadastre o apelido em 'apelidos_colunas' na configuração.")
    return 0


def cmd_historico(args):
    cfg = config_mod.carregar(args.sistema)
    execs = Historico(args.historico, cfg.sigla).execucoes()
    if not execs:
        print("Nenhuma execução registrada para este sistema.")
        return 0
    print(f"\n{cfg.sigla} — {len(execs)} execução(ões) registradas\n")
    print(f"{'Data':<18}{'Registros':>12}{'Ocorrências':>14}{'Escore':>9}{'Resolut.':>10}  Arquivo")
    for ex in execs:
        escore = f"{ex['escore']:.1f}%" if ex.get("escore") is not None else "—"
        resol = f"{ex['resolutividade']:.1f}%" if ex.get("resolutividade") is not None else "—"
        registros = f"{ex.get('registros', 0):,}".replace(",", ".")
        ocorrencias = f"{ex.get('ocorrencias', 0):,}".replace(",", ".")
        print(f"{ex.get('data_processamento', ''):<18}{registros:>12}{ocorrencias:>14}"
              f"{escore:>9}{resol:>10}  {ex.get('arquivo', '')}")
    return 0


def cmd_listar(_args=None):
    print("\nSistemas configurados (pasta configs/):\n")
    for sigla in config_mod.listar():
        try:
            cfg = config_mod.carregar(sigla)
            print(f"  {sigla:<16} {cfg.sigla} — {cfg.nome}")
            print(f"  {'':<16} {len(cfg.campos)} campos, {len(cfg.regras_cruzadas)} regras "
                  f"cruzadas, {len(cfg.chaves_duplicidade)} chave(s) de duplicidade")
        except Exception as erro:  # configuração inválida não pode derrubar a listagem
            print(f"  {sigla:<16} (erro ao ler: {erro})")
    return 0


# --------------------------------------------------------------------------- #
def menu_interativo():
    """Menu simples para quem prefere não usar a linha de comando."""
    print(BANNER)
    sistemas = config_mod.listar()
    if not sistemas:
        print("Nenhuma configuração encontrada na pasta 'configs'.")
        return 1
    print("Sistemas disponíveis:")
    for i, sigla in enumerate(sistemas, start=1):
        cfg = config_mod.carregar(sigla)
        print(f"  {i}. {cfg.sigla} — {cfg.nome}")
    print("  0. Painel consolidado de todos os sistemas")
    try:
        escolha = input("\nEscolha o número do sistema: ").strip()
    except (EOFError, KeyboardInterrupt):
        return 1
    if escolha == "0":
        caminho = consolidado_mod.gerar_consolidado(
            "historico", os.path.join("saida", "painel_consolidado.html"))
        print(f"\nPainel consolidado gerado: {os.path.abspath(caminho)}")
        return 0
    try:
        sigla = sistemas[int(escolha) - 1]
    except (ValueError, IndexError):
        print("Opção inválida.")
        return 1
    base = input("Caminho do arquivo CSV da base: ").strip().strip('"')
    if not os.path.exists(base):
        print(f"Arquivo não encontrado: {base}")
        return 1
    data = input("Data da extração (DD/MM/AAAA, Enter para usar a data do arquivo): ").strip()
    inteira = input("Pintar a linha inteira? (s/N): ").strip().lower().startswith("s")
    resultado = processamento.executar(sigla, base, data_extracao=data or None,
                                       pintar_linha_inteira=inteira)
    caminho = os.path.join(resultado["destino"],
                           f"{resultado['sistema']}_instrumento_qualitativo.xlsx")
    gerar_instrumento(resultado["config"], caminho, indicadores=resultado["indicadores"],
                      escore_automatico=resultado["escore"])
    print(f"\nProdutos gerados em: {os.path.abspath(resultado['destino'])}")
    input("\nPressione Enter para fechar...")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return menu_interativo()
    args = _parser().parse_args(argv)
    comandos = {
        "analisar": cmd_analisar, "consolidar": cmd_consolidar,
        "instrumento": cmd_instrumento, "validar": cmd_validar,
        "historico": cmd_historico, "listar": cmd_listar,
    }
    if args.comando not in comandos:
        _parser().print_help()
        return 1
    try:
        return comandos[args.comando](args)
    except (config_mod.ErroConfig, FileNotFoundError, RuntimeError) as erro:
        print(f"\nErro: {erro}", file=sys.stderr)
        return 2
