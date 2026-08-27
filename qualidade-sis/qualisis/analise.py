"""Agregação estatística e cálculo dos indicadores por atributo de qualidade.

O agregador recebe um registro por vez (nunca a base inteira) e mantém apenas
contadores. Ao final, converte contadores em indicadores percentuais, cada um
com numerador, denominador e fórmula explícitos — para que qualquer número do
relatório possa ser auditado e reproduzido pelo setor.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from . import tipos as T

LIMITE_ESTRATOS = 800
LIMITE_VALORES_INVALIDOS = 40


def _pct(num, den):
    if not den:
        return None
    return round(100.0 * num / den, 2)


def _quantil(pares_ordenados, total, q):
    """Quantil a partir de um histograma {valor: frequência} já ordenado."""
    if not total:
        return None
    alvo = q * total
    acumulado = 0
    for valor, freq in pares_ordenados:
        acumulado += freq
        if acumulado >= alvo:
            return valor
    return pares_ordenados[-1][0] if pares_ordenados else None


class Agregador:
    def __init__(self, cfg, motor, data_extracao=None):
        self.cfg = cfg
        self.motor = motor
        self.data_extracao = data_extracao or date.today()
        self.campos = list(motor.campos_ativos)
        self.n_campos = len(self.campos)
        self.essenciais = [c for c in self.campos if cfg.campos[c].get("essencial")]
        self.campos_com_dominio = [c for c in self.campos if cfg.campos[c].get("dominio")]

        self.n_registros = 0
        self.n_registros_com_inconsistencia = 0
        self.n_registros_completos = 0          # todos os essenciais preenchidos
        self.n_registros_sem_ignorado = 0
        self.n_ocorrencias = 0

        self.occ_por_tipo = Counter()
        self.reg_por_tipo = Counter()
        self.occ_por_campo = defaultdict(Counter)     # campo -> tipo -> n
        self.occ_por_regra = Counter()
        self.regra_descricao = {}
        self.regra_tipo = {}
        self.occ_por_gravidade = Counter()

        self.preenchidos = Counter()      # campo -> nº preenchidos
        self.vazios = Counter()
        self.preenchidos_dominio = 0
        self.valores_invalidos = defaultdict(Counter)  # campo -> valor -> n

        self.serie_mensal = defaultdict(lambda: {"registros": 0, "ocorrencias": 0, "com_inc": 0})
        self.estratos = {c: defaultdict(lambda: {"registros": 0, "ocorrencias": 0, "com_inc": 0})
                         for c in cfg.campos_estratificacao}

        self.atrasos = defaultdict(Counter)   # id tempestividade -> dias -> n
        self.atrasos_no_prazo = Counter()
        self.atrasos_total = Counter()

        self.data_min_evento = None
        self.data_max_evento = None
        self.chaves_registro = 0
        self.chaves_vazias = 0

    # ------------------------------------------------------------------ #
    def adicionar(self, linha, ocorrencias, contexto):
        self.n_registros += 1

        vazios_essenciais = 0
        for campo in self.campos:
            valor = (linha.get(campo) or "").strip()
            if valor:
                self.preenchidos[campo] += 1
            else:
                self.vazios[campo] += 1
                if campo in self.cfg.campos and self.cfg.campos[campo].get("essencial"):
                    vazios_essenciais += 1
        for campo in self.campos_com_dominio:
            if (linha.get(campo) or "").strip():
                self.preenchidos_dominio += 1
        if vazios_essenciais == 0:
            self.n_registros_completos += 1

        tipos_no_registro = set()
        for oc in ocorrencias:
            self.n_ocorrencias += 1
            self.occ_por_tipo[oc.tipo] += 1
            self.occ_por_campo[oc.campo][oc.tipo] += 1
            self.occ_por_regra[oc.regra] += 1
            self.regra_descricao.setdefault(oc.regra, oc.descricao)
            self.regra_tipo.setdefault(oc.regra, oc.tipo)
            self.occ_por_gravidade[T.tipo(oc.tipo).gravidade] += 1
            tipos_no_registro.add(oc.tipo)
            if oc.tipo in (T.CODIGO_INVALIDO, T.FORA_DE_FAIXA, T.DATA_INVALIDA) and oc.valor:
                alvo = self.valores_invalidos[oc.campo]
                if len(alvo) < LIMITE_VALORES_INVALIDOS or oc.valor in alvo:
                    alvo[str(oc.valor)[:60]] += 1

        for tp in tipos_no_registro:
            self.reg_por_tipo[tp] += 1
        tem_inc = bool(ocorrencias)
        if tem_inc:
            self.n_registros_com_inconsistencia += 1
        if T.IGNORADO not in tipos_no_registro:
            self.n_registros_sem_ignorado += 1

        # tempestividade
        for tid, dias in contexto.get("atrasos", {}).items():
            self.atrasos[tid][dias] += 1
            self.atrasos_total[tid] += 1
            prazo = self._prazo(tid)
            if prazo is not None and 0 <= dias <= prazo:
                self.atrasos_no_prazo[tid] += 1

        # série temporal pelo evento de referência
        dref = contexto.get("data_referencia")
        if dref:
            chave = f"{dref.year:04d}-{dref.month:02d}"
            bloco = self.serie_mensal[chave]
            bloco["registros"] += 1
            bloco["ocorrencias"] += len(ocorrencias)
            bloco["com_inc"] += 1 if tem_inc else 0
            if self.data_min_evento is None or dref < self.data_min_evento:
                self.data_min_evento = dref
            if self.data_max_evento is None or dref > self.data_max_evento:
                self.data_max_evento = dref

        # estratos (distrito sanitário, unidade notificadora, agravo...)
        for campo, mapa in self.estratos.items():
            valor = (linha.get(campo) or "").strip() or "(em branco)"
            if len(mapa) >= LIMITE_ESTRATOS and valor not in mapa:
                valor = "(outros)"
            bloco = mapa[valor]
            bloco["registros"] += 1
            bloco["ocorrencias"] += len(ocorrencias)
            bloco["com_inc"] += 1 if tem_inc else 0

        chave = self.motor.chave_registro(linha)
        if chave:
            self.chaves_registro += 1
        else:
            self.chaves_vazias += 1

    def _prazo(self, tid):
        for tp in self.cfg.tempestividade:
            if tp["id"] == tid:
                return tp.get("prazo_dias")
        return None

    def _rotulo_tempestividade(self, tid):
        for tp in self.cfg.tempestividade:
            if tp["id"] == tid:
                return tp.get("rotulo", tid)
        return tid

    # ------------------------------------------------------------------ #
    # Indicadores por atributo de qualidade
    # ------------------------------------------------------------------ #
    def indicadores(self):
        N = self.n_registros
        celulas = N * self.n_campos
        celulas_essenciais = N * len(self.essenciais)
        vazios_essenciais = sum(
            self.occ_por_campo[c][T.EM_BRANCO] for c in self.essenciais
        )
        celulas_vazias = sum(self.vazios.values())
        celulas_preenchidas = celulas - celulas_vazias
        ignorados = self.occ_por_tipo[T.IGNORADO]
        invalidos = (self.occ_por_tipo[T.CODIGO_INVALIDO] + self.occ_por_tipo[T.DATA_INVALIDA]
                     + self.occ_por_tipo[T.FORMATO_INVALIDO] + self.occ_por_tipo[T.FORA_DE_FAIXA])
        reg_incoerentes = self.reg_por_tipo[T.INCOERENCIA]
        reg_duplicados = self.reg_por_tipo[T.DUPLICIDADE]
        reg_data_invalida = self.reg_por_tipo[T.DATA_INVALIDA]
        reg_fora_faixa = self.reg_por_tipo[T.FORA_DE_FAIXA]

        ind = {}

        def add(nome, valor, num, den, formula, obs=""):
            rotulo, cor = T.classificar(valor)
            ind[nome] = {
                "atributo": nome,
                "valor": valor,
                "numerador": num,
                "denominador": den,
                "formula": formula,
                "classificacao": rotulo,
                "cor": cor,
                "observacao": obs,
            }

        add("Completude", _pct(celulas_essenciais - vazios_essenciais, celulas_essenciais),
            celulas_essenciais - vazios_essenciais, celulas_essenciais,
            "campos essenciais preenchidos ÷ (registros × campos essenciais)")

        add("Suficiência", _pct(self.n_registros_completos, N),
            self.n_registros_completos, N,
            "registros com TODOS os campos essenciais preenchidos ÷ registros")

        add("Confiabilidade", _pct(celulas_preenchidas - ignorados, celulas_preenchidas),
            celulas_preenchidas - ignorados, celulas_preenchidas,
            "campos preenchidos com valor informativo ÷ campos preenchidos "
            "(exclui 'ignorado'/'não informado')")

        add("Validade", _pct(self.preenchidos_dominio - self.occ_por_tipo[T.CODIGO_INVALIDO],
                             self.preenchidos_dominio),
            self.preenchidos_dominio - self.occ_por_tipo[T.CODIGO_INVALIDO],
            self.preenchidos_dominio,
            "valores dentro do domínio ÷ valores preenchidos em campos com domínio definido")

        add("Correção", _pct(celulas_preenchidas - invalidos, celulas_preenchidas),
            celulas_preenchidas - invalidos, celulas_preenchidas,
            "campos sem erro detectável (domínio, data, formato, faixa) ÷ campos preenchidos")

        add("Precisão", _pct(celulas_preenchidas - self.occ_por_tipo[T.FORA_DE_FAIXA]
                             - self.occ_por_tipo[T.FORMATO_INVALIDO], celulas_preenchidas),
            celulas_preenchidas - self.occ_por_tipo[T.FORA_DE_FAIXA]
            - self.occ_por_tipo[T.FORMATO_INVALIDO], celulas_preenchidas,
            "campos sem erro de faixa/formato ÷ campos preenchidos")

        add("Coerência", _pct(N - reg_incoerentes, N), N - reg_incoerentes, N,
            "registros sem incoerência entre campos ÷ registros")

        add("Logicidade", _pct(N - reg_incoerentes - reg_data_invalida, N),
            max(N - reg_incoerentes - reg_data_invalida, 0), N,
            "registros sem incoerência lógica nem data impossível ÷ registros")

        add("Singularidade", _pct(N - reg_duplicados, N), N - reg_duplicados, N,
            "registros não duplicados ÷ registros")

        # Tempestividade: média ponderada das regras de prazo configuradas
        num_t = sum(self.atrasos_no_prazo.values())
        den_t = sum(self.atrasos_total.values())
        add("Tempestividade", _pct(num_t, den_t), num_t, den_t,
            "registros dentro do prazo pactuado ÷ registros com as duas datas preenchidas")

        # Atualidade: defasagem do evento mais recente em relação à extração
        defasagem = None
        valor_atualidade = None
        if self.data_max_evento:
            defasagem = (self.data_extracao - self.data_max_evento).days
            prazo_ref = self.cfg.parametros.get("defasagem_aceitavel_dias", 30)
            valor_atualidade = round(max(0.0, min(100.0, 100.0 * prazo_ref / max(defasagem, 1)
                                                  if defasagem > prazo_ref else 100.0)), 2)
        add("Atualidade", valor_atualidade, defasagem,
            self.cfg.parametros.get("defasagem_aceitavel_dias", 30),
            "100% se a defasagem entre a extração e o evento mais recente ≤ prazo aceitável; "
            "decai proporcionalmente acima disso",
            obs=f"Defasagem observada: {defasagem} dias" if defasagem is not None else "")

        # Abrangência: estratos esperados presentes na base
        esperados = self.cfg.parametros.get("estratos_esperados") or []
        campo_estrato = self.cfg.parametros.get("campo_abrangencia")
        valor_abr, num_abr, den_abr = None, 0, 0
        if esperados and campo_estrato and campo_estrato.upper() in self.estratos:
            presentes = {k for k, v in self.estratos[campo_estrato.upper()].items()
                         if v["registros"] > 0}
            num_abr = len([e for e in esperados if str(e) in presentes])
            den_abr = len(esperados)
            valor_abr = _pct(num_abr, den_abr)
        elif campo_estrato and campo_estrato.upper() in self.preenchidos:
            num_abr = self.preenchidos[campo_estrato.upper()]
            den_abr = N
            valor_abr = _pct(num_abr, den_abr)
        add("Abrangência", valor_abr, num_abr, den_abr,
            "estratos (distritos/unidades) esperados presentes na base ÷ estratos esperados")

        add("Quantidade", None, N, self.cfg.parametros.get("registros_esperados_ano"),
            "volume de registros do período — avaliado na comparação entre envios",
            obs=f"{N:,}".replace(",", "."))

        add("Formato", _pct(celulas_preenchidas - self.occ_por_tipo[T.FORMATO_INVALIDO],
                            celulas_preenchidas),
            celulas_preenchidas - self.occ_por_tipo[T.FORMATO_INVALIDO], celulas_preenchidas,
            "campos com máscara/estrutura corretas ÷ campos preenchidos")

        reg_suspeitos = reg_data_invalida + reg_fora_faixa + reg_incoerentes
        add("Veracidade", _pct(max(N - reg_suspeitos, 0), N), max(N - reg_suspeitos, 0), N,
            "registros sem indício de erro material (data impossível, valor implausível, "
            "incoerência) ÷ registros")

        add("Inequivocidade", _pct(celulas_preenchidas - ignorados
                                   - self.occ_por_tipo[T.CODIGO_INVALIDO], celulas_preenchidas),
            celulas_preenchidas - ignorados - self.occ_por_tipo[T.CODIGO_INVALIDO],
            celulas_preenchidas,
            "campos com significado único (sem 'ignorado' e sem código fora do domínio) "
            "÷ campos preenchidos")

        cobertura = self.cfg.validar_contra_base(self.motor.colunas) if self.motor.colunas else None
        if cobertura:
            den_c = len(cobertura["cobertas"]) + len(cobertura["ausentes"])
            add("Compatibilidade", _pct(len(cobertura["cobertas"]), den_c),
                len(cobertura["cobertas"]), den_c,
                "campos do dicionário oficial presentes na exportação ÷ campos do dicionário",
                obs=f"{len(cobertura['nao_previstas'])} coluna(s) na base fora do dicionário")
            add("Mensurabilidade", _pct(len(cobertura["cobertas"]), den_c),
                len(cobertura["cobertas"]), den_c,
                "variáveis necessárias aos indicadores do setor disponíveis na base")

        celulas_uteis = celulas_preenchidas - ignorados - invalidos
        add("Valor informativo", _pct(celulas_uteis, celulas),
            celulas_uteis, celulas,
            "campos preenchidos, válidos e não ignorados ÷ total de campos da base")

        add("Volume", None, celulas, None,
            "massa de dados processada (registros × campos)",
            obs=f"{N:,} registros × {self.n_campos} campos".replace(",", "."))

        neg = sum(1 for tid in self.atrasos for d in self.atrasos[tid] if d < 0)
        add("Ordem", _pct(N - reg_data_invalida, N), N - reg_data_invalida, N,
            "registros com sequência cronológica coerente ÷ registros",
            obs=f"{neg} intervalo(s) negativo(s) entre datas" if neg else "")

        return ind

    # ------------------------------------------------------------------ #
    def escore_geral(self, indicadores=None):
        ind = indicadores or self.indicadores()
        soma, pesos = 0.0, 0.0
        for nome, dados in ind.items():
            if dados["valor"] is None:
                continue
            atributo = T.ATRIBUTOS.get(nome)
            peso = self.cfg.pesos_atributos.get(nome, atributo.peso if atributo else 1.0)
            soma += dados["valor"] * peso
            pesos += peso
        if not pesos:
            return None
        return round(soma / pesos, 2)

    # ------------------------------------------------------------------ #
    def resumo_tempestividade(self):
        saida = []
        for tid, hist in self.atrasos.items():
            pares = sorted(hist.items())
            total = sum(hist.values())
            prazo = self._prazo(tid)
            saida.append({
                "id": tid,
                "rotulo": self._rotulo_tempestividade(tid),
                "prazo_dias": prazo,
                "registros": total,
                "no_prazo": self.atrasos_no_prazo.get(tid, 0),
                "pct_no_prazo": _pct(self.atrasos_no_prazo.get(tid, 0), total),
                "mediana": _quantil(pares, total, 0.5),
                "p25": _quantil(pares, total, 0.25),
                "p75": _quantil(pares, total, 0.75),
                "p90": _quantil(pares, total, 0.90),
                "minimo": pares[0][0] if pares else None,
                "maximo": pares[-1][0] if pares else None,
                "media": round(sum(d * n for d, n in pares) / total, 1) if total else None,
                "negativos": sum(n for d, n in pares if d < 0),
                "histograma": pares,
            })
        return saida

    def resumo_campos(self):
        """Tabela campo a campo: preenchimento, ignorados, inválidos, incoerências."""
        linhas = []
        N = max(self.n_registros, 1)
        for campo in self.campos:
            spec = self.cfg.campos[campo]
            oc = self.occ_por_campo.get(campo, Counter())
            preenchidos = self.preenchidos.get(campo, 0)
            linhas.append({
                "campo": campo,
                "rotulo": spec.get("rotulo", campo),
                "bloco": spec.get("bloco", "Geral"),
                "essencial": bool(spec.get("essencial")),
                "preenchidos": preenchidos,
                "vazios": self.vazios.get(campo, 0),
                "pct_preenchimento": _pct(preenchidos, N),
                "ignorados": oc[T.IGNORADO],
                "pct_ignorado": _pct(oc[T.IGNORADO], max(preenchidos, 1)),
                "invalidos": oc[T.CODIGO_INVALIDO] + oc[T.DATA_INVALIDA]
                + oc[T.FORMATO_INVALIDO] + oc[T.FORA_DE_FAIXA],
                "incoerencias": oc[T.INCOERENCIA],
                "duplicidades": oc[T.DUPLICIDADE],
                "fora_prazo": oc[T.FORA_DO_PRAZO],
                "total_ocorrencias": sum(oc.values()),
                "pct_ok": _pct(N - sum(oc.values()), N),
                "valores_invalidos_frequentes": self.valores_invalidos.get(campo, Counter()).most_common(10),
            })
        linhas.sort(key=lambda x: (-x["total_ocorrencias"], x["campo"]))
        return linhas

    def resumo_regras(self):
        saida = []
        for regra, n in self.occ_por_regra.most_common():
            saida.append({
                "regra": regra,
                "tipo": self.regra_tipo.get(regra, ""),
                "descricao": self.regra_descricao.get(regra, ""),
                "ocorrencias": n,
                "pct_registros": _pct(n, max(self.n_registros, 1)),
            })
        return saida

    def resumo_estratos(self, campo, top=25):
        mapa = self.estratos.get(campo, {})
        itens = sorted(mapa.items(), key=lambda kv: -kv[1]["registros"])[:top]
        return [{
            "valor": k,
            "registros": v["registros"],
            "ocorrencias": v["ocorrencias"],
            "com_inc": v["com_inc"],
            "pct_com_inc": _pct(v["com_inc"], max(v["registros"], 1)),
            "ocorrencias_por_registro": round(v["ocorrencias"] / max(v["registros"], 1), 2),
        } for k, v in itens]

    def resumo_serie(self):
        return [{
            "periodo": k,
            "registros": v["registros"],
            "ocorrencias": v["ocorrencias"],
            "com_inc": v["com_inc"],
            "pct_com_inc": _pct(v["com_inc"], max(v["registros"], 1)),
        } for k, v in sorted(self.serie_mensal.items())]
