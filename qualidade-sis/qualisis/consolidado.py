"""Painel consolidado: compara todos os sistemas do setor em uma página.

Lê o histórico de execuções (``historico/<sigla>/execucoes.json``) e monta o
quadro comparativo que a Subcoordenadoria usa na reunião de monitoramento:
onde cada sistema está, quem melhorou, quem piorou e em qual atributo.
"""

from __future__ import annotations

import os
from datetime import datetime

from . import tipos as T
from .comparacao import Historico
from .relatorio import (CSS, SERIES, barras_horizontais, e, _n, _pc, legenda_tipos,
                        linha_multipla, tabela)


def coletar(pasta_historico="historico", siglas=None):
    """Devolve {sigla: [execuções ordenadas]} para os sistemas com histórico."""
    if not os.path.isdir(pasta_historico):
        return {}
    dados = {}
    for nome in sorted(os.listdir(pasta_historico)):
        caminho = os.path.join(pasta_historico, nome)
        if not os.path.isdir(caminho):
            continue
        if siglas and nome.lower() not in {s.lower() for s in siglas}:
            continue
        execs = Historico(pasta_historico, nome).execucoes()
        if execs:
            dados[nome.upper()] = execs
    return dados


def gerar_consolidado(pasta_historico="historico", caminho_saida="painel_consolidado.html",
                      siglas=None, orgao="Subcoordenadoria de Informação em Saúde — SMS Salvador"):
    dados = coletar(pasta_historico, siglas)
    if not dados:
        raise RuntimeError("Nenhum histórico encontrado — execute a análise de ao menos "
                           "um sistema antes de gerar o painel consolidado.")

    ultimas = {sigla: execs[-1] for sigla, execs in dados.items()}
    p = []

    p.append(f"""<header class="topo">
<div class="eyebrow">{e(orgao)}</div>
<h1>Painel consolidado da qualidade dos sistemas de informação</h1>
<p class="sub">Comparação entre {len(dados)} sistema(s) — última avaliação de cada um.
Gerado em {e(datetime.now().strftime('%d/%m/%Y às %H:%M'))}.</p>
</header>""")

    # -- quadro geral ---------------------------------------------------- #
    linhas = []
    for sigla, ex in sorted(ultimas.items(), key=lambda kv: -(kv[1].get("escore") or 0)):
        faixa, cor = T.classificar(ex.get("escore"))
        linhas.append([
            sigla,
            ex.get("data_processamento", ""),
            _n(ex.get("registros")),
            _n(ex.get("registros_com_inconsistencia")),
            _pc(ex.get("pct_registros_com_inconsistencia")),
            _n(ex.get("ocorrencias")),
            (f'<span class="chip" style="border-color:{cor};color:{cor}">'
             f'{_pc(ex.get("escore"))} · {e(faixa)}</span>', ""),
            _pc(ex.get("resolutividade")),
        ])
    itens = [(sigla, ex.get("escore"), SERIES[i % len(SERIES)],
              f"{sigla}: escore {_pc(ex.get('escore'))}")
             for i, (sigla, ex) in enumerate(sorted(ultimas.items()))]
    p.append(f"""<h2>1. Situação atual por sistema</h2>
<section>
{barras_horizontais(itens, sufixo="%", casas=1)}
{tabela(["Sistema", "Última avaliação", "Registros", "Com inconsistência",
         "% com inconsistência", "Ocorrências", "Escore global", "Resolutividade"],
        linhas, classes_num=(2, 3, 4, 5, 7))}
</section>""")

    # -- matriz atributo x sistema ---------------------------------------- #
    nomes_sistemas = sorted(ultimas)
    cabecalho = ["Atributo"] + nomes_sistemas
    linhas_matriz = []
    for atributo in T.ATRIBUTOS_AUTOMATICOS:
        linha = [atributo.nome]
        tem = False
        for sigla in nomes_sistemas:
            ind = (ultimas[sigla].get("indicadores") or {}).get(atributo.nome) or {}
            valor = ind.get("valor") if isinstance(ind, dict) else ind
            if valor is None:
                linha.append(("—", "num"))
                continue
            tem = True
            _f, cor = T.classificar(valor)
            linha.append((f'<span style="display:inline-block;padding:1px 7px;border-radius:5px;'
                          f'background:{cor}22;color:{cor};font-weight:600;'
                          f'font-variant-numeric:tabular-nums">{_pc(valor)}</span>', "num"))
        if tem:
            linhas_matriz.append(linha)
    p.append(f"""<h2>2. Matriz comparativa por atributo</h2>
<section>
<p class="nota">Cada célula traz o indicador do atributo no sistema, com a cor da faixa de
classificação (verde ≥ 90%, amarelo 80–89,9%, laranja/vermelho abaixo disso). Leitura por
linha: onde o setor está mais frágil em todos os sistemas. Leitura por coluna: o perfil de
cada sistema.</p>
{tabela(cabecalho, linhas_matriz, classes_num=tuple(range(1, len(nomes_sistemas) + 1)))}
</section>""")

    # -- composição das inconsistências ------------------------------------ #
    linhas_tipo = []
    for codigo in T.ORDEM_TIPOS:
        linha = [(f'<span class="sw" style="background:var(--c-{codigo})"></span> '
                  f'{e(T.TIPOS[codigo].rotulo)}', "")]
        total_geral = 0
        for sigla in nomes_sistemas:
            n = (ultimas[sigla].get("ocorrencias_por_tipo") or {}).get(codigo, 0)
            total_geral += n
            pct = 100.0 * n / max(ultimas[sigla].get("ocorrencias") or 1, 1)
            linha.append((f'{_n(n)} <span style="color:var(--muted)">({_pc(pct)})</span>', "num"))
        if total_geral:
            linhas_tipo.append(linha)
    p.append(f"""<h2>3. Composição das inconsistências</h2>
<section>
{legenda_tipos()}
{tabela(["Tipo de inconsistência"] + nomes_sistemas, linhas_tipo,
        classes_num=tuple(range(1, len(nomes_sistemas) + 1)))}
</section>""")

    # -- evolução ---------------------------------------------------------- #
    # Eixo do tempo: uma coluna por mês de avaliação (cadência usual do setor).
    # Se todas as avaliações caírem no mesmo mês, o eixo passa a ser a ordem da
    # avaliação de cada sistema (1ª, 2ª, 3ª...), que é o que resta de comparável.
    meses = sorted({ex["carimbo"][:6] for execs in dados.values() for ex in execs})
    por_mes = len(meses) >= 2
    if por_mes:
        carimbos = meses
        rotulos = [f"{m[4:6]}/{m[:4]}" for m in meses]
    else:
        maximo = max(len(execs) for execs in dados.values())
        carimbos = list(range(maximo))
        rotulos = [f"{i + 1}ª aval." for i in range(maximo)]
    series_escore, series_inc = [], []
    for i, sigla in enumerate(nomes_sistemas):
        execs = sorted(dados[sigla], key=lambda ex: ex["carimbo"])
        if por_mes:  # última execução de cada mês
            mapa = {ex["carimbo"][:6]: ex for ex in execs}
            alinhado = [mapa.get(c) for c in carimbos]
        else:
            alinhado = [execs[j] if j < len(execs) else None for j in carimbos]
        cor = SERIES[i % len(SERIES)]
        series_escore.append((sigla, [(ex or {}).get("escore") for ex in alinhado], cor))
        series_inc.append((sigla, [(ex or {}).get("pct_registros_com_inconsistencia")
                                   for ex in alinhado], cor))
    if len(carimbos) >= 2:
        p.append(f"""<h2>4. Evolução entre avaliações</h2>
<section>
<h3>Escore global por sistema</h3>
{linha_multipla(series_escore, rotulos, sufixo="%")}
<h3>% de registros com inconsistência</h3>
{linha_multipla(series_inc, rotulos, sufixo="%")}
</section>""")

    # -- resolutividade ------------------------------------------------------ #
    itens_res = [(sigla, ultimas[sigla].get("resolutividade"), SERIES[i % len(SERIES)],
                  f"{sigla}: {_pc(ultimas[sigla].get('resolutividade'))} das pendências "
                  f"anteriores resolvidas")
                 for i, sigla in enumerate(nomes_sistemas)
                 if ultimas[sigla].get("resolutividade") is not None]
    if itens_res:
        p.append(f"""<h2>5. Resolutividade desde o envio anterior</h2>
<section>{barras_horizontais(itens_res, sufixo="%", casas=1)}
<p class="nota">Percentual das inconsistências apontadas no envio anterior que já não
aparecem no envio atual, considerando apenas registros que continuam na base.</p>
</section>""")

    p.append(f"""<h2>Leitura sugerida</h2>
<section><ul class="acoes">{_leitura(ultimas)}</ul></section>
<footer>QualiSIS — painel consolidado. {e(orgao)}.
Fonte: histórico de execuções em <code>{e(os.path.abspath(pasta_historico))}</code>.</footer>""")

    html = f"""<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Painel consolidado — qualidade dos sistemas</title>
<style>{CSS}</style></head>
<body><div class="wrap">{"".join(p)}</div></body></html>"""

    os.makedirs(os.path.dirname(os.path.abspath(caminho_saida)), exist_ok=True)
    with open(caminho_saida, "w", encoding="utf-8") as fh:
        fh.write(html)
    return caminho_saida


def _leitura(ultimas):
    itens = []
    com_escore = {s: ex for s, ex in ultimas.items() if ex.get("escore") is not None}
    if com_escore:
        pior = min(com_escore.items(), key=lambda kv: kv[1]["escore"])
        melhor = max(com_escore.items(), key=lambda kv: kv[1]["escore"])
        itens.append(f"Maior escore: <strong>{e(melhor[0])}</strong> "
                     f"({_pc(melhor[1]['escore'])}). Menor escore: "
                     f"<strong>{e(pior[0])}</strong> ({_pc(pior[1]['escore'])}) — "
                     "concentrar esforço de qualificação neste sistema no próximo trimestre.")
    for sigla, ex in sorted(ultimas.items()):
        res = ex.get("resolutividade")
        if res is not None and res < 50:
            itens.append(f"<strong>{e(sigla)}</strong>: resolutividade de {_pc(res)} — "
                         "as devolutivas não estão se convertendo em correção; rever fluxo "
                         "com as unidades notificadoras.")
    itens.append("Repetir o processamento a cada novo envio e arquivar o relatório de cada "
                 "sistema junto ao processo de monitoramento do setor.")
    return "".join(f"<li>{i}</li>" for i in itens)
