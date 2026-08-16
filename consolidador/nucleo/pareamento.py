"""Pareamento (record linkage) entre os dois sistemas.

Tres passadas, da mais segura para a mais tolerante:

1. Chave primaria - igualdade exata do valor normalizado (CPF/CNPJ pelos
   digitos, codigos sem pontuacao).
2. Chaves alternativas - combinacoes de campos definidas no perfil ou
   deduzidas automaticamente.
3. Similaridade - comparacao aproximada (Jaro-Winkler + tokens) sobre os
   campos de texto mais informativos, com bloqueio por token para nao
   comparar todos contra todos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import texto as tx
from .config import Perfil
from .normalizacao import COL_ID, Consolidado, ParDeCampos, mapear_campos_entre_sistemas

TIPO_CHAVE = "Exato por chave"
TIPO_ALTERNATIVA = "Exato por chave alternativa"
TIPO_PROVAVEL = "Provavel por similaridade"
TIPO_DUVIDOSO = "Duvidoso - revisar"


@dataclass
class Divergencia:
    campo_a: str
    campo_b: str
    valor_a: str
    valor_b: str


@dataclass
class Par:
    id_a: str
    id_b: str
    tipo: str
    chave_usada: str
    valor_chave: str
    escore: float
    divergencias: List[Divergencia] = field(default_factory=list)
    multiplicidade: str = "1:1"
    linha_a: Dict[str, Any] = field(default_factory=dict)
    linha_b: Dict[str, Any] = field(default_factory=dict)

    @property
    def situacao(self) -> str:
        if self.divergencias:
            return f"Divergente em {len(self.divergencias)} campo(s)"
        return "Identico nos campos comparados"


@dataclass
class NaoPareado:
    linha: Dict[str, Any]
    motivo: str
    melhor_candidato: str = ""
    escore_candidato: float = 0.0


@dataclass
class ResultadoPareamento:
    pares: List[Par] = field(default_factory=list)
    somente_a: List[NaoPareado] = field(default_factory=list)
    somente_b: List[NaoPareado] = field(default_factory=list)
    mapa_campos: List[ParDeCampos] = field(default_factory=list)
    chaves_usadas: List[Tuple[str, str]] = field(default_factory=list)
    campos_similaridade: List[Tuple[str, str]] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)

    @property
    def total_pares(self) -> int:
        return len(self.pares)

    def contagem_por_tipo(self) -> Dict[str, int]:
        contagem: Dict[str, int] = {}
        for par in self.pares:
            contagem[par.tipo] = contagem.get(par.tipo, 0) + 1
        return contagem

    @property
    def pares_divergentes(self) -> int:
        return sum(1 for p in self.pares if p.divergencias)


# --------------------------------------------------------------------------
# Entrada principal
# --------------------------------------------------------------------------


def parear(
    consolidado_a: Consolidado,
    consolidado_b: Consolidado,
    perfil: Perfil,
) -> ResultadoPareamento:
    resultado = ResultadoPareamento()
    resultado.mapa_campos = mapear_campos_entre_sistemas(consolidado_a, consolidado_b, perfil)
    if not consolidado_a.tabela.linhas or not consolidado_b.tabela.linhas:
        resultado.avisos.append("Um dos sistemas ficou sem registros: o pareamento nao foi possivel.")
        resultado.somente_a = [NaoPareado(l, "Sistema oposto sem registros") for l in consolidado_a.tabela.linhas]
        resultado.somente_b = [NaoPareado(l, "Sistema oposto sem registros") for l in consolidado_b.tabela.linhas]
        return resultado

    escolhidos = set(perfil.pareamento.campos_comparacao)
    if escolhidos:
        # O perfil pode restringir o que e comparado: comparar campos que os
        # dois sistemas preenchem com vocabularios diferentes so gera ruido.
        comparaveis = [p for p in resultado.mapa_campos if p.campo_a in escolhidos]
    else:
        comparaveis = list(resultado.mapa_campos)

    chaves = _definir_chaves(consolidado_a, consolidado_b, perfil, resultado)
    if not chaves:
        resultado.avisos.append(
            "Nenhuma chave comum foi identificada; o pareamento usou apenas similaridade."
        )
    resultado.chaves_usadas = [(c[0], c[1]) for c in chaves]

    pareados_a: Dict[str, List[Par]] = {}
    pareados_b: Dict[str, List[Par]] = {}

    for ordem, (campo_a, campo_b, rotulo) in enumerate(chaves):
        tipo = TIPO_CHAVE if ordem == 0 else TIPO_ALTERNATIVA
        _parear_por_chave(
            consolidado_a, consolidado_b, campo_a, campo_b, rotulo, tipo,
            resultado, pareados_a, pareados_b, comparaveis,
        )

    restantes_a = [l for l in consolidado_a.tabela.linhas if l[COL_ID] not in pareados_a]
    restantes_b = [l for l in consolidado_b.tabela.linhas if l[COL_ID] not in pareados_b]
    campos_sim = _definir_campos_similaridade(
        consolidado_a, consolidado_b, perfil, resultado, {c[0] for c in chaves}
    )
    resultado.campos_similaridade = campos_sim

    aproximados = _parear_por_similaridade(
        restantes_a, restantes_b, campos_sim, perfil, consolidado_a, consolidado_b,
        comparaveis,
    )
    for par in aproximados:
        resultado.pares.append(par)
        pareados_a.setdefault(par.id_a, []).append(par)
        pareados_b.setdefault(par.id_b, []).append(par)

    _marcar_multiplicidade(resultado, pareados_a, pareados_b)
    _listar_nao_pareados(
        consolidado_a, consolidado_b, pareados_a, pareados_b, campos_sim, resultado
    )
    resultado.pares.sort(key=lambda p: (p.tipo != TIPO_CHAVE, -p.escore, p.id_a))
    return resultado


# --------------------------------------------------------------------------
# Escolha de chaves e de campos de similaridade
# --------------------------------------------------------------------------


def _definir_chaves(
    consolidado_a: Consolidado,
    consolidado_b: Consolidado,
    perfil: Perfil,
    resultado: ResultadoPareamento,
) -> List[Tuple[str, str, str]]:
    """Devolve pares (campo em A, campo em B, rotulo) em ordem de prioridade."""
    chaves: List[Tuple[str, str, str]] = []
    mapa_direto = {p.campo_a: p.campo_b for p in resultado.mapa_campos}

    # Tanto a chave primaria quanto as alternativas podem combinar campos,
    # escritos como "Nome+Data de nascimento" ou como lista.
    grupos = [
        nome.split("+") if isinstance(nome, str) else list(nome)
        for nome in perfil.pareamento.chaves_primarias
    ]
    grupos += [list(g) for g in perfil.pareamento.chaves_alternativas if g]
    for grupo in grupos:
        grupo = [c.strip() for c in grupo if c.strip()]
        if not grupo:
            continue
        campos_b = [mapa_direto.get(c, c) for c in grupo]
        if all(c in consolidado_a.tabela.colunas for c in grupo) and \
           all(c in consolidado_b.tabela.colunas for c in campos_b):
            chaves.append(("+".join(grupo), "+".join(campos_b), " + ".join(grupo)))
    if chaves:
        return chaves

    # Modo automatico: procura o par de colunas com maior poder de identificacao
    candidatos: List[Tuple[float, str, str, str]] = []
    for par in resultado.mapa_campos:
        campo_a = consolidado_a.campo(par.campo_a)
        campo_b = consolidado_b.campo(par.campo_b)
        if not campo_a or not campo_b:
            continue
        completude_a, unicidade_a = _perfil_coluna(consolidado_a, par.campo_a)
        completude_b, unicidade_b = _perfil_coluna(consolidado_b, par.campo_b)
        if completude_a < 0.70 or completude_b < 0.70:
            continue
        # A chave nao precisa ser unica dos dois lados: e comum um sistema
        # trazer uma linha por atendimento e o outro uma linha por pessoa.
        documento = campo_a.tipo in ("cpf", "cnpj", "cpf_cnpj", "codigo")
        if max(unicidade_a, unicidade_b) < 0.90 and not documento:
            continue
        sobreposicao = _sobreposicao_valores(consolidado_a, par.campo_a, consolidado_b, par.campo_b)
        if sobreposicao < 0.05:
            continue
        bonus = 0.35 if campo_a.tipo in ("cpf", "cnpj", "cpf_cnpj") else 0.0
        bonus += 0.15 if campo_a.chave or campo_b.chave else 0.0
        nota = (
            0.45 * sobreposicao
            + 0.25 * max(unicidade_a, unicidade_b)
            + 0.15 * min(unicidade_a, unicidade_b)
            + 0.15 * min(completude_a, completude_b)
            + bonus
        )
        candidatos.append((nota, par.campo_a, par.campo_b, par.campo_a))
    candidatos.sort(key=lambda item: -item[0])
    for nota, campo_a, campo_b, rotulo in candidatos[:3]:
        chaves.append((campo_a, campo_b, rotulo))
    return chaves


def _perfil_coluna(consolidado: Consolidado, coluna: str) -> Tuple[float, float]:
    """Devolve (completude, unicidade) da coluna, de 0 a 1."""
    valores = [tx.normalizar(l.get(coluna)) for l in consolidado.tabela.linhas]
    preenchidos = [v for v in valores if v]
    if not preenchidos:
        return 0.0, 0.0
    return len(preenchidos) / len(valores), len(set(preenchidos)) / len(preenchidos)


def _poder_identificador(consolidado: Consolidado, coluna: str) -> float:
    completude, unicidade = _perfil_coluna(consolidado, coluna)
    return unicidade * 0.7 + completude * 0.3


def _sobreposicao_valores(
    consolidado_a: Consolidado, coluna_a: str, consolidado_b: Consolidado, coluna_b: str
) -> float:
    valores_a = {_chave_normalizada(l.get(coluna_a)) for l in consolidado_a.tabela.linhas}
    valores_b = {_chave_normalizada(l.get(coluna_b)) for l in consolidado_b.tabela.linhas}
    valores_a.discard("")
    valores_b.discard("")
    if not valores_a or not valores_b:
        return 0.0
    return len(valores_a & valores_b) / min(len(valores_a), len(valores_b))


def _definir_campos_similaridade(
    consolidado_a: Consolidado,
    consolidado_b: Consolidado,
    perfil: Perfil,
    resultado: ResultadoPareamento,
    campos_chave: Optional[set] = None,
) -> List[Tuple[str, str]]:
    mapa_direto = {p.campo_a: p.campo_b for p in resultado.mapa_campos}
    escolhidos: List[Tuple[str, str]] = []
    for nome in perfil.pareamento.campos_similaridade:
        campo_b = mapa_direto.get(nome, nome)
        if nome in consolidado_a.tabela.colunas and campo_b in consolidado_b.tabela.colunas:
            escolhidos.append((nome, campo_b))
    if escolhidos:
        return escolhidos
    # Campos ja usados como chave exata nao ajudam na segunda passada: ali
    # estao justamente os registros cuja chave falhou.
    usados = campos_chave or set()
    for excluir_chaves in (True, False):  # sem candidatos, aceita reusar as chaves
        candidatos: List[Tuple[float, str, str]] = []
        for par in resultado.mapa_campos:
            campo_a = consolidado_a.campo(par.campo_a)
            if not campo_a or campo_a.tipo not in ("texto", "codigo", "cpf", "cnpj", "cpf_cnpj"):
                continue
            if excluir_chaves and par.campo_a in usados:
                continue
            poder = _poder_identificador(consolidado_a, par.campo_a)
            if poder < 0.55:
                continue
            candidatos.append((poder * par.nota, par.campo_a, par.campo_b))
        if candidatos:
            candidatos.sort(key=lambda item: -item[0])
            return [(a, b) for _, a, b in candidatos[:2]]
    return []


# --------------------------------------------------------------------------
# Passadas de pareamento
# --------------------------------------------------------------------------


def _chave_normalizada(valor: Any) -> str:
    return tx.chave_valor(valor)


def _valor_chave(linha: Dict[str, Any], especificacao: str) -> str:
    partes = [_chave_normalizada(linha.get(c)) for c in especificacao.split("+")]
    if not all(partes):
        return ""
    return "|".join(partes)


def _parear_por_chave(
    consolidado_a: Consolidado,
    consolidado_b: Consolidado,
    campo_a: str,
    campo_b: str,
    rotulo: str,
    tipo: str,
    resultado: ResultadoPareamento,
    pareados_a: Dict[str, List[Par]],
    pareados_b: Dict[str, List[Par]],
    comparaveis: Sequence[ParDeCampos],
) -> None:
    indice: Dict[str, List[Dict[str, Any]]] = {}
    for linha in consolidado_b.tabela.linhas:
        chave = _valor_chave(linha, campo_b)
        if chave:
            indice.setdefault(chave, []).append(linha)
    for linha_a in consolidado_a.tabela.linhas:
        if linha_a[COL_ID] in pareados_a:
            continue
        chave = _valor_chave(linha_a, campo_a)
        if not chave:
            continue
        for linha_b in indice.get(chave, []):
            if linha_b[COL_ID] in pareados_b and linha_a[COL_ID] in pareados_a:
                continue
            par = Par(
                id_a=linha_a[COL_ID],
                id_b=linha_b[COL_ID],
                tipo=tipo,
                chave_usada=rotulo,
                valor_chave=" + ".join(tx.limpar(linha_a.get(c)) for c in campo_a.split("+")),
                escore=1.0,
                linha_a=linha_a,
                linha_b=linha_b,
            )
            par.divergencias = _comparar_campos(linha_a, linha_b, comparaveis, campo_a, campo_b)
            resultado.pares.append(par)
            pareados_a.setdefault(linha_a[COL_ID], []).append(par)
            pareados_b.setdefault(linha_b[COL_ID], []).append(par)


def _parear_por_similaridade(
    restantes_a: List[Dict[str, Any]],
    restantes_b: List[Dict[str, Any]],
    campos_sim: List[Tuple[str, str]],
    perfil: Perfil,
    consolidado_a: Consolidado,
    consolidado_b: Consolidado,
    mapa_campos: Sequence[ParDeCampos] = (),
) -> List[Par]:
    if not campos_sim or not restantes_a or not restantes_b:
        return []
    limiar = perfil.pareamento.limiar_duvidoso
    indice_tokens = _indice_por_token(restantes_b, campos_sim, "b")
    forca = _campos_discriminantes(consolidado_a, mapa_campos)

    candidatos: List[Tuple[float, int, int, int, int]] = []
    for indice_a, linha_a in enumerate(restantes_a):
        for indice_b in _candidatos_do_bloco(linha_a, campos_sim, "a", indice_tokens):
            escore = _escore_similaridade(linha_a, restantes_b[indice_b], campos_sim)
            if escore < limiar:
                continue
            fortes, concordantes, comparaveis = _corroboracao(
                linha_a, restantes_b[indice_b], mapa_campos, campos_sim, forca
            )
            if not _aceitar_aproximado(escore, fortes, concordantes, comparaveis):
                continue
            candidatos.append((escore, indice_a, indice_b, concordantes, comparaveis))
    candidatos.sort(key=lambda item: (-item[3], -item[0]))

    usados_a, usados_b = set(), set()
    pares: List[Par] = []
    for escore, indice_a, indice_b, concordantes, comparaveis in candidatos:
        if indice_a in usados_a or indice_b in usados_b:
            continue
        usados_a.add(indice_a)
        usados_b.add(indice_b)
        linha_a, linha_b = restantes_a[indice_a], restantes_b[indice_b]
        confirmado = concordantes >= 1 or comparaveis == 0
        tipo = (
            TIPO_PROVAVEL
            if escore >= perfil.pareamento.limiar_provavel and confirmado
            else TIPO_DUVIDOSO
        )
        rotulo = " / ".join(f"{a}~{b}" for a, b in campos_sim)
        confirmacao = (
            f", confirmado por {concordantes} de {comparaveis} campo(s)"
            if comparaveis else ", sem outro campo para confirmar"
        )
        par = Par(
            id_a=linha_a[COL_ID],
            id_b=linha_b[COL_ID],
            tipo=tipo,
            chave_usada=f"similaridade ({rotulo}){confirmacao}",
            valor_chave=next(
                (tx.limpar(linha_a.get(campo)) for campo, _ in campos_sim
                 if tx.limpar(linha_a.get(campo))),
                "",
            ),
            escore=round(escore, 3),
            linha_a=linha_a,
            linha_b=linha_b,
        )
        par.divergencias = _comparar_campos(linha_a, linha_b, [], "", "")
        pares.append(par)
    return pares


LIMITE_CANDIDATOS = 200


def _indice_por_token(linhas, campos_sim, lado: str) -> Dict[str, List[int]]:
    """Indice invertido token -> posicoes, usado para reduzir comparacoes."""
    indice: Dict[str, List[int]] = {}
    if not campos_sim:
        return indice
    for posicao, linha in enumerate(linhas):
        for token in _tokens_bloqueio(linha, campos_sim, lado):
            indice.setdefault(token, []).append(posicao)
    return indice


def _candidatos_do_bloco(
    linha: Dict[str, Any],
    campos_sim,
    lado: str,
    indice: Dict[str, List[int]],
    limite: int = LIMITE_CANDIDATOS,
) -> List[int]:
    """Escolhe quais registros do outro lado merecem comparacao detalhada.

    Comeca pelos tokens mais raros: sobrenomes comuns como 'silva' aparecem em
    milhares de registros e, se fossem usados, o pareamento aproximado viraria
    uma comparacao de todos contra todos.
    """
    tokens = _tokens_bloqueio(linha, campos_sim, lado)
    if not tokens:
        return []
    ordenados = sorted(
        {t for t in tokens if t in indice}, key=lambda token: len(indice[token])
    )
    escolhidos: List[int] = []
    vistos = set()
    for token in ordenados:
        for posicao in indice[token]:
            if posicao not in vistos:
                vistos.add(posicao)
                escolhidos.append(posicao)
                if len(escolhidos) >= limite:
                    return escolhidos
    return escolhidos


LIMIAR_SEM_CONFIRMACAO = 0.97


def _campos_discriminantes(consolidado: Consolidado, mapa_campos) -> Dict[str, bool]:
    """Marca quais campos servem de prova: 'ATIVO/INATIVO' nao confirma nada."""
    forca: Dict[str, bool] = {}
    total = max(len(consolidado.tabela.linhas), 1)
    for par in mapa_campos:
        valores = {
            tx.normalizar(l.get(par.campo_a)) for l in consolidado.tabela.linhas
            if tx.limpar(l.get(par.campo_a))
        }
        forca[par.campo_a] = len(valores) >= 20 or len(valores) / total >= 0.5
    return forca


def _corroboracao(
    linha_a: Dict[str, Any],
    linha_b: Dict[str, Any],
    mapa_campos: Sequence[ParDeCampos],
    campos_sim: List[Tuple[str, str]],
    forca: Dict[str, bool],
) -> Tuple[int, int, int]:
    """Conta quantos outros campos confirmam que os dois registros sao o mesmo.

    Devolve (concordancias fortes, concordancias totais, campos comparaveis).
    """
    usados = {campo_a for campo_a, _ in campos_sim}
    fortes = concordantes = comparaveis = 0
    for par in mapa_campos:
        if par.campo_a in usados:
            continue
        valor_a = tx.limpar(linha_a.get(par.campo_a))
        valor_b = tx.limpar(linha_b.get(par.campo_b))
        if not valor_a or not valor_b:
            continue
        comparaveis += 1
        if _equivalentes(valor_a, valor_b, par.tipo):
            concordantes += 1
            if forca.get(par.campo_a):
                fortes += 1
    return fortes, concordantes, comparaveis


def _aceitar_aproximado(
    escore: float, fortes: int, concordantes: int, comparaveis: int
) -> bool:
    """Semelhanca de nome, sozinha, nao basta para afirmar que e a mesma pessoa.

    Homonimos e nomes proximos ('Maria dos Santos Silva' e 'Maria Santos da
    Silva') sao comuns; por isso, havendo outros campos comparaveis, e preciso
    ao menos uma coincidencia em campo discriminante (data de nascimento,
    codigo, documento) ou duas coincidencias em campos fracos. Sem nenhum campo
    de apoio, so um casamento praticamente perfeito e aceito.
    """
    if comparaveis == 0:
        return escore >= LIMIAR_SEM_CONFIRMACAO
    return fortes >= 1 or concordantes >= 2


def _tokens_bloqueio(linha: Dict[str, Any], campos_sim, lado: str) -> List[str]:
    tokens: List[str] = []
    for campo_a, campo_b in campos_sim:
        valor = tx.normalizar(linha.get(campo_a if lado == "a" else campo_b))
        for palavra in valor.split():
            if len(palavra) >= 3:
                tokens.append(palavra)
        if valor:
            tokens.append(valor[:4])
    return tokens[:20]


def _escore_similaridade(linha_a, linha_b, campos_sim) -> float:
    notas = []
    for campo_a, campo_b in campos_sim:
        valor_a, valor_b = tx.limpar(linha_a.get(campo_a)), tx.limpar(linha_b.get(campo_b))
        if not valor_a or not valor_b:
            continue
        notas.append(tx.similaridade(valor_a, valor_b))
    if not notas:
        return 0.0
    return sum(notas) / len(notas)


# --------------------------------------------------------------------------
# Comparacao campo a campo e itens sem par
# --------------------------------------------------------------------------


def _comparar_campos(
    linha_a: Dict[str, Any],
    linha_b: Dict[str, Any],
    mapa_campos: Sequence[ParDeCampos],
    chave_a: str,
    chave_b: str,
) -> List[Divergencia]:
    divergencias: List[Divergencia] = []
    campos_chave = set(chave_a.split("+")) if chave_a else set()
    for par in mapa_campos:
        if par.campo_a in campos_chave:
            continue
        valor_a = tx.limpar(linha_a.get(par.campo_a))
        valor_b = tx.limpar(linha_b.get(par.campo_b))
        if not valor_a and not valor_b:
            continue
        if _equivalentes(valor_a, valor_b, par.tipo):
            continue
        divergencias.append(Divergencia(par.campo_a, par.campo_b, valor_a, valor_b))
    return divergencias


def _equivalentes(valor_a: str, valor_b: str, tipo: str) -> bool:
    if tx.normalizar(valor_a) == tx.normalizar(valor_b):
        return True
    if tipo in ("cpf", "cnpj", "cpf_cnpj", "codigo", "cep", "telefone"):
        return tx.so_digitos(valor_a).lstrip("0") == tx.so_digitos(valor_b).lstrip("0") != ""
    if tipo == "data":
        data_a, data_b = tx.para_data(valor_a), tx.para_data(valor_b)
        return data_a is not None and data_a == data_b
    if tipo == "numero":
        numero_a, numero_b = tx.para_numero(valor_a), tx.para_numero(valor_b)
        if numero_a is None or numero_b is None:
            return False
        return abs(numero_a - numero_b) <= max(0.005, abs(numero_a) * 0.0001)
    return False


def _marcar_multiplicidade(
    resultado: ResultadoPareamento,
    pareados_a: Dict[str, List[Par]],
    pareados_b: Dict[str, List[Par]],
) -> None:
    for par in resultado.pares:
        quantidade_a = len(pareados_a.get(par.id_a, []))
        quantidade_b = len(pareados_b.get(par.id_b, []))
        if quantidade_a > 1 or quantidade_b > 1:
            par.multiplicidade = f"{quantidade_a}:{quantidade_b} (revisar duplicidade)"


def _listar_nao_pareados(
    consolidado_a: Consolidado,
    consolidado_b: Consolidado,
    pareados_a: Dict[str, List[Par]],
    pareados_b: Dict[str, List[Par]],
    campos_sim: List[Tuple[str, str]],
    resultado: ResultadoPareamento,
) -> None:
    restantes_b = [l for l in consolidado_b.tabela.linhas if l[COL_ID] not in pareados_b]
    restantes_a = [l for l in consolidado_a.tabela.linhas if l[COL_ID] not in pareados_a]
    chave_a = resultado.chaves_usadas[0][0] if resultado.chaves_usadas else ""
    chave_b = resultado.chaves_usadas[0][1] if resultado.chaves_usadas else ""

    # Indices por token: sem eles, procurar o "mais parecido" viraria uma
    # comparacao de todos contra todos, inviavel em bases grandes.
    indice_b = _indice_por_token(restantes_b, campos_sim, "b")
    indice_a = _indice_por_token(restantes_a, campos_sim, "a")

    for linha in restantes_a:
        melhor, escore = _mais_parecido(linha, restantes_b, campos_sim, "a", indice_b)
        resultado.somente_a.append(NaoPareado(
            linha=linha,
            motivo=_motivo_ausencia(linha, chave_a, consolidado_b.nome, escore),
            melhor_candidato=melhor,
            escore_candidato=escore,
        ))
    for linha in restantes_b:
        melhor, escore = _mais_parecido(linha, restantes_a, campos_sim, "b", indice_a)
        resultado.somente_b.append(NaoPareado(
            linha=linha,
            motivo=_motivo_ausencia(linha, chave_b, consolidado_a.nome, escore),
            melhor_candidato=melhor,
            escore_candidato=escore,
        ))


def _motivo_ausencia(linha, campo_chave: str, nome_oposto: str, escore: float) -> str:
    partes = [c for c in campo_chave.split("+") if c] if campo_chave else []
    vazios = [c for c in partes if not tx.limpar(linha.get(c))]
    if vazios:
        return (
            f"Registro sem valor em {', '.join(repr(c) for c in vazios)}, que compoe a "
            f"chave de busca, o que impede localiza-lo em {nome_oposto}."
        )
    valor = " + ".join(tx.limpar(linha.get(c)) for c in partes)
    rotulo = " + ".join(partes)
    inicio = (
        f"Chave '{rotulo}' = {valor} nao encontrada em {nome_oposto}"
        if partes else f"Nenhuma correspondencia encontrada em {nome_oposto}"
    )
    if escore >= 0.60:
        return f"{inicio}; ha um registro parecido ({escore:.0%}), abaixo do limite de aceite."
    return f"{inicio}; nenhum registro semelhante foi localizado."


def _mais_parecido(
    linha, candidatos, campos_sim, lado: str, indice: Dict[str, List[int]]
) -> Tuple[str, float]:
    """Registro mais parecido do outro sistema, para explicar a ausencia."""
    if not campos_sim or not candidatos:
        return "", 0.0
    invertidos = [(b, a) for a, b in campos_sim] if lado == "b" else campos_sim
    melhor_texto, melhor_escore = "", 0.0
    campo_mostrar = campos_sim[0][1] if lado == "a" else campos_sim[0][0]
    for posicao in _candidatos_do_bloco(linha, campos_sim, lado, indice):
        candidato = candidatos[posicao]
        escore = _escore_similaridade(linha, candidato, invertidos)
        if escore > melhor_escore:
            melhor_escore = escore
            melhor_texto = f"{candidato[COL_ID]}: {tx.limpar(candidato.get(campo_mostrar))}"
    return melhor_texto, round(melhor_escore, 3)
