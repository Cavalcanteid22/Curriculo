"""Relatório HTML: análise descritiva e comparativa da qualidade da base.

Um arquivo único, sem internet e sem dependências — abre em qualquer navegador
da rede da Secretaria, imprime em A4 e pode ser anexado a processo. Segue a
identidade visual clara/escura e usa gráficos em SVG desenhados na própria
página.
"""

from __future__ import annotations

import html
from datetime import datetime

from . import tipos as T

# Passo escuro de cada cor de tipo (mesmas famílias, ajustadas ao fundo escuro)
CORES_ESCURAS = {
    T.DUPLICIDADE: "#e66767",
    T.EM_BRANCO: "#c98500",
    T.IGNORADO: "#d95926",
    T.CODIGO_INVALIDO: "#9085e9",
    T.DATA_INVALIDA: "#3987e5",
    T.INCOERENCIA: "#199e70",
    T.FORMATO_INVALIDO: "#d55181",
    T.FORA_DE_FAIXA: "#008300",
    T.FORA_DO_PRAZO: "#898781",
}

CSS = """
*, *::before, *::after { box-sizing: border-box; }
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --surface-2: #f2f1ed;
  --text: #0b0b0b; --text-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --baseline: #c3c2b7; --borda: rgba(11,11,11,0.10);
  --bom: #0ca30c; --atencao: #fab219; --serio: #ec835a; --critico: #d03b3b;
  --acento: #2a78d6;
  --c-duplicidade: #e34948; --c-em_branco: #eda100; --c-ignorado: #eb6834;
  --c-codigo_invalido: #4a3aa7; --c-data_invalida: #2a78d6; --c-incoerencia: #1baf7a;
  --c-formato_invalido: #e87ba4; --c-fora_de_faixa: #008300; --c-fora_do_prazo: #898781;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --surface-2: #232322;
    --text: #ffffff; --text-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --baseline: #383835; --borda: rgba(255,255,255,0.10);
    --acento: #3987e5;
    --c-duplicidade: #e66767; --c-em_branco: #c98500; --c-ignorado: #d95926;
    --c-codigo_invalido: #9085e9; --c-data_invalida: #3987e5; --c-incoerencia: #199e70;
    --c-formato_invalido: #d55181; --c-fora_de_faixa: #008300; --c-fora_do_prazo: #898781;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --surface-2: #232322;
  --text: #ffffff; --text-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --baseline: #383835; --borda: rgba(255,255,255,0.10);
  --acento: #3987e5;
  --c-duplicidade: #e66767; --c-em_branco: #c98500; --c-ignorado: #d95926;
  --c-codigo_invalido: #9085e9; --c-data_invalida: #3987e5; --c-incoerencia: #199e70;
  --c-formato_invalido: #d55181; --c-fora_de_faixa: #008300; --c-fora_do_prazo: #898781;
}
body {
  margin: 0; background: var(--page); color: var(--text);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 15px; line-height: 1.55;
}
.wrap { max-width: 1180px; margin: 0 auto; padding: 32px 20px 80px; }
header.topo { border-bottom: 2px solid var(--borda); padding-bottom: 18px; margin-bottom: 28px; }
.eyebrow { color: var(--muted); font-size: 12px; letter-spacing: .09em; text-transform: uppercase; }
h1 { font-size: 27px; margin: 6px 0 4px; line-height: 1.2; }
h2 { font-size: 19px; margin: 44px 0 6px; }
h3 { font-size: 15px; margin: 24px 0 6px; color: var(--text-2); }
p.sub { color: var(--text-2); margin: 2px 0; font-size: 14px; }
section { background: var(--surface); border: 1px solid var(--borda); border-radius: 12px;
          padding: 20px 22px; margin-top: 16px; }
.grid { display: grid; gap: 14px; }
.grid.k4 { grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }
.grid.k2 { grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); }
.tile { background: var(--surface-2); border: 1px solid var(--borda); border-radius: 10px;
        padding: 14px 16px; }
.tile .rot { color: var(--text-2); font-size: 12.5px; text-transform: uppercase;
             letter-spacing: .05em; }
.tile .val { font-size: 30px; font-weight: 650; margin-top: 4px; }
.tile .obs { color: var(--muted); font-size: 12.5px; }
.hero { display: flex; flex-wrap: wrap; align-items: baseline; gap: 14px; }
.hero .num { font-size: 60px; font-weight: 700; line-height: 1; }
.chip { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12.5px;
        font-weight: 600; border: 1px solid var(--borda); }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; margin-top: 10px; }
th, td { text-align: left; padding: 7px 9px; border-bottom: 1px solid var(--grid);
         vertical-align: top; }
th { color: var(--text-2); font-weight: 600; font-size: 12.5px; text-transform: uppercase;
     letter-spacing: .04em; position: sticky; top: 0; background: var(--surface); }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
tbody tr:hover { background: var(--surface-2); }
.rolagem { overflow-x: auto; }
.legenda { display: flex; flex-wrap: wrap; gap: 8px 18px; margin: 10px 0 4px;
           font-size: 13px; color: var(--text-2); }
.legenda span.item { display: inline-flex; align-items: center; gap: 6px; }
.sw { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }
.barra-fundo { background: var(--surface-2); border-radius: 4px; height: 9px;
               min-width: 84px; flex: 1 1 84px; overflow: hidden; }
.barra { height: 9px; border-radius: 4px; }
.nota { color: var(--text-2); font-size: 13px; }
.aviso { border-left: 3px solid var(--atencao); padding-left: 12px; margin: 10px 0; }
ul.acoes li { margin-bottom: 7px; }
svg { max-width: 100%; height: auto; display: block; }
footer { margin-top: 44px; color: var(--muted); font-size: 12.5px;
         border-top: 1px solid var(--borda); padding-top: 14px; }
code { background: var(--surface-2); padding: 1px 5px; border-radius: 4px; font-size: 12.5px; }
@media print {
  body { background: #fff; font-size: 11.5px; }
  section { break-inside: avoid; border-color: #ccc; }
  .wrap { max-width: none; padding: 0; }
  h2 { break-after: avoid; }
}
"""


def e(txt):
    return html.escape("" if txt is None else str(txt))


def _n(valor, casas=0):
    """Formata número no padrão brasileiro."""
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, float):
        txt = f"{valor:,.{casas}f}"
    else:
        txt = f"{valor:,}"
    return txt.replace(",", "@").replace(".", ",").replace("@", ".")


def _pc(valor):
    return "—" if valor is None else f"{_n(float(valor), 1)}%"


def _corta(texto, limite=32):
    """Encurta o rótulo do eixo — o texto completo continua no tooltip."""
    txt = str(texto)
    return txt if len(txt) <= limite else txt[: limite - 1] + "…"


GRAVIDADE_ROTULO = {"alta": "Alta", "media": "Média", "baixa": "Baixa"}


# --------------------------------------------------------------------------- #
# Componentes gráficos (SVG inline)
# --------------------------------------------------------------------------- #

def barras_horizontais(itens, largura=760, altura_barra=26, sufixo="", casas=0):
    """itens: [(rotulo, valor, cor_css, titulo_hover)] — rótulo direto em cada barra."""
    itens = [i for i in itens if i[1] is not None]
    if not itens:
        return "<p class='nota'>Sem dados para exibir.</p>"
    maximo = max(i[1] for i in itens) or 1
    esq = 240
    altura = len(itens) * altura_barra + 12
    partes = [f'<svg viewBox="0 0 {largura} {altura}" role="img" '
              f'aria-label="Gráfico de barras horizontais">']
    for idx, item in enumerate(itens):
        rotulo, valor, cor, titulo = (list(item) + [None] * 4)[:4]
        y = idx * altura_barra + 6
        comp = max(2, (largura - esq - 90) * valor / maximo)
        partes.append(
            f'<g><title>{e(titulo or f"{rotulo}: {_n(valor, casas)}{sufixo}")}</title>'
            f'<text x="{esq - 10}" y="{y + 13}" text-anchor="end" font-size="12.5" '
            f'fill="var(--text-2)">{e(_corta(rotulo))}</text>'
            f'<rect x="{esq}" y="{y + 3}" width="{comp:.1f}" height="14" rx="4" fill="{cor}"/>'
            f'<text x="{esq + comp + 8:.1f}" y="{y + 14}" font-size="12.5" '
            f'fill="var(--text-2)" font-variant-numeric="tabular-nums">'
            f'{_n(valor, casas)}{sufixo}</text></g>'
        )
    partes.append("</svg>")
    return "".join(partes)


def barras_empilhadas(linhas, cores, largura=760, altura_barra=24):
    """linhas: [(rotulo, {chave: valor}, total)] — segmentos com 2px de respiro."""
    if not linhas:
        return "<p class='nota'>Sem dados para exibir.</p>"
    maximo = max(l[2] for l in linhas) or 1
    esq, dir_ = 240, 80
    altura = len(linhas) * altura_barra + 12
    util = largura - esq - dir_
    partes = [f'<svg viewBox="0 0 {largura} {altura}" role="img" '
              f'aria-label="Barras empilhadas por tipo de inconsistência">']
    for idx, (rotulo, segmentos, total) in enumerate(linhas):
        y = idx * altura_barra + 6
        x = esq
        partes.append(f'<text x="{esq - 10}" y="{y + 13}" text-anchor="end" font-size="12.5" '
                      f'fill="var(--text-2)">{e(_corta(rotulo))}</text>')
        for chave, valor in segmentos.items():
            if not valor:
                continue
            comp = util * valor / maximo
            if comp < 0.6:
                continue
            partes.append(
                f'<g><title>{e(rotulo)} — {e(T.tipo(chave).rotulo)}: {_n(valor)}</title>'
                f'<rect x="{x:.1f}" y="{y + 3}" width="{max(comp - 2, 0.8):.1f}" height="14" '
                f'rx="3" fill="{cores.get(chave, "var(--muted)")}"/></g>')
            x += comp
        partes.append(f'<text x="{x + 8:.1f}" y="{y + 14}" font-size="12.5" '
                      f'fill="var(--text-2)" font-variant-numeric="tabular-nums">'
                      f'{_n(total)}</text>')
    partes.append("</svg>")
    return "".join(partes)


def linha_temporal(pontos, largura=760, altura=220, sufixo="", cor="var(--acento)", casas=1):
    """pontos: [(rotulo, valor)] — série única, com marcadores e rótulos seletivos."""
    pontos = [(r, v) for r, v in pontos if v is not None]
    if len(pontos) < 2:
        return "<p class='nota'>Série insuficiente para o gráfico (mínimo de 2 períodos).</p>"
    esq, dir_, topo, base = 52, 18, 18, 34
    valores = [v for _, v in pontos]
    vmax, vmin = max(valores), min(valores)
    if vmax == vmin:
        vmax, vmin = vmax + 1, max(vmin - 1, 0)
    espaco_x = (largura - esq - dir_) / (len(pontos) - 1)
    altura_util = altura - topo - base

    def px(i):
        return esq + i * espaco_x

    def py(v):
        return topo + altura_util * (1 - (v - vmin) / (vmax - vmin))

    partes = [f'<svg viewBox="0 0 {largura} {altura}" role="img" aria-label="Série temporal">']
    for f in range(5):  # grade horizontal recuada
        v = vmin + (vmax - vmin) * f / 4
        y = py(v)
        partes.append(f'<line x1="{esq}" y1="{y:.1f}" x2="{largura - dir_}" y2="{y:.1f}" '
                      f'stroke="var(--grid)" stroke-width="1"/>')
        partes.append(f'<text x="{esq - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" '
                      f'fill="var(--muted)" font-variant-numeric="tabular-nums">'
                      f'{_n(round(v, casas), casas)}</text>')
    d = " ".join(f"{'M' if i == 0 else 'L'}{px(i):.1f},{py(v):.1f}"
                 for i, (_, v) in enumerate(pontos))
    partes.append(f'<path d="{d}" fill="none" stroke="{cor}" stroke-width="2" '
                  f'stroke-linejoin="round"/>')
    passo = max(1, len(pontos) // 12)
    for i, (rot, v) in enumerate(pontos):
        partes.append(f'<g><title>{e(rot)}: {_n(v, casas)}{sufixo}</title>'
                      f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="4" fill="{cor}" '
                      f'stroke="var(--surface)" stroke-width="2"/></g>')
        if i % passo == 0 or i == len(pontos) - 1:
            partes.append(f'<text x="{px(i):.1f}" y="{altura - 12}" text-anchor="middle" '
                          f'font-size="10.5" fill="var(--muted)">{e(rot)}</text>')
    ultimo = pontos[-1]
    partes.append(f'<text x="{px(len(pontos) - 1):.1f}" y="{py(ultimo[1]) - 10:.1f}" '
                  f'text-anchor="end" font-size="12" fill="var(--text-2)" font-weight="600">'
                  f'{_n(ultimo[1], casas)}{sufixo}</text>')
    partes.append("</svg>")
    return "".join(partes)


SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4",
          "#008300", "#4a3aa7", "#e34948"]


def linha_multipla(series, rotulos_x, largura=760, altura=250, sufixo="", casas=1):
    """series: [(nome, [valores alinhados a rotulos_x], cor)] — com legenda e rótulo final."""
    validos = [(n, v, c) for n, v, c in series if any(x is not None for x in v)]
    if not validos or len(rotulos_x) < 2:
        return "<p class='nota'>Série insuficiente para o gráfico.</p>"
    todos = [x for _, v, _ in validos for x in v if x is not None]
    vmax, vmin = max(todos), min(todos)
    if vmax == vmin:
        vmax, vmin = vmax + 1, max(vmin - 1, 0)
    esq, dir_, topo, base = 52, 96, 16, 34
    espaco = (largura - esq - dir_) / (len(rotulos_x) - 1)
    altura_util = altura - topo - base
    partes = [f'<svg viewBox="0 0 {largura} {altura}" role="img" '
              f'aria-label="Comparação entre sistemas ao longo do tempo">']
    for f in range(5):
        v = vmin + (vmax - vmin) * f / 4
        y = topo + altura_util * (1 - (v - vmin) / (vmax - vmin))
        partes.append(f'<line x1="{esq}" y1="{y:.1f}" x2="{largura - dir_}" y2="{y:.1f}" '
                      f'stroke="var(--grid)" stroke-width="1"/>'
                      f'<text x="{esq - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" '
                      f'fill="var(--muted)">{_n(round(v, casas), casas)}</text>')
    for nome, valores, cor in validos:
        pontos = [(esq + i * espaco, topo + altura_util * (1 - (v - vmin) / (vmax - vmin)))
                  for i, v in enumerate(valores) if v is not None]
        if len(pontos) >= 2:
            d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}"
                         for i, (x, y) in enumerate(pontos))
            partes.append(f'<path d="{d}" fill="none" stroke="{cor}" stroke-width="2" '
                          f'stroke-linejoin="round"/>')
        for (x, y), v in zip(pontos, [v for v in valores if v is not None]):
            partes.append(f'<g><title>{e(nome)}: {_n(v, casas)}{sufixo}</title>'
                          f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{cor}" '
                          f'stroke="var(--surface)" stroke-width="2"/></g>')
        if pontos:
            x, y = pontos[-1]
            partes.append(f'<text x="{x + 8:.1f}" y="{y + 4:.1f}" font-size="11.5" '
                          f'fill="{cor}" font-weight="600">{e(nome)}</text>')
    passo = max(1, len(rotulos_x) // 10)
    for i, rot in enumerate(rotulos_x):
        if i % passo == 0 or i == len(rotulos_x) - 1:
            partes.append(f'<text x="{esq + i * espaco:.1f}" y="{altura - 12}" '
                          f'text-anchor="middle" font-size="10.5" fill="var(--muted)">'
                          f'{e(rot)}</text>')
    partes.append("</svg>")
    return "".join(partes)


def barra_inline(valor, cor):
    v = 0 if valor is None else max(0.0, min(100.0, float(valor)))
    return (f'<div class="barra-fundo"><div class="barra" style="width:{v:.1f}%;'
            f'background:{cor}"></div></div>')


def tabela(cabecalho, linhas, classes_num=()):
    ths = "".join(f'<th class="{"num" if i in classes_num else ""}">{e(c)}</th>'
                  for i, c in enumerate(cabecalho))
    corpo = []
    for linha in linhas:
        tds = []
        for i, celula in enumerate(linha):
            classe = "num" if i in classes_num else ""
            if isinstance(celula, tuple):  # (html_bruto, classe)
                conteudo, extra = celula
                tds.append(f'<td class="{classe} {extra}">{conteudo}</td>')
            else:
                tds.append(f'<td class="{classe}">{e(celula)}</td>')
        corpo.append("<tr>" + "".join(tds) + "</tr>")
    return (f'<div class="rolagem"><table><thead><tr>{ths}</tr></thead>'
            f'<tbody>{"".join(corpo)}</tbody></table></div>')


def legenda_tipos(codigos=None):
    codigos = codigos or T.ORDEM_TIPOS
    itens = "".join(
        f'<span class="item"><span class="sw" style="background:var(--c-{c})"></span>'
        f'{e(T.TIPOS[c].rotulo)}</span>' for c in codigos
    )
    return f'<div class="legenda">{itens}</div>'


# --------------------------------------------------------------------------- #
# Relatório
# --------------------------------------------------------------------------- #

def gerar_html(cfg, ag, indicadores, comparador=None, meta=None, execucoes=None):
    meta = meta or {}
    escore = ag.escore_geral(indicadores)
    faixa, cor_faixa = T.classificar(escore)
    cores_css = {c: f"var(--c-{c})" for c in T.ORDEM_TIPOS}
    p = []

    # -- cabeçalho ---------------------------------------------------------- #
    p.append(f"""<header class="topo">
<div class="eyebrow">{e(cfg.orgao)}</div>
<h1>Avaliação da qualidade da informação — {e(cfg.sigla)}</h1>
<p class="sub">{e(cfg.nome)}</p>
<p class="sub">Base analisada: <code>{e(meta.get('arquivo', ''))}</code>
 &nbsp;|&nbsp; Extração: <strong>{e(meta.get('data_extracao', ''))}</strong>
 &nbsp;|&nbsp; Processado em {e(datetime.now().strftime('%d/%m/%Y às %H:%M'))}</p>
<p class="sub">Período dos eventos na base:
 <strong>{e(ag.data_min_evento.strftime('%d/%m/%Y') if ag.data_min_evento else '—')}</strong>
 a <strong>{e(ag.data_max_evento.strftime('%d/%m/%Y') if ag.data_max_evento else '—')}</strong></p>
</header>""")

    # -- resumo executivo ---------------------------------------------------- #
    pct_reg_inc = 100.0 * ag.n_registros_com_inconsistencia / max(ag.n_registros, 1)
    tiles = [
        ("Registros analisados", _n(ag.n_registros), "linhas da base acumulada"),
        ("Registros com inconsistência", _n(ag.n_registros_com_inconsistencia),
         f"{_pc(pct_reg_inc)} do total"),
        ("Ocorrências detectadas", _n(ag.n_ocorrencias),
         f"{_n(ag.n_ocorrencias / max(ag.n_registros, 1), 2)} por registro"),
        ("Registros completos", _n(ag.n_registros_completos),
         "todos os campos essenciais preenchidos"),
    ]
    if comparador and comparador.disponivel:
        tiles.append(("Resolutividade desde o último envio",
                      _pc(comparador.taxa_resolutividade),
                      f"{_n(comparador.total_corrigidas)} corrigidas de "
                      f"{_n(comparador.total_corrigidas + comparador.total_persistentes)}"))
    tiles_html = "".join(
        f'<div class="tile"><div class="rot">{e(r)}</div><div class="val">{v}</div>'
        f'<div class="obs">{e(o)}</div></div>' for r, v, o in tiles)
    p.append(f"""<section>
<div class="hero"><div class="num" style="color:{cor_faixa}">{_pc(escore)}</div>
<div><span class="chip" style="border-color:{cor_faixa};color:{cor_faixa}">{e(faixa)}</span>
<p class="sub" style="margin-top:6px">Escore global ponderado dos atributos mensuráveis
 na base. Média ponderada dos indicadores da seção seguinte.</p></div></div>
<div class="grid k4" style="margin-top:18px">{tiles_html}</div>
</section>""")

    # -- indicadores por atributo -------------------------------------------- #
    linhas = []
    for atributo in T.ATRIBUTOS_AUTOMATICOS:
        d = indicadores.get(atributo.nome)
        if not d:
            continue
        _faixa, cor = T.classificar(d["valor"])
        linhas.append([
            atributo.nome,
            (f'<div style="display:flex;align-items:center;gap:9px">'
             f'<span style="min-width:56px;text-align:right;font-variant-numeric:tabular-nums">'
             f'{_pc(d["valor"])}</span>{barra_inline(d["valor"], cor)}</div>', ""),
            (f'<span class="chip" style="border-color:{cor};color:{cor}">'
             f'{e(d["classificacao"])}</span>' if d["valor"] is not None else "—", ""),
            _n(d["numerador"]), _n(d["denominador"]),
            d["formula"] + ((" — " + d["observacao"]) if d["observacao"] else ""),
        ])
    p.append(f"""<h2>1. Indicadores por atributo de qualidade</h2>
<section>
<p class="nota">Atributos mensuráveis diretamente na base. Os demais atributos
(clareza, acessibilidade, segurança, utilidade, etc.) são avaliados pelo
instrumento estruturado gerado pelo programa — ver a planilha
<code>instrumento_qualitativo</code>.</p>
{tabela(["Atributo", "Indicador", "Classificação", "Numerador", "Denominador",
         "Como é calculado"], linhas, classes_num=(3, 4))}
</section>""")

    # -- tipos de inconsistência --------------------------------------------- #
    itens = []
    linhas_tipo = []
    for codigo in T.ORDEM_TIPOS:
        n = ag.occ_por_tipo.get(codigo, 0)
        if not n:
            continue
        info = T.TIPOS[codigo]
        regs = ag.reg_por_tipo.get(codigo, 0)
        itens.append((info.rotulo, n, cores_css[codigo],
                      f"{info.rotulo}: {_n(n)} ocorrências em {_n(regs)} registros"))
        linhas_tipo.append([
            (f'<span class="sw" style="background:var(--c-{codigo})"></span> '
             f'{e(info.rotulo)}', ""),
            _n(n), _pc(100 * n / max(ag.n_ocorrencias, 1)), _n(regs),
            _pc(100 * regs / max(ag.n_registros, 1)),
            GRAVIDADE_ROTULO.get(info.gravidade, info.gravidade), ", ".join(info.atributos),
        ])
    p.append(f"""<h2>2. Inconsistências por tipo</h2>
<section>
{legenda_tipos([c for c in T.ORDEM_TIPOS if ag.occ_por_tipo.get(c)])}
{barras_horizontais(itens)}
{tabela(["Tipo (cor na planilha)", "Ocorrências", "% das ocorrências",
         "Registros atingidos", "% dos registros", "Gravidade", "Atributos impactados"],
        linhas_tipo, classes_num=(1, 2, 3, 4))}
</section>""")

    # -- campos críticos ------------------------------------------------------ #
    campos = [l for l in ag.resumo_campos() if l["total_ocorrencias"] > 0][:20]
    empilhado = []
    for l in campos:
        oc = ag.occ_por_campo.get(l["campo"], {})
        segmentos = {c: oc.get(c, 0) for c in T.ORDEM_TIPOS if oc.get(c)}
        empilhado.append((f'{l["rotulo"]} ({l["campo"]})', segmentos, l["total_ocorrencias"]))
    linhas_campo = []
    for l in ag.resumo_campos()[:40]:
        _f, cor = T.classificar(l["pct_preenchimento"])
        linhas_campo.append([
            l["campo"], l["rotulo"], "Sim" if l["essencial"] else "",
            (f'<div style="display:flex;align-items:center;gap:8px">'
             f'<span style="min-width:52px;text-align:right;font-variant-numeric:tabular-nums">'
             f'{_pc(l["pct_preenchimento"])}</span>{barra_inline(l["pct_preenchimento"], cor)}</div>', ""),
            _n(l["vazios"]), _n(l["ignorados"]), _n(l["invalidos"]), _n(l["incoerencias"]),
            _n(l["duplicidades"]), _n(l["fora_prazo"]),
            "; ".join(f"{v} ({n})" for v, n in l["valores_invalidos_frequentes"][:5]),
        ])
    p.append(f"""<h2>3. Campos com mais inconsistências</h2>
<section>
{legenda_tipos([c for c in T.ORDEM_TIPOS if ag.occ_por_tipo.get(c)])}
{barras_empilhadas(empilhado, cores_css)}
<h3>Detalhamento campo a campo (40 primeiros por volume de problemas)</h3>
{tabela(["Campo", "Rótulo", "Essencial", "Preenchimento", "Em branco", "Ignorados",
         "Inválidos", "Incoerências", "Duplicidades", "Fora do prazo",
         "Valores inválidos mais frequentes"], linhas_campo, classes_num=(4, 5, 6, 7, 8, 9))}
</section>""")

    # -- regras --------------------------------------------------------------- #
    linhas_regra = [[r["regra"], T.tipo(r["tipo"]).rotulo, _n(r["ocorrencias"]),
                     _pc(r["pct_registros"]), r["descricao"]]
                    for r in ag.resumo_regras()[:30]]
    if linhas_regra:
        p.append(f"""<h2>4. Críticas disparadas (ranking de regras)</h2>
<section>{tabela(["Regra", "Tipo", "Ocorrências", "% dos registros", "O que a regra verifica"],
                 linhas_regra, classes_num=(2, 3))}</section>""")

    # -- tempestividade -------------------------------------------------------- #
    temp = ag.resumo_tempestividade()
    if temp:
        itens_t = [(t["rotulo"], t["pct_no_prazo"], "var(--acento)",
                    f'{t["rotulo"]}: {_pc(t["pct_no_prazo"])} dentro de {t["prazo_dias"]} dias')
                   for t in temp]
        linhas_t = [[t["rotulo"], _n(t["prazo_dias"]), _n(t["registros"]), _n(t["no_prazo"]),
                     _pc(t["pct_no_prazo"]), _n(t["media"], 1), _n(t["p25"]), _n(t["mediana"]),
                     _n(t["p75"]), _n(t["p90"]), _n(t["maximo"]), _n(t["negativos"])]
                    for t in temp]
        faixas_html = []
        for t in temp:
            prazo = t["prazo_dias"] or 0
            baldes = {"No prazo": 0, "1 a 30 dias de atraso": 0, "31 a 60": 0,
                      "61 a 180": 0, "mais de 180": 0, "negativo (data incoerente)": 0}
            for dias, n in t["histograma"]:
                if dias < 0:
                    baldes["negativo (data incoerente)"] += n
                elif dias <= prazo:
                    baldes["No prazo"] += n
                elif dias <= prazo + 30:
                    baldes["1 a 30 dias de atraso"] += n
                elif dias <= prazo + 60:
                    baldes["31 a 60"] += n
                elif dias <= prazo + 180:
                    baldes["61 a 180"] += n
                else:
                    baldes["mais de 180"] += n
            itens_b = [(k, v, "var(--c-fora_do_prazo)" if k != "No prazo" else "var(--bom)",
                        f"{t['rotulo']} — {k}: {_n(v)} registros")
                       for k, v in baldes.items() if v]
            faixas_html.append(f"<h3>{e(t['rotulo'])} — distribuição do atraso</h3>"
                               + barras_horizontais(itens_b))
        p.append(f"""<h2>5. Tempestividade e oportunidade</h2>
<section>
{barras_horizontais(itens_t, sufixo="%", casas=1)}
{tabela(["Indicador de prazo", "Prazo (dias)", "Registros", "No prazo", "% no prazo",
         "Média", "P25", "Mediana", "P75", "P90", "Máximo", "Intervalos negativos"],
        linhas_t, classes_num=tuple(range(1, 12)))}
{"".join(faixas_html)}
</section>""")

    # -- série mensal ---------------------------------------------------------- #
    serie = ag.resumo_serie()
    if len(serie) >= 2:
        p.append(f"""<h2>6. Evolução mensal (por data do evento)</h2>
<section>
<h3>Registros por mês de ocorrência</h3>
{linha_temporal([(s["periodo"], s["registros"]) for s in serie], casas=0)}
<h3>Percentual de registros com pelo menos uma inconsistência</h3>
{linha_temporal([(s["periodo"], s["pct_com_inc"]) for s in serie],
                sufixo="%", cor="var(--c-duplicidade)")}
<p class="nota">Os dois gráficos são separados de propósito: volume e percentual
têm escalas diferentes e não devem dividir o mesmo eixo.</p>
</section>""")

    # -- estratos --------------------------------------------------------------- #
    blocos_estrato = []
    for campo in ag.estratos:
        dados = ag.resumo_estratos(campo, top=15)
        if not dados:
            continue
        itens_e = [(d["valor"], d["pct_com_inc"], "var(--c-ignorado)",
                    f'{d["valor"]}: {_pc(d["pct_com_inc"])} dos {_n(d["registros"])} registros')
                   for d in sorted(dados, key=lambda x: -(x["pct_com_inc"] or 0))]
        linhas_e = [[d["valor"], _n(d["registros"]), _n(d["ocorrencias"]), _n(d["com_inc"]),
                     _pc(d["pct_com_inc"]), _n(d["ocorrencias_por_registro"], 2)] for d in dados]
        blocos_estrato.append(
            f"<h3>{e(cfg.rotulo(campo))}</h3>"
            + barras_horizontais(itens_e, sufixo="%", casas=1)
            + tabela(["Valor", "Registros", "Ocorrências", "Com inconsistência",
                      "% com inconsistência", "Ocorrências por registro"],
                     linhas_e, classes_num=(1, 2, 3, 4, 5)))
    if blocos_estrato:
        p.append(f"""<h2>7. Onde estão os problemas (estratificação)</h2>
<section><p class="nota">Ordenado pelo percentual de registros com inconsistência —
é a lista de trabalho para a devolutiva às unidades notificadoras.</p>
{"".join(blocos_estrato)}</section>""")

    # -- comparativo entre envios ------------------------------------------------ #
    if comparador and comparador.disponivel:
        c = comparador
        tiles_c = "".join(
            f'<div class="tile"><div class="rot">{e(r)}</div><div class="val">{v}</div>'
            f'<div class="obs">{e(o)}</div></div>'
            for r, v, o in [
                ("Taxa de resolutividade", _pc(c.taxa_resolutividade),
                 "corrigidas ÷ (corrigidas + persistentes)"),
                ("Corrigidas", _n(c.total_corrigidas), "desde o envio anterior"),
                ("Persistentes", _n(c.total_persistentes), "apontadas e não resolvidas"),
                ("Novas", _n(c.total_novas), "surgiram neste envio"),
                ("Registros novos", _n(c.registros_novos), "entraram na base acumulada"),
                ("Registros que sumiram", _n(c.registros_ausentes),
                 "conferir expurgo/exclusão"),
            ])
        linhas_ct = [[
            (f'<span class="sw" style="background:var(--c-{l["tipo"]})"></span> '
             f'{e(T.tipo(l["tipo"]).rotulo)}', ""),
            _n(l["anteriores"]), _n(l["corrigidas"]), _pc(l["pct_resolvido"]),
            _n(l["persistentes"]), _n(l["novas"]), _n(l["sem_registro"])]
            for l in c.por_tipo()]
        linhas_cc = [[l["campo"], _n(l["anteriores"]), _n(l["corrigidas"]),
                      _pc(l["pct_resolvido"]), _n(l["persistentes"]), _n(l["novas"])]
                     for l in c.por_campo(20)]
        evolucao = c.evolucao_indicadores(indicadores)
        linhas_ev = []
        for ev in evolucao:
            if ev["anterior"] is None and ev["atual"] is None:
                continue
            delta = ev["delta"]
            cor_delta = "var(--bom)" if (delta or 0) > 0 else (
                "var(--critico)" if (delta or 0) < 0 else "var(--muted)")
            seta = "▲" if (delta or 0) > 0 else ("▼" if (delta or 0) < 0 else "•")
            linhas_ev.append([
                ev["atributo"], _pc(ev["anterior"]), _pc(ev["atual"]),
                (f'<span style="color:{cor_delta};font-variant-numeric:tabular-nums">'
                 f'{seta} {_n(abs(delta), 2) if delta is not None else "—"} p.p.</span>', "num"),
                ev["classificacao"],
            ])
        itens_res = [(T.tipo(l["tipo"]).rotulo, l["pct_resolvido"], cores_css[l["tipo"]],
                      f'{T.tipo(l["tipo"]).rotulo}: {_n(l["corrigidas"])} corrigidas de '
                      f'{_n(l["corrigidas"] + l["persistentes"])}')
                     for l in c.por_tipo() if l["pct_resolvido"] is not None]
        p.append(f"""<h2>8. Comparativo com o envio anterior (resolutividade)</h2>
<section>
<p class="nota">Referência: envio de
<strong>{e((c.anterior or {}).get('data_processamento', ''))}</strong>
(<code>{e((c.anterior or {}).get('arquivo', ''))}</code>). Como a base é acumulativa,
cada registro é acompanhado pela chave
<code>{e(' + '.join(cfg.chave_registro) or 'chave configurada')}</code>.</p>
<div class="grid k4">{tiles_c}</div>
<h3>Percentual resolvido por tipo de inconsistência</h3>
{barras_horizontais(itens_res, sufixo="%", casas=1)}
{tabela(["Tipo", "Existiam antes", "Corrigidas", "% resolvido", "Persistentes", "Novas",
         "Sem registro na base"], linhas_ct, classes_num=(1, 2, 3, 4, 5, 6))}
<h3>Campos com maior passivo</h3>
{tabela(["Campo", "Existiam antes", "Corrigidas", "% resolvido", "Persistentes", "Novas"],
        linhas_cc, classes_num=(1, 2, 3, 4, 5))}
<h3>Evolução dos indicadores (pontos percentuais)</h3>
{tabela(["Atributo", "Envio anterior", "Envio atual", "Variação", "Classificação atual"],
        linhas_ev, classes_num=(1, 2, 3))}
</section>""")

    # -- histórico -------------------------------------------------------------- #
    execucoes = execucoes or []
    if len(execucoes) >= 2:
        pontos = [(x["carimbo"][:8], x.get("escore")) for x in execucoes if x.get("escore")]
        pontos_inc = [(x["carimbo"][:8], x.get("pct_registros_com_inconsistencia"))
                      for x in execucoes if x.get("pct_registros_com_inconsistencia") is not None]
        p.append(f"""<h2>9. Série histórica das avaliações</h2>
<section>
<h3>Escore global ponderado por execução</h3>
{linha_temporal(pontos, sufixo="%")}
<h3>% de registros com inconsistência por execução</h3>
{linha_temporal(pontos_inc, sufixo="%", cor="var(--c-duplicidade)")}
</section>""")

    # -- plano de providências --------------------------------------------------- #
    p.append(f"""<h2>10. Providências sugeridas</h2>
<section><ul class="acoes">{_plano(cfg, ag, indicadores, comparador)}</ul></section>""")

    # -- nota metodológica -------------------------------------------------------- #
    cobertura = cfg.validar_contra_base(ag.motor.colunas) if ag.motor.colunas else \
        {"ausentes": [], "nao_previstas": []}
    p.append(f"""<h2>11. Nota metodológica</h2>
<section>
<p class="nota">Classificação dos indicadores: <strong>Excelente</strong> ≥ 95%;
<strong>Bom</strong> 90–94,9%; <strong>Regular</strong> 80–89,9%;
<strong>Ruim</strong> 50–79,9%; <strong>Muito ruim</strong> &lt; 50%.
O escore global é a média dos indicadores ponderada pelo peso de cada atributo.</p>
<p class="nota">Campos do dicionário ausentes na exportação:
<code>{e(', '.join(cobertura['ausentes']) or 'nenhum')}</code>.<br>
Colunas da base sem correspondência no dicionário:
<code>{e(', '.join(cobertura['nao_previstas']) or 'nenhuma')}</code>.</p>
<p class="nota">Duplicidade avaliada pelas chaves:
{e('; '.join(ch.get('nome', ', '.join(ch['campos'])) for ch in ag.motor.chaves_dup) or 'não configurada')}.
Registros sem chave preenchida ({_n(ag.chaves_vazias)}) não entram na comparação entre envios.</p>
<p class="nota">Cada percentual desta página tem numerador e denominador explicitados na
seção 1 e pode ser reproduzido a partir da planilha de inconsistências.</p>
</section>
<footer>
QualiSIS — avaliação da qualidade de sistemas de informação em saúde.
{e(cfg.orgao)}. Gerado em {e(datetime.now().strftime('%d/%m/%Y %H:%M'))}.
Arquivo de configuração: <code>{e(cfg.caminho or '')}</code>.
</footer>""")

    corpo = "".join(p)
    return f"""<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Qualidade {e(cfg.sigla)} — {e(meta.get('data_extracao', ''))}</title>
<style>{CSS}</style></head>
<body><div class="wrap">{corpo}</div></body></html>"""


def _plano(cfg, ag, indicadores, comparador):
    """Gera automaticamente a lista de providências a partir dos achados."""
    acoes = []
    campos = ag.resumo_campos()

    piores_branco = [c for c in campos if c["essencial"] and (c["pct_preenchimento"] or 100) < 90][:5]
    if piores_branco:
        acoes.append("Priorizar o preenchimento dos campos essenciais com maior lacuna: "
                     + ", ".join(f"<strong>{e(c['rotulo'])}</strong> "
                                 f"({_pc(c['pct_preenchimento'])} preenchido)"
                                 for c in piores_branco)
                     + " — devolutiva às unidades notificadoras e reforço no treinamento.")

    piores_ign = sorted([c for c in campos if (c["pct_ignorado"] or 0) > 10],
                        key=lambda c: -(c["pct_ignorado"] or 0))[:5]
    if piores_ign:
        acoes.append("Reduzir o uso do código 'ignorado' em "
                     + ", ".join(f"<strong>{e(c['rotulo'])}</strong> ({_pc(c['pct_ignorado'])})"
                                 for c in piores_ign)
                     + " — o campo consta preenchido, mas não gera informação utilizável.")

    dups = ag.reg_por_tipo.get(T.DUPLICIDADE, 0)
    if dups:
        acoes.append(f"Investigar <strong>{_n(dups)} registro(s)</strong> marcados como "
                     "duplicidade (aba <em>Inconsistências</em>, filtro pela cor vermelha) e "
                     "executar a rotina de exclusão/vinculação no sistema de origem.")

    for t in ag.resumo_tempestividade():
        if t["pct_no_prazo"] is not None and t["pct_no_prazo"] < 80:
            acoes.append(f"Melhorar a oportunidade de <strong>{e(t['rotulo'])}</strong>: "
                         f"apenas {_pc(t['pct_no_prazo'])} dentro do prazo de "
                         f"{t['prazo_dias']} dias (mediana observada: {_n(t['mediana'])} dias).")
        if t["negativos"]:
            acoes.append(f"Corrigir {_n(t['negativos'])} registro(s) com intervalo negativo em "
                         f"<strong>{e(t['rotulo'])}</strong> — indica erro de digitação de data.")

    for campo in ag.estratos:
        piores = [d for d in ag.resumo_estratos(campo, top=100) if d["registros"] >= 30]
        piores.sort(key=lambda d: -(d["pct_com_inc"] or 0))
        if piores and (piores[0]["pct_com_inc"] or 0) > 0:
            nomes = ", ".join(f"{e(d['valor'])} ({_pc(d['pct_com_inc'])})" for d in piores[:3])
            acoes.append(f"Pactuar plano de correção com os maiores focos em "
                         f"<strong>{e(cfg.rotulo(campo))}</strong>: {nomes}.")

    if comparador and comparador.disponivel:
        if (comparador.taxa_resolutividade or 0) < 50:
            acoes.append("A resolutividade desde o envio anterior está abaixo de 50%: "
                         "reavaliar o fluxo de devolutiva — as listas estão chegando a quem "
                         "pode corrigir, e há prazo pactuado para retorno?")
        if comparador.registros_ausentes:
            acoes.append(f"Conferir os {_n(comparador.registros_ausentes)} registro(s) presentes "
                         "no envio anterior e ausentes no atual (expurgo indevido, mudança de "
                         "chave ou exclusão).")
        if comparador.total_novas > comparador.total_corrigidas:
            acoes.append("Entraram mais inconsistências novas do que foram corrigidas no "
                         "período: atuar na origem (crítica no momento da digitação) e não "
                         "apenas na correção posterior.")

    fracos = sorted([d for d in indicadores.values() if d["valor"] is not None],
                    key=lambda d: d["valor"])[:3]
    if fracos:
        acoes.append("Atributos com pior desempenho nesta avaliação: "
                     + ", ".join(f"<strong>{e(d['atributo'])}</strong> ({_pc(d['valor'])})"
                                 for d in fracos)
                     + " — definir meta de melhoria para o próximo envio.")

    acoes.append("Registrar esta avaliação no histórico do setor e repetir o processamento "
                 "no próximo envio para medir a resolutividade.")
    return "".join(f"<li>{a}</li>" for a in acoes)
