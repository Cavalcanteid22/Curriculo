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
# Menu interativo — para uso sem linha de comando
# --------------------------------------------------------------------------- #

def _perguntar(texto, padrao=""):
    try:
        resposta = input(texto).strip().strip('"').strip("'")
    except (EOFError, KeyboardInterrupt):
        raise SystemExit(0)
    return resposta or padrao


def _abrir(caminho):
    """Abre o arquivo ou a pasta no programa padrão do sistema operacional."""
    caminho = os.path.abspath(caminho)
    try:
        if sys.platform.startswith("win"):
            os.startfile(caminho)  # noqa: S606 - abertura no Explorer do Windows
        elif sys.platform == "darwin":
            os.system(f'open "{caminho}"')
        else:
            os.system(f'xdg-open "{caminho}" >/dev/null 2>&1 &')
        return True
    except Exception:
        return False


def _executar_pelo_menu(sigla, base):
    data = _perguntar("Data da extração da base (DD/MM/AAAA) — Enter usa a data do arquivo: ")
    inteira = _perguntar("Pintar a linha inteira, e não só a célula? (s/N): ").lower()
    print("\nProcessando... (pode demorar alguns minutos em bases grandes)\n")
    resultado = processamento.executar(
        sigla, base, data_extracao=data or None,
        pintar_linha_inteira=inteira.startswith("s"))
    caminho_inst = os.path.join(resultado["destino"],
                                f"{resultado['sistema']}_instrumento_qualitativo.xlsx")
    gerar_instrumento(resultado["config"], caminho_inst,
                      indicadores=resultado["indicadores"],
                      escore_automatico=resultado["escore"])
    destino = os.path.abspath(resultado["destino"])
    print("\n" + "=" * 66)
    print("PRONTO. Os arquivos foram gravados em:")
    print(f"  {destino}")
    print("\n  RELATÓRIO (abra primeiro) .... "
          f"{resultado['sistema']}_relatorio.html")
    print(f"  PLANILHA COLORIDA ............ {resultado['sistema']}_inconsistencias.xlsx")
    print(f"  INSTRUMENTO (fórmulas) ....... {resultado['sistema']}_instrumento_qualitativo.xlsx")
    print("=" * 66)
    if _perguntar("\nAbrir a pasta com os resultados agora? (S/n): ", "s").lower().startswith("s"):
        _abrir(destino)
        _abrir(os.path.join(destino, f"{resultado['sistema']}_relatorio.html"))
    return resultado


def _demonstracao():
    """Gera bases fictícias e roda o fluxo completo — para aprender sem dado real."""
    from exemplos.gerar_exemplos import gerar

    print("\nGerando bases FICTÍCIAS (nenhum dado real) em 'exemplos/bases'...\n")
    gerar("exemplos/bases", registros=1500)
    for sigla, arquivo in (("sim", "SIM_envio1.csv"), ("sim", "SIM_envio2.csv")):
        print(f"\n--- Analisando {arquivo} ---")
        resultado = processamento.executar(sigla, os.path.join("exemplos", "bases", arquivo))
    destino = os.path.abspath(resultado["destino"])
    print("\n" + "=" * 66)
    print("Demonstração concluída. Foram analisados dois 'envios' seguidos, então o")
    print("relatório do segundo já mostra a comparação de resolutividade.")
    print(f"\nResultados em: {destino}")
    print("=" * 66)
    if _perguntar("\nAbrir o relatório agora? (S/n): ", "s").lower().startswith("s"):
        _abrir(os.path.join(destino, "SIM_relatorio.html"))
    return 0


def menu_interativo():
    print(BANNER)
    sistemas = config_mod.listar()
    if not sistemas:
        print("Nenhuma configuração encontrada na pasta 'configs'.")
        input("\nPressione Enter para fechar...")
        return 1

    while True:
        print("\n" + "=" * 66)
        print("O QUE VOCÊ QUER FAZER?")
        print("=" * 66)
        print("\n  ANALISAR A BASE DE UM SISTEMA:")
        for i, sigla in enumerate(sistemas, start=1):
            cfg = config_mod.carregar(sigla)
            print(f"    {i}. {cfg.sigla:<13} {cfg.nome}")
        print("\n  OUTRAS OPÇÕES:")
        print("    C. Painel consolidado (compara todos os sistemas já analisados)")
        print("    V. Conferir se o layout do CSV bate com o dicionário (recomendado na 1ª vez)")
        print("    H. Ver o histórico de análises de um sistema")
        print("    E. EXEMPLO — testar a ferramenta com base fictícia, sem usar dado real")
        print("    S. Sair")

        escolha = _perguntar("\nDigite o número ou a letra e tecle Enter: ").upper()

        if escolha in ("S", "SAIR", ""):
            return 0

        try:
            if escolha == "E":
                _demonstracao()
                continue

            if escolha == "C":
                caminho = consolidado_mod.gerar_consolidado(
                    "historico", os.path.join("saida", "painel_consolidado.html"))
                print(f"\nPainel consolidado gerado em:\n  {os.path.abspath(caminho)}")
                if _perguntar("\nAbrir agora? (S/n): ", "s").lower().startswith("s"):
                    _abrir(caminho)
                continue

            if escolha in ("V", "H"):
                sigla = _escolher_sistema(sistemas)
                if not sigla:
                    continue
                if escolha == "H":
                    cmd_historico(_Args(sistema=sigla, historico="historico"))
                    continue
                base = _pedir_arquivo()
                if base:
                    cmd_validar(_Args(sistema=sigla, base=base))
                continue

            indice = int(escolha)
            if not 1 <= indice <= len(sistemas):
                print("\nOpção inválida.")
                continue
            base = _pedir_arquivo()
            if base:
                _executar_pelo_menu(sistemas[indice - 1], base)

        except SystemExit:
            raise
        except Exception as erro:
            print(f"\nDeu problema: {erro}")
            print("Se a mensagem não estiver clara, anote-a e procure o suporte do setor.")


class _Args:
    """Empacota argumentos para reaproveitar os comandos da linha de comando."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _escolher_sistema(sistemas):
    for i, sigla in enumerate(sistemas, start=1):
        print(f"    {i}. {config_mod.carregar(sigla).sigla}")
    escolha = _perguntar("Número do sistema: ")
    try:
        return sistemas[int(escolha) - 1]
    except (ValueError, IndexError):
        print("\nOpção inválida.")
        return None


def _pedir_arquivo():
    print("\nInforme o arquivo CSV da base.")
    print("DICA: arraste o arquivo do Explorer para esta janela e solte — o caminho")
    print("      aparece sozinho. Depois tecle Enter.")
    base = _perguntar("\nArquivo: ")
    if not base:
        return None
    if not os.path.exists(base):
        print(f"\nArquivo não encontrado:\n  {base}")
        print("Confira se o caminho está completo (com a letra do drive, ex.: C:\\...).")
        return None
    return base


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
