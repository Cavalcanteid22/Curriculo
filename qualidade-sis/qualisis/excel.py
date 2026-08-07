"""Geração da planilha Excel com as linhas inconsistentes pintadas por cor.

A planilha é o produto de trabalho do dia a dia: o técnico abre, filtra pelo
tipo de inconsistência, vê a célula exatamente onde está o problema e devolve a
lista para a unidade notificadora corrigir.

Abas produzidas:
    Painel                -> indicadores por atributo de qualidade
    Inconsistências       -> registros com problema, célula a célula, coloridos
    Resumo por campo      -> completude, ignorados e erros de cada variável
    Resumo por regra      -> ranking das críticas disparadas
    Tempestividade        -> prazos, medianas e percentis
    Série mensal          -> evolução por mês de ocorrência do evento
    Estratos              -> distrito/unidade/agravo com mais problemas
    Comparativo de envios -> resolutividade desde o envio anterior
    Legenda               -> significado de cada cor
    Ficha técnica         -> parâmetros da execução (rastreabilidade)
"""

from __future__ import annotations

from datetime import datetime

from . import tipos as T
from .xlsxmin import LIMITE_LINHAS_EXCEL, LivroExcel

COLUNAS_META = ["_LINHA_CSV", "_CHAVE", "_QTD", "_GRAVIDADE", "_TIPOS", "_DETALHE"]
LARGURA_META = [11, 30, 7, 11, 34, 60]


class RelatorioExcel:
    def __init__(self, caminho, cfg, motor, colunas_base, pintar_linha_inteira=False,
                 max_linhas=None, colunas_saida=None):
        self.caminho = caminho
        self.cfg = cfg
        self.motor = motor
        self.colunas_base = list(colunas_base)
        self.colunas_saida = [c for c in (colunas_saida or self.colunas_base)
                              if c in self.colunas_base]
        self.pintar_linha_inteira = pintar_linha_inteira
        self.max_linhas = max_linhas
        self.livro = LivroExcel(caminho)
        for codigo in T.ORDEM_TIPOS:
            self.livro.registrar_cor(T.TIPOS[codigo].cor_celula, nome=codigo)
        for _limite, rotulo, cor in T.FAIXAS:
            self.livro.registrar_cor(_clarear(cor), nome=f"faixa_{rotulo}")
        self.livro.registrar_cor("F0EFEC", nome="zebra")
        self.livro.registrar_cor("D8F0D8", nome="ok")
        self._aba = None
        self._n_abas_inc = 0
        self.linhas_escritas = 0
        self.linhas_omitidas = 0

    # ------------------------------------------------------------------ #
    def _nova_aba_inconsistencias(self):
        if self._aba is not None:
            self._aba.fechar()
        self._n_abas_inc += 1
        nome = "Inconsistências" if self._n_abas_inc == 1 else f"Inconsistências ({self._n_abas_inc})"
        larguras = LARGURA_META + [16] * len(self.colunas_saida)
        self._aba = self.livro.aba(nome, larguras=larguras, congelar_linhas=1, congelar_colunas=2)
        self._aba._abrir()
        cabecalho = COLUNAS_META + [self.cfg.rotulo(c) if c in self.cfg.campos else c
                                    for c in self.colunas_saida]
        self._aba.linha(cabecalho, estilo_geral="cabecalho")

    def registrar(self, n_linha, linha, ocorrencias):
        """Escreve um registro inconsistente com as células pintadas."""
        if not ocorrencias:
            return
        if self.max_linhas is not None and self.linhas_escritas >= self.max_linhas:
            self.linhas_omitidas += 1
            return
        if self._aba is None or self._aba.n_linhas >= LIMITE_LINHAS_EXCEL:
            self._nova_aba_inconsistencias()

        por_campo = {}
        gravidade = 0.0
        tipos_presentes = []
        detalhes = []
        for oc in ocorrencias:
            atual = por_campo.get(oc.campo)
            if atual is None or T.tipo(oc.tipo).peso > T.tipo(atual).peso:
                por_campo[oc.campo] = oc.tipo
            gravidade += T.tipo(oc.tipo).peso
            if oc.tipo not in tipos_presentes:
                tipos_presentes.append(oc.tipo)
            if len(detalhes) < 15:
                detalhes.append(f"[{T.tipo(oc.tipo).rotulo}] {oc.descricao}")

        dominante = max(tipos_presentes, key=lambda t: T.tipo(t).peso)
        rotulos = ", ".join(T.tipo(t).rotulo for t in
                            sorted(tipos_presentes, key=lambda t: -T.tipo(t).peso))

        valores = [n_linha, self.motor.chave_registro(linha), len(ocorrencias),
                   round(gravidade, 1), rotulos, " | ".join(detalhes)]
        estilos = [dominante, dominante, dominante, dominante, dominante, None]
        for campo in self.colunas_saida:
            valores.append(linha.get(campo, ""))
            tipo_celula = por_campo.get(campo)
            if tipo_celula:
                estilos.append(tipo_celula)
            elif self.pintar_linha_inteira:
                estilos.append(dominante)
            else:
                estilos.append(None)
        self._aba.linha(valores, estilos=estilos)
        self.linhas_escritas += 1

    # ------------------------------------------------------------------ #
    def finalizar(self, ag, comparacao=None, meta=None):
        if self._aba is not None:
            self._aba.fechar()
            self._aba = None
        elif self._n_abas_inc == 0:
            self._nova_aba_inconsistencias()
            self._aba.linha(["Nenhuma inconsistência encontrada nesta execução."])
            self._aba.fechar()
            self._aba = None

        indicadores = ag.indicadores()
        self._aba_painel(ag, indicadores, meta)
        self._aba_campos(ag)
        self._aba_regras(ag)
        self._aba_tempestividade(ag)
        self._aba_serie(ag)
        self._aba_estratos(ag)
        if comparacao:
            self._aba_comparativo(comparacao)
        self._aba_legenda()
        self._aba_ficha(ag, meta)

        ordem = ["Painel", "Resumo por campo", "Resumo por regra", "Tempestividade",
                 "Série mensal", "Estratos", "Comparativo de envios", "Legenda",
                 "Ficha técnica"]
        ordem += [a.nome for a in self.livro.abas if a.nome.startswith("Inconsistências")]
        self.livro.reordenar(ordem)
        self.livro.fechar()

    # -- abas de resumo -------------------------------------------------- #
    def _aba_painel(self, ag, indicadores, meta):
        with self.livro.aba("Painel", larguras=[30, 12, 16, 14, 14, 62, 34],
                            congelar_linhas=6, autofiltro=False) as ab:
            ab.linha([f"Avaliação da qualidade — {self.cfg.sigla}"], estilo_geral="titulo")
            ab.linha([self.cfg.nome])
            ab.linha([f"{self.cfg.orgao}"])
            ab.linha([f"Base: {(meta or {}).get('arquivo', '')}  |  "
                      f"Extração: {(meta or {}).get('data_extracao', '')}  |  "
                      f"Execução: {datetime.now().strftime('%d/%m/%Y %H:%M')}"])
            escore = ag.escore_geral(indicadores)
            faixa, _cor = T.classificar(escore)
            ab.linha([f"Escore global ponderado: {escore}%  ({faixa})",
                      "", f"Registros: {ag.n_registros}",
                      f"Com inconsistência: {ag.n_registros_com_inconsistencia}",
                      f"Ocorrências: {ag.n_ocorrencias}"], estilo_geral="negrito")
            ab.linha(["Atributo", "Valor (%)", "Classificação", "Numerador",
                      "Denominador", "Como é calculado", "Observação"],
                     estilo_geral="cabecalho")
            for nome in [a.nome for a in T.ATRIBUTOS_AUTOMATICOS]:
                d = indicadores.get(nome)
                if not d:
                    continue
                estilo = f"faixa_{d['classificacao']}" if d["valor"] is not None else None
                ab.linha([nome, d["valor"], d["classificacao"], d["numerador"],
                          d["denominador"], d["formula"], d["observacao"]],
                         estilos=[None, estilo, estilo, None, None, None, None])
            ab.linha_vazia()
            ab.linha(["Ocorrências por tipo de inconsistência"], estilo_geral="negrito")
            ab.linha(["Tipo", "Ocorrências", "% das ocorrências", "Registros atingidos",
                      "% dos registros", "Atributos impactados"], estilo_geral="cabecalho")
            total = max(ag.n_ocorrencias, 1)
            for codigo in T.ORDEM_TIPOS:
                n = ag.occ_por_tipo.get(codigo, 0)
                if not n:
                    continue
                info = T.TIPOS[codigo]
                ab.linha([info.rotulo, n, round(100 * n / total, 2),
                          ag.reg_por_tipo.get(codigo, 0),
                          round(100 * ag.reg_por_tipo.get(codigo, 0) / max(ag.n_registros, 1), 2),
                          ", ".join(info.atributos)],
                         estilos=[codigo, None, None, None, None, None])

    def _aba_campos(self, ag):
        with self.livro.aba("Resumo por campo", larguras=[20, 30, 18, 8, 12, 12, 12, 12,
                                                          12, 12, 12, 12, 12, 40]) as ab:
            ab.linha(["Campo", "Rótulo", "Bloco", "Essencial", "Preenchidos",
                      "% preench.", "Em branco", "Ignorados", "% ignorado", "Inválidos",
                      "Incoerências", "Duplicidades", "Fora do prazo",
                      "Valores inválidos mais frequentes"], estilo_geral="cabecalho")
            for l in ag.resumo_campos():
                faixa, _ = T.classificar(l["pct_preenchimento"])
                ab.linha([
                    l["campo"], l["rotulo"], l["bloco"], "SIM" if l["essencial"] else "",
                    l["preenchidos"], l["pct_preenchimento"], l["vazios"], l["ignorados"],
                    l["pct_ignorado"], l["invalidos"], l["incoerencias"], l["duplicidades"],
                    l["fora_prazo"],
                    "; ".join(f"{v} ({n})" for v, n in l["valores_invalidos_frequentes"]),
                ], estilos=[None, None, None, None, None, f"faixa_{faixa}",
                            T.EM_BRANCO if l["vazios"] else None,
                            T.IGNORADO if l["ignorados"] else None, None,
                            T.CODIGO_INVALIDO if l["invalidos"] else None,
                            T.INCOERENCIA if l["incoerencias"] else None,
                            T.DUPLICIDADE if l["duplicidades"] else None,
                            T.FORA_DO_PRAZO if l["fora_prazo"] else None, None])

    def _aba_regras(self, ag):
        with self.livro.aba("Resumo por regra", larguras=[24, 22, 14, 14, 80]) as ab:
            ab.linha(["Regra", "Tipo", "Ocorrências", "% dos registros", "Descrição"],
                     estilo_geral="cabecalho")
            for r in ag.resumo_regras():
                ab.linha([r["regra"], T.tipo(r["tipo"]).rotulo, r["ocorrencias"],
                          r["pct_registros"], r["descricao"]],
                         estilos=[None, r["tipo"], None, None, None])

    def _aba_tempestividade(self, ag):
        with self.livro.aba("Tempestividade", larguras=[34, 10, 12, 12, 12, 10, 10, 10,
                                                        10, 10, 10, 12]) as ab:
            ab.linha(["Indicador de prazo", "Prazo (dias)", "Registros", "No prazo",
                      "% no prazo", "Média", "P25", "Mediana", "P75", "P90",
                      "Máximo", "Intervalos negativos"], estilo_geral="cabecalho")
            for t in ag.resumo_tempestividade():
                faixa, _ = T.classificar(t["pct_no_prazo"])
                ab.linha([t["rotulo"], t["prazo_dias"], t["registros"], t["no_prazo"],
                          t["pct_no_prazo"], t["media"], t["p25"], t["mediana"],
                          t["p75"], t["p90"], t["maximo"], t["negativos"]],
                         estilos=[None, None, None, None, f"faixa_{faixa}"] + [None] * 7)

    def _aba_serie(self, ag):
        with self.livro.aba("Série mensal", larguras=[14, 14, 16, 20, 18]) as ab:
            ab.linha(["Mês do evento", "Registros", "Ocorrências",
                      "Registros com inconsistência", "% com inconsistência"],
                     estilo_geral="cabecalho")
            for s in ag.resumo_serie():
                faixa, _ = T.classificar(100 - (s["pct_com_inc"] or 0))
                ab.linha([s["periodo"], s["registros"], s["ocorrencias"], s["com_inc"],
                          s["pct_com_inc"]],
                         estilos=[None, None, None, None, f"faixa_{faixa}"])

    def _aba_estratos(self, ag):
        if not ag.estratos:
            return
        with self.livro.aba("Estratos", larguras=[26, 44, 14, 14, 20, 18, 20]) as ab:
            ab.linha(["Variável", "Valor", "Registros", "Ocorrências",
                      "Registros com inconsist.", "% com inconsist.",
                      "Ocorrências por registro"], estilo_geral="cabecalho")
            for campo in ag.estratos:
                for e in ag.resumo_estratos(campo, top=60):
                    faixa, _ = T.classificar(100 - (e["pct_com_inc"] or 0))
                    ab.linha([self.cfg.rotulo(campo), e["valor"], e["registros"],
                              e["ocorrencias"], e["com_inc"], e["pct_com_inc"],
                              e["ocorrencias_por_registro"]],
                             estilos=[None, None, None, None, None, f"faixa_{faixa}", None])

    def _aba_comparativo(self, comp):
        with self.livro.aba("Comparativo de envios", larguras=[44, 18, 46],
                            congelar_linhas=1, autofiltro=False) as ab:
            ab.linha(["Indicador", "Valor", "Leitura"], estilo_geral="cabecalho")
            for item in comp.linhas_resumo():
                ab.linha([item["rotulo"], item["valor"], item["leitura"]])
            ab.linha_vazia()
            ab.linha(["Resolutividade por tipo de inconsistência"], estilo_geral="negrito")
            ab.linha(["Tipo", "Existiam no envio anterior", "Corrigidas", "% resolvido",
                      "Persistentes", "Novas"], estilo_geral="cabecalho")
            for l in comp.por_tipo():
                ab.linha([T.tipo(l["tipo"]).rotulo, l["anteriores"], l["corrigidas"],
                          l["pct_resolvido"], l["persistentes"], l["novas"]],
                         estilos=[l["tipo"], None, None, None, None, None])
            ab.linha_vazia()
            ab.linha(["Resolutividade por campo (20 maiores)"], estilo_geral="negrito")
            ab.linha(["Campo", "Existiam", "Corrigidas", "% resolvido", "Persistentes",
                      "Novas"], estilo_geral="cabecalho")
            for l in comp.por_campo(20):
                ab.linha([l["campo"], l["anteriores"], l["corrigidas"], l["pct_resolvido"],
                          l["persistentes"], l["novas"]])

    def _aba_legenda(self):
        with self.livro.aba("Legenda", larguras=[26, 12, 14, 62, 46],
                            congelar_linhas=2, autofiltro=False) as ab:
            ab.linha(["Legenda de cores das inconsistências"], estilo_geral="titulo")
            ab.linha(["Tipo", "Cor", "Gravidade", "O que significa",
                      "Atributos de qualidade impactados"], estilo_geral="cabecalho")
            for codigo in T.ORDEM_TIPOS:
                info = T.TIPOS[codigo]
                ab.linha([info.rotulo, "", info.gravidade.capitalize(), info.descricao,
                          ", ".join(info.atributos)],
                         estilos=[codigo, codigo, None, None, None])
            ab.linha_vazia()
            ab.linha(["Faixas de classificação dos indicadores"], estilo_geral="negrito")
            ab.linha(["Faixa", "Critério"], estilo_geral="cabecalho")
            faixas = [("Excelente", "≥ 95%"), ("Bom", "90% a 94,9%"),
                      ("Regular", "80% a 89,9%"), ("Ruim", "50% a 79,9%"),
                      ("Muito ruim", "< 50%")]
            for rotulo, criterio in faixas:
                ab.linha([rotulo, criterio], estilos=[f"faixa_{rotulo}", None])

    def _aba_ficha(self, ag, meta):
        meta = meta or {}
        with self.livro.aba("Ficha técnica", larguras=[36, 90], congelar_linhas=1,
                            autofiltro=False) as ab:
            ab.linha(["Item", "Conteúdo"], estilo_geral="cabecalho")
            itens = [
                ("Sistema", f"{self.cfg.sigla} — {self.cfg.nome}"),
                ("Órgão responsável", self.cfg.orgao),
                ("Arquivo analisado", meta.get("arquivo", "")),
                ("Tamanho do arquivo", meta.get("tamanho", "")),
                ("Codificação detectada", meta.get("encoding", "")),
                ("Separador detectado", meta.get("separador", "")),
                ("Data da extração informada", str(meta.get("data_extracao", ""))),
                ("Data/hora do processamento", datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
                ("Registros lidos", ag.n_registros),
                ("Colunas na base", len(self.colunas_base)),
                ("Campos avaliados (dicionário)", ag.n_campos),
                ("Campos essenciais", len(ag.essenciais)),
                ("Regras cruzadas ativas", len(self.motor.regras_ativas)),
                ("Chaves de duplicidade ativas", len(self.motor.chaves_dup)),
                ("Registros com inconsistência", ag.n_registros_com_inconsistencia),
                ("Total de ocorrências", ag.n_ocorrencias),
                ("Linhas exportadas nesta planilha", self.linhas_escritas),
                ("Linhas omitidas por limite", self.linhas_omitidas),
                ("Arquivo de configuração", self.cfg.caminho or ""),
                ("Versão do QualiSIS", meta.get("versao", "")),
            ]
            for chave, valor in itens:
                ab.linha([chave, valor], estilos=["negrito", None])
            ab.linha_vazia()
            ab.linha(["Colunas da base sem correspondência no dicionário de dados"],
                     estilo_geral="negrito")
            cobertura = self.cfg.validar_contra_base(self.colunas_base)
            ab.linha([", ".join(cobertura["nao_previstas"]) or "(nenhuma)"])
            ab.linha(["Campos do dicionário ausentes na base"], estilo_geral="negrito")
            ab.linha([", ".join(cobertura["ausentes"]) or "(nenhum)"])


def _clarear(hexcor, fator=0.75):
    """Clareia uma cor para uso como preenchimento (texto preto continua legível)."""
    h = hexcor.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r + (255 - r) * fator)
    g = int(g + (255 - g) * fator)
    b = int(b + (255 - b) * fator)
    return f"{r:02X}{g:02X}{b:02X}"
