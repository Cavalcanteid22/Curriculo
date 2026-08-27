"""Orquestração: lê a base, aplica as regras e escreve todos os produtos.

Estratégia de duas passagens (nunca carrega a base na memória):

    1ª passagem -> descobre quais chaves aparecem mais de uma vez (duplicidade)
    2ª passagem -> avalia registro a registro e vai escrevendo, em fluxo, a
                   planilha colorida, o CSV de ocorrências e a assinatura do
                   envio usada na comparação com o próximo
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime

from . import comparacao as cmp_mod
from . import config as config_mod
from . import relatorio as rel_mod
from . import tipos as T
from .analise import Agregador
from .comparacao import Comparador, GravadorAssinatura, Historico, carimbo_agora
from .excel import RelatorioExcel
from .leitura import LeitorCSV, escrever_csv, tamanho_legivel
from .regras import MotorRegras

VERSAO = "1.0"


def _msg(texto, silencioso=False):
    if not silencioso:
        print(texto, file=sys.stderr, flush=True)


def _data(valor):
    if not valor:
        return None
    if isinstance(valor, date):
        return valor
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(str(valor), fmt).date()
        except ValueError:
            continue
    return None


def executar(sistema, arquivo, pasta_saida="saida", data_extracao=None, limite=None,
             gerar_excel=True, gerar_html=True, gerar_csv=True, comparar=True,
             pintar_linha_inteira=False, max_linhas_excel=200_000,
             pasta_historico="historico", silencioso=False, colunas_saida=None):
    """Executa a avaliação completa de um sistema. Devolve dicionário de resultados."""
    t0 = time.time()
    cfg = config_mod.carregar(sistema)
    if not os.path.exists(arquivo):
        raise FileNotFoundError(f"Base não encontrada: {arquivo}")

    data_extracao = _data(data_extracao) or date.fromtimestamp(os.path.getmtime(arquivo))
    carimbo = _carimbo_livre(pasta_saida, pasta_historico, cfg.sigla)
    destino = os.path.join(pasta_saida, cfg.sigla.lower(), carimbo)
    os.makedirs(destino, exist_ok=True)

    _msg(f"\n=== {cfg.sigla} — {cfg.nome} ===", silencioso)
    _msg(f"Base ......... {arquivo} ({tamanho_legivel(os.path.getsize(arquivo))})", silencioso)
    _msg(f"Extração ..... {data_extracao.strftime('%d/%m/%Y')}", silencioso)
    _msg(f"Saída ........ {destino}", silencioso)

    # ------------------------------------------------------------------ #
    # 1ª passagem: duplicidades
    # ------------------------------------------------------------------ #
    with LeitorCSV(arquivo, encoding=cfg.encoding, separador=cfg.separador,
                   mapa_colunas=cfg.mapa_colunas) as leitor:
        colunas = leitor.colunas
        motor = MotorRegras(cfg, data_extracao=data_extracao, colunas=colunas)
        _msg(f"Colunas ...... {len(colunas)} na base | {len(motor.campos_ativos)} avaliadas "
             f"| {len(motor.regras_ativas)} regras cruzadas ativas", silencioso)
        vistos = [set() for _ in motor.chaves_dup]
        duplicados = [set() for _ in motor.chaves_dup]
        n = 0
        for n_linha, linha in leitor:
            n += 1
            if limite and n > limite:
                break
            for idx, h in motor.hashes_duplicidade(linha):
                if h in vistos[idx]:
                    duplicados[idx].add(h)
                else:
                    vistos[idx].add(h)
            if n % 200_000 == 0:
                _msg(f"  [1/2] {n:,} registros lidos...".replace(",", "."), silencioso)
        total_estimado = n
    del vistos
    _msg(f"  [1/2] duplicidade mapeada em {total_estimado:,} registros "
         f"({sum(len(d) for d in duplicados):,} chaves repetidas)"
         .replace(",", "."), silencioso)

    # ------------------------------------------------------------------ #
    # Preparação da 2ª passagem
    # ------------------------------------------------------------------ #
    historico = Historico(pasta_historico, cfg.sigla)
    anterior = historico.ultima_execucao(ignorar_carimbo=carimbo) if comparar else None
    comparador = None
    if anterior:
        comparador = Comparador(historico, anterior)
        if comparador.carregar_anterior():
            _msg(f"Comparando com o envio de {anterior.get('data_processamento', '')} "
                 f"({len(comparador.hashes_ant):,} ocorrências registradas)"
                 .replace(",", "."), silencioso)
        else:
            _msg("Envio anterior sem arquivo de assinatura — comparação desativada.", silencioso)
            comparador = None

    gravador = GravadorAssinatura(historico, carimbo)
    ag = Agregador(cfg, motor, data_extracao=data_extracao)

    excel = None
    if gerar_excel:
        excel = RelatorioExcel(os.path.join(destino, f"{cfg.sigla}_inconsistencias.xlsx"),
                               cfg, motor, colunas,
                               pintar_linha_inteira=pintar_linha_inteira,
                               max_linhas=max_linhas_excel, colunas_saida=colunas_saida)

    caminho_ocor = os.path.join(destino, f"{cfg.sigla}_ocorrencias.csv")
    fh_ocor = None
    if gerar_csv:
        fh_ocor = open(caminho_ocor, "w", encoding="utf-8-sig", newline="")
        fh_ocor.write("linha_csv;chave;campo;rotulo;tipo;tipo_rotulo;regra;valor;descricao\n")

    # ------------------------------------------------------------------ #
    # 2ª passagem: crítica registro a registro
    # ------------------------------------------------------------------ #
    with LeitorCSV(arquivo, encoding=cfg.encoding, separador=cfg.separador,
                   mapa_colunas=cfg.mapa_colunas) as leitor:
        n = 0
        for n_linha, linha in leitor:
            n += 1
            if limite and n > limite:
                break
            ocorrencias, contexto = motor.avaliar(linha, duplicados)
            ag.adicionar(linha, ocorrencias, contexto)
            chave = motor.chave_registro(linha)
            chave_hash = cmp_mod._h(chave) if chave else cmp_mod._h(f"__linha__{n_linha}")
            gravador.escrever(chave_hash, ocorrencias)
            if comparador:
                comparador.observar(chave_hash, ocorrencias)
            if excel:
                excel.registrar(n_linha, linha, ocorrencias)
            if fh_ocor and ocorrencias:
                for oc in ocorrencias:
                    fh_ocor.write(";".join(_limpa(x) for x in [
                        n_linha, chave, oc.campo, cfg.rotulo(oc.campo), oc.tipo,
                        T.tipo(oc.tipo).rotulo, oc.regra, oc.valor, oc.descricao]) + "\n")
            if n % 200_000 == 0:
                _msg(f"  [2/2] {n:,} registros avaliados | "
                     f"{ag.n_ocorrencias:,} ocorrências".replace(",", "."), silencioso)

    gravador.fechar()
    if fh_ocor:
        fh_ocor.close()
    if comparador:
        comparador.finalizar()

    indicadores = ag.indicadores()
    escore = ag.escore_geral(indicadores)

    # ------------------------------------------------------------------ #
    # Produtos
    # ------------------------------------------------------------------ #
    meta = {
        "arquivo": os.path.basename(arquivo),
        "caminho": os.path.abspath(arquivo),
        "tamanho": tamanho_legivel(os.path.getsize(arquivo)),
        "encoding": leitor.encoding,
        "separador": repr(leitor.separador),
        "data_extracao": data_extracao.strftime("%d/%m/%Y"),
        "versao": VERSAO,
        "carimbo": carimbo,
    }

    # registra a execução antes dos produtos, para que o relatório já mostre a
    # série histórica incluindo o envio atual
    historico.registrar_execucao({
        "carimbo": carimbo,
        "data_processamento": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "arquivo": os.path.basename(arquivo),
        "data_extracao": data_extracao.isoformat(),
        "registros": ag.n_registros,
        "registros_com_inconsistencia": ag.n_registros_com_inconsistencia,
        "pct_registros_com_inconsistencia": round(
            100.0 * ag.n_registros_com_inconsistencia / max(ag.n_registros, 1), 2),
        "ocorrencias": ag.n_ocorrencias,
        "escore": escore,
        "ocorrencias_por_tipo": dict(ag.occ_por_tipo),
        "indicadores": {k: {"valor": v["valor"]} for k, v in indicadores.items()},
        "resolutividade": comparador.taxa_resolutividade if (comparador and comparador.disponivel) else None,
        "pasta_saida": os.path.abspath(destino),
    })
    historico.limpar_antigas(manter=12)

    if excel:
        excel.finalizar(ag, comparacao=comparador if (comparador and comparador.disponivel) else None,
                        meta=meta)
        _msg(f"  planilha ..... {excel.caminho} "
             f"({excel.linhas_escritas:,} linhas coloridas)".replace(",", "."), silencioso)

    if gerar_html:
        html = rel_mod.gerar_html(cfg, ag, indicadores, comparador=comparador, meta=meta,
                                  execucoes=historico.execucoes())
        caminho_html = os.path.join(destino, f"{cfg.sigla}_relatorio.html")
        with open(caminho_html, "w", encoding="utf-8") as fh:
            fh.write(html)
        _msg(f"  relatório .... {caminho_html}", silencioso)

    if gerar_csv:
        _escrever_csvs(destino, cfg, ag, indicadores, comparador)
        _msg(f"  tabelas ...... {destino} (CSV para tabela dinâmica)", silencioso)

    duracao = time.time() - t0
    _msg(f"  escore ....... {escore}% ({T.classificar(escore)[0]}) | "
         f"{ag.n_registros:,} registros | {ag.n_ocorrencias:,} ocorrências | "
         f"{duracao:,.1f}s".replace(",", "."), silencioso)

    return {
        "sistema": cfg.sigla,
        "config": cfg,
        "agregador": ag,
        "indicadores": indicadores,
        "escore": escore,
        "comparador": comparador,
        "destino": destino,
        "meta": meta,
        "duracao": duracao,
    }


def _carimbo_livre(pasta_saida, pasta_historico, sigla):
    """Carimbo de tempo ainda não usado — duas execuções no mesmo segundo não
    podem sobrescrever uma à outra nem anular a comparação entre envios."""
    base = carimbo_agora()
    carimbo, n = base, 1
    while (os.path.exists(os.path.join(pasta_saida, sigla.lower(), carimbo))
           or os.path.exists(os.path.join(pasta_historico, sigla.lower(),
                                          f"{carimbo}_ocorrencias.csv.gz"))):
        n += 1
        carimbo = f"{base}_{n}"
    return carimbo


def _limpa(valor):
    txt = str(valor if valor is not None else "")
    return txt.replace(";", ",").replace("\n", " ").replace("\r", " ")


def _escrever_csvs(destino, cfg, ag, indicadores, comparador):
    escrever_csv(
        os.path.join(destino, f"{cfg.sigla}_indicadores.csv"),
        ["atributo", "valor_pct", "classificacao", "numerador", "denominador", "formula", "observacao"],
        [[d["atributo"], d["valor"], d["classificacao"], d["numerador"], d["denominador"],
          d["formula"], d["observacao"]] for d in indicadores.values()])

    escrever_csv(
        os.path.join(destino, f"{cfg.sigla}_resumo_campos.csv"),
        ["campo", "rotulo", "bloco", "essencial", "preenchidos", "pct_preenchimento", "vazios",
         "ignorados", "pct_ignorado", "invalidos", "incoerencias", "duplicidades",
         "fora_do_prazo", "total_ocorrencias", "valores_invalidos_frequentes"],
        [[l["campo"], l["rotulo"], l["bloco"], "SIM" if l["essencial"] else "NAO",
          l["preenchidos"], l["pct_preenchimento"], l["vazios"], l["ignorados"],
          l["pct_ignorado"], l["invalidos"], l["incoerencias"], l["duplicidades"],
          l["fora_prazo"], l["total_ocorrencias"],
          "; ".join(f"{v} ({n})" for v, n in l["valores_invalidos_frequentes"])]
         for l in ag.resumo_campos()])

    escrever_csv(
        os.path.join(destino, f"{cfg.sigla}_resumo_regras.csv"),
        ["regra", "tipo", "ocorrencias", "pct_registros", "descricao"],
        [[r["regra"], r["tipo"], r["ocorrencias"], r["pct_registros"], r["descricao"]]
         for r in ag.resumo_regras()])

    escrever_csv(
        os.path.join(destino, f"{cfg.sigla}_serie_mensal.csv"),
        ["periodo", "registros", "ocorrencias", "registros_com_inconsistencia", "pct_com_inconsistencia"],
        [[s["periodo"], s["registros"], s["ocorrencias"], s["com_inc"], s["pct_com_inc"]]
         for s in ag.resumo_serie()])

    linhas_estrato = []
    for campo in ag.estratos:
        for e_ in ag.resumo_estratos(campo, top=1000):
            linhas_estrato.append([campo, cfg.rotulo(campo), e_["valor"], e_["registros"],
                                   e_["ocorrencias"], e_["com_inc"], e_["pct_com_inc"],
                                   e_["ocorrencias_por_registro"]])
    if linhas_estrato:
        escrever_csv(
            os.path.join(destino, f"{cfg.sigla}_estratos.csv"),
            ["campo", "rotulo", "valor", "registros", "ocorrencias",
             "registros_com_inconsistencia", "pct_com_inconsistencia", "ocorrencias_por_registro"],
            linhas_estrato)

    escrever_csv(
        os.path.join(destino, f"{cfg.sigla}_tempestividade.csv"),
        ["indicador", "prazo_dias", "registros", "no_prazo", "pct_no_prazo", "media",
         "p25", "mediana", "p75", "p90", "maximo", "negativos"],
        [[t["rotulo"], t["prazo_dias"], t["registros"], t["no_prazo"], t["pct_no_prazo"],
          t["media"], t["p25"], t["mediana"], t["p75"], t["p90"], t["maximo"], t["negativos"]]
         for t in ag.resumo_tempestividade()])

    if comparador and comparador.disponivel:
        escrever_csv(
            os.path.join(destino, f"{cfg.sigla}_comparativo_envios.csv"),
            ["tipo", "existiam_antes", "corrigidas", "pct_resolvido", "persistentes",
             "novas", "sem_registro"],
            [[T.tipo(l["tipo"]).rotulo, l["anteriores"], l["corrigidas"], l["pct_resolvido"],
              l["persistentes"], l["novas"], l["sem_registro"]] for l in comparador.por_tipo()])
