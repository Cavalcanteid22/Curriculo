"""Analise dos atributos de qualidade de uma tabela consolidada.

Dimensoes avaliadas (alinhadas ao vocabulario usual de qualidade de dados):

- Completude .......... campos preenchidos
- Unicidade ........... duplicidade de chave e de registro inteiro
- Validade ............ formato/dominio (CPF, CNPJ, data, numero, e-mail, lista)
- Consistencia ........ regras entre campos (ex.: data final >= data inicial)
- Padronizacao ........ mesma informacao escrita de maneiras diferentes
- Acuracia ............ valores implausiveis (outliers, datas fora da faixa)
- Atualidade .......... quao recente e a informacao
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import texto as tx
from .config import CampoConfig, Perfil
from .normalizacao import COL_ARQUIVO, COL_ID, COL_LINHA, Consolidado

DIMENSOES = (
    "Completude", "Unicidade", "Validade", "Consistencia",
    "Padronizacao", "Acuracia", "Atualidade",
)
PESOS = {
    "Completude": 0.25, "Unicidade": 0.20, "Validade": 0.25,
    "Consistencia": 0.10, "Padronizacao": 0.10, "Acuracia": 0.05,
    "Atualidade": 0.05,
}
GRAVIDADE_ALTA, GRAVIDADE_MEDIA, GRAVIDADE_BAIXA = "Alta", "Media", "Baixa"


@dataclass
class Ocorrencia:
    id_registro: str
    arquivo: str
    linha: Any
    campo: str
    dimensao: str
    gravidade: str
    descricao: str
    valor: str = ""


@dataclass
class MetricaCampo:
    campo: str
    tipo: str
    total: int = 0
    preenchidos: int = 0
    distintos: int = 0
    invalidos: int = 0
    duplicados: int = 0
    variacoes_grafia: int = 0
    fora_dominio: int = 0
    implausiveis: int = 0
    exemplos: List[str] = field(default_factory=list)
    chave: bool = False

    @property
    def completude(self) -> float:
        return 100.0 * self.preenchidos / self.total if self.total else 0.0

    @property
    def validade(self) -> float:
        if not self.preenchidos:
            return 100.0
        return 100.0 * (self.preenchidos - self.invalidos - self.fora_dominio) / self.preenchidos

    @property
    def unicidade(self) -> float:
        if not self.preenchidos:
            return 100.0
        return 100.0 * self.distintos / self.preenchidos

    @property
    def nota(self) -> float:
        nota = 0.45 * self.completude + 0.35 * self.validade
        nota += 0.10 * (100.0 - min(100.0, 100.0 * self.variacoes_grafia / max(self.preenchidos, 1)))
        nota += 0.10 * (100.0 - min(100.0, 100.0 * self.implausiveis / max(self.preenchidos, 1)))
        if self.chave:
            nota = min(nota, self.unicidade)
        return round(nota, 1)

    @property
    def classificacao(self) -> str:
        return classificar(self.nota)


@dataclass
class ResultadoQualidade:
    sistema_id: str
    nome: str
    metricas: List[MetricaCampo] = field(default_factory=list)
    ocorrencias: List[Ocorrencia] = field(default_factory=list)
    notas_dimensao: Dict[str, float] = field(default_factory=dict)
    nota_geral: float = 0.0
    total_registros: int = 0
    registros_com_problema: int = 0
    registros_duplicados: int = 0
    resumo_texto: List[str] = field(default_factory=list)

    def por_dimensao(self) -> Dict[str, int]:
        contagem = {d: 0 for d in DIMENSOES}
        for ocorrencia in self.ocorrencias:
            contagem[ocorrencia.dimensao] = contagem.get(ocorrencia.dimensao, 0) + 1
        return contagem

    def por_gravidade(self) -> Dict[str, int]:
        contagem = {GRAVIDADE_ALTA: 0, GRAVIDADE_MEDIA: 0, GRAVIDADE_BAIXA: 0}
        for ocorrencia in self.ocorrencias:
            contagem[ocorrencia.gravidade] = contagem.get(ocorrencia.gravidade, 0) + 1
        return contagem


def classificar(nota: float) -> str:
    if nota >= 95:
        return "Excelente"
    if nota >= 85:
        return "Bom"
    if nota >= 70:
        return "Regular"
    if nota >= 50:
        return "Ruim"
    return "Critico"


# --------------------------------------------------------------------------
# Analise
# --------------------------------------------------------------------------


def analisar(consolidado: Consolidado, perfil: Perfil) -> ResultadoQualidade:
    resultado = ResultadoQualidade(sistema_id=consolidado.sistema_id, nome=consolidado.nome)
    tabela = consolidado.tabela
    resultado.total_registros = len(tabela.linhas)
    if not tabela.linhas:
        resultado.resumo_texto.append("Nenhum registro foi consolidado para este sistema.")
        return resultado

    limite_inferior = tx.para_data(perfil.qualidade.data_minima) or _dt.date(1900, 1, 1)
    limite_superior = tx.para_data(perfil.qualidade.data_maxima) or _dt.date.today()

    for campo in consolidado.campos:
        metrica = _analisar_campo(
            tabela, campo, resultado, limite_inferior, limite_superior, perfil
        )
        resultado.metricas.append(metrica)

    _verificar_registros_duplicados(consolidado, resultado)
    _verificar_regras_consistencia(consolidado, perfil, resultado)
    _calcular_notas(resultado, consolidado)
    _montar_resumo(resultado, consolidado, limite_superior)
    return resultado


def _analisar_campo(
    tabela,
    campo: CampoConfig,
    resultado: ResultadoQualidade,
    limite_inferior: _dt.date,
    limite_superior: _dt.date,
    perfil: Perfil,
) -> MetricaCampo:
    metrica = MetricaCampo(campo=campo.nome, tipo=campo.tipo, chave=campo.chave)
    metrica.total = len(tabela.linhas)
    vistos: Dict[str, str] = {}       # normalizado -> primeira grafia encontrada
    contagem_chave: Dict[str, List[dict]] = {}
    numeros: List[Tuple[float, dict]] = []
    dominio = {tx.normalizar(v) for v in campo.dominio} if campo.dominio else set()

    for linha in tabela.linhas:
        bruto = tx.limpar(linha.get(campo.nome))
        if not bruto:
            if campo.obrigatorio:
                _registrar(resultado, linha, campo.nome, "Completude", GRAVIDADE_ALTA,
                           "Campo obrigatorio nao preenchido", "")
            continue
        metrica.preenchidos += 1
        chave = tx.normalizar(bruto)

        if chave in vistos:
            if vistos[chave] != bruto:
                metrica.variacoes_grafia += 1
                _registrar(resultado, linha, campo.nome, "Padronizacao", GRAVIDADE_BAIXA,
                           f"Grafia divergente de '{vistos[chave]}' para o mesmo conteudo", bruto)
        else:
            vistos[chave] = bruto

        if bruto != str(linha.get(campo.nome, "")).strip() or "  " in str(linha.get(campo.nome, "")):
            metrica.variacoes_grafia += 1
            _registrar(resultado, linha, campo.nome, "Padronizacao", GRAVIDADE_BAIXA,
                       "Espacos extras no inicio, no fim ou entre palavras", bruto)

        problema = _validar_valor(bruto, campo)
        if problema:
            metrica.invalidos += 1
            if len(metrica.exemplos) < 5:
                metrica.exemplos.append(bruto[:40])
            gravidade = GRAVIDADE_ALTA if campo.tipo in ("cpf", "cnpj", "cpf_cnpj") or campo.chave \
                else GRAVIDADE_MEDIA
            _registrar(resultado, linha, campo.nome, "Validade", gravidade, problema, bruto)

        if dominio and chave not in dominio:
            metrica.fora_dominio += 1
            _registrar(resultado, linha, campo.nome, "Validade", GRAVIDADE_MEDIA,
                       "Valor fora da lista de valores aceitos", bruto)

        if campo.tipo == "data":
            data = tx.para_data(bruto)
            if data and not (limite_inferior <= data <= limite_superior):
                metrica.implausiveis += 1
                _registrar(resultado, linha, campo.nome, "Acuracia", GRAVIDADE_MEDIA,
                           f"Data fora da faixa plausivel ({limite_inferior:%d/%m/%Y} a "
                           f"{limite_superior:%d/%m/%Y})", bruto)
        elif campo.tipo == "numero":
            numero = tx.para_numero(bruto)
            if numero is not None:
                numeros.append((numero, linha))
                if campo.minimo is not None and numero < campo.minimo:
                    metrica.implausiveis += 1
                    _registrar(resultado, linha, campo.nome, "Acuracia", GRAVIDADE_MEDIA,
                               f"Valor abaixo do minimo previsto ({campo.minimo})", bruto)
                if campo.maximo is not None and numero > campo.maximo:
                    metrica.implausiveis += 1
                    _registrar(resultado, linha, campo.nome, "Acuracia", GRAVIDADE_MEDIA,
                               f"Valor acima do maximo previsto ({campo.maximo})", bruto)

        if campo.tamanho_minimo and len(bruto) < campo.tamanho_minimo:
            metrica.invalidos += 1
            _registrar(resultado, linha, campo.nome, "Validade", GRAVIDADE_MEDIA,
                       f"Texto menor que o tamanho minimo ({campo.tamanho_minimo})", bruto)
        if campo.tamanho_maximo and len(bruto) > campo.tamanho_maximo:
            metrica.invalidos += 1
            _registrar(resultado, linha, campo.nome, "Validade", GRAVIDADE_BAIXA,
                       f"Texto maior que o tamanho maximo ({campo.tamanho_maximo})", bruto)

        if campo.chave or campo.unico:
            contagem_chave.setdefault(chave, []).append(linha)

    metrica.distintos = len(vistos)

    for chave, linhas in contagem_chave.items():
        if len(linhas) > 1:
            metrica.duplicados += len(linhas)
            identificadores = ", ".join(str(l.get(COL_ID)) for l in linhas[:6])
            for linha in linhas:
                _registrar(resultado, linha, campo.nome, "Unicidade", GRAVIDADE_ALTA,
                           f"Valor repetido em {len(linhas)} registros ({identificadores})",
                           tx.limpar(linha.get(campo.nome)))

    if perfil.qualidade.detectar_outliers and len(numeros) >= 12:
        for numero, linha in _detectar_outliers(numeros):
            metrica.implausiveis += 1
            _registrar(resultado, linha, campo.nome, "Acuracia", GRAVIDADE_BAIXA,
                       "Valor muito distante da faixa usual da coluna (possivel outlier)",
                       tx.formatar_numero(numero))
    return metrica


def _validar_valor(valor: str, campo: CampoConfig) -> str:
    tipo = campo.tipo
    if tipo == "cpf":
        if not tx.cpf_valido(valor):
            digitos = tx.so_digitos(valor)
            if len(digitos) != 11:
                return f"CPF com {len(digitos)} digitos (esperado 11)"
            return "CPF com digito verificador invalido"
    elif tipo == "cnpj":
        if not tx.cnpj_valido(valor):
            digitos = tx.so_digitos(valor)
            if len(digitos) != 14:
                return f"CNPJ com {len(digitos)} digitos (esperado 14)"
            return "CNPJ com digito verificador invalido"
    elif tipo == "cpf_cnpj":
        digitos = tx.so_digitos(valor)
        if len(digitos) == 11 and not tx.cpf_valido(valor):
            return "CPF com digito verificador invalido"
        if len(digitos) == 14 and not tx.cnpj_valido(valor):
            return "CNPJ com digito verificador invalido"
        if len(digitos) not in (11, 14):
            return f"Documento com {len(digitos)} digitos (esperado 11 ou 14)"
    elif tipo == "email":
        if not tx.email_valido(valor):
            return "E-mail em formato invalido"
    elif tipo == "cep":
        if not tx.cep_valido(valor):
            return f"CEP com {len(tx.so_digitos(valor))} digitos (esperado 8)"
    elif tipo == "telefone":
        if not tx.telefone_valido(valor):
            return "Telefone com quantidade de digitos improvavel"
    elif tipo == "data":
        if tx.para_data(valor) is None:
            return "Data em formato nao reconhecido"
    elif tipo == "numero":
        if tx.para_numero(valor) is None:
            return "Valor numerico em formato nao reconhecido"
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", valor):
        return "Contem caracteres de controle invalidos"
    if tipo in ("texto", "categoria") and re.fullmatch(r"[-_.\s/]+", valor):
        return "Conteudo sem informacao util (apenas simbolos)"
    return ""


def _detectar_outliers(numeros: List[Tuple[float, dict]]) -> List[Tuple[float, dict]]:
    valores = sorted(n for n, _ in numeros)
    quantidade = len(valores)
    q1 = valores[quantidade // 4]
    q3 = valores[(3 * quantidade) // 4]
    intervalo = q3 - q1
    if intervalo <= 0:
        return []
    inferior, superior = q1 - 3 * intervalo, q3 + 3 * intervalo
    return [(n, linha) for n, linha in numeros if n < inferior or n > superior][:50]


def _verificar_registros_duplicados(consolidado: Consolidado, resultado: ResultadoQualidade) -> None:
    """Registros identicos em todas as colunas de dados."""
    vistos: Dict[Tuple, List[dict]] = {}
    for linha in consolidado.tabela.linhas:
        assinatura = tuple(tx.normalizar(linha.get(c)) for c in consolidado.colunas_dados)
        if not any(assinatura):
            continue
        vistos.setdefault(assinatura, []).append(linha)
    for linhas in vistos.values():
        if len(linhas) > 1:
            resultado.registros_duplicados += len(linhas) - 1
            identificadores = ", ".join(str(l.get(COL_ID)) for l in linhas[:6])
            for linha in linhas[1:]:
                _registrar(resultado, linha, "(registro inteiro)", "Unicidade", GRAVIDADE_ALTA,
                           f"Registro identico a outro(s) do mesmo sistema ({identificadores})", "")


def _verificar_regras_consistencia(
    consolidado: Consolidado, perfil: Perfil, resultado: ResultadoQualidade
) -> None:
    for regra in perfil.qualidade.regras_consistencia:
        if regra.campo_a not in consolidado.tabela.colunas:
            continue
        for linha in consolidado.tabela.linhas:
            valor_a = tx.limpar(linha.get(regra.campo_a))
            valor_b = tx.limpar(linha.get(regra.campo_b)) if regra.campo_b else regra.valor
            if not valor_a or not valor_b:
                continue
            if not _comparar(valor_a, valor_b, regra.operador):
                descricao = regra.descricao or (
                    f"{regra.campo_a} ({valor_a}) deveria ser {regra.operador} "
                    f"{regra.campo_b or regra.valor} ({valor_b})"
                )
                _registrar(resultado, linha, regra.campo_a, "Consistencia", GRAVIDADE_MEDIA,
                           descricao, valor_a)


def _comparar(valor_a: str, valor_b: str, operador: str) -> bool:
    esquerda: Any = tx.para_data(valor_a) or tx.para_numero(valor_a)
    direita: Any = tx.para_data(valor_b) or tx.para_numero(valor_b)
    if esquerda is None or direita is None or type(esquerda) is not type(direita):
        esquerda, direita = tx.normalizar(valor_a), tx.normalizar(valor_b)
    try:
        return {
            ">=": lambda: esquerda >= direita,
            "<=": lambda: esquerda <= direita,
            ">": lambda: esquerda > direita,
            "<": lambda: esquerda < direita,
            "==": lambda: esquerda == direita,
            "!=": lambda: esquerda != direita,
        }.get(operador, lambda: True)()
    except TypeError:
        return True


def _registrar(
    resultado: ResultadoQualidade,
    linha: dict,
    campo: str,
    dimensao: str,
    gravidade: str,
    descricao: str,
    valor: str,
) -> None:
    resultado.ocorrencias.append(Ocorrencia(
        id_registro=str(linha.get(COL_ID, "")),
        arquivo=str(linha.get(COL_ARQUIVO, "")),
        linha=linha.get(COL_LINHA, ""),
        campo=campo,
        dimensao=dimensao,
        gravidade=gravidade,
        descricao=descricao,
        valor=str(valor)[:200],
    ))


def _calcular_notas(resultado: ResultadoQualidade, consolidado: Consolidado) -> None:
    total = max(resultado.total_registros, 1)
    campos = max(len(resultado.metricas), 1)
    celulas = total * campos

    completude = sum(m.completude for m in resultado.metricas) / campos
    validade = sum(m.validade for m in resultado.metricas) / campos
    chaves = [m for m in resultado.metricas if m.chave] or resultado.metricas
    unicidade = sum(m.unicidade for m in chaves) / len(chaves)
    unicidade = min(unicidade, 100.0 * (total - resultado.registros_duplicados) / total)

    contagem = resultado.por_dimensao()
    padronizacao = 100.0 * (1 - min(1.0, contagem.get("Padronizacao", 0) / celulas))
    consistencia = 100.0 * (1 - min(1.0, contagem.get("Consistencia", 0) / total))
    acuracia = 100.0 * (1 - min(1.0, contagem.get("Acuracia", 0) / celulas))

    resultado.notas_dimensao = {
        "Completude": round(completude, 1),
        "Unicidade": round(unicidade, 1),
        "Validade": round(validade, 1),
        "Consistencia": round(consistencia, 1),
        "Padronizacao": round(padronizacao, 1),
        "Acuracia": round(acuracia, 1),
        "Atualidade": round(_nota_atualidade(consolidado), 1),
    }
    resultado.nota_geral = round(
        sum(resultado.notas_dimensao[d] * PESOS[d] for d in DIMENSOES), 1
    )
    resultado.registros_com_problema = len({o.id_registro for o in resultado.ocorrencias if o.id_registro})


def _nota_atualidade(consolidado: Consolidado) -> float:
    datas = []
    for campo in consolidado.campos:
        if campo.tipo != "data":
            continue
        for linha in consolidado.tabela.linhas:
            data = tx.para_data(linha.get(campo.nome))
            if data:
                datas.append(data)
    if not datas:
        return 100.0
    mais_recente = max(datas)
    dias = (_dt.date.today() - mais_recente).days
    if dias <= 45:
        return 100.0
    if dias <= 180:
        return 90.0
    if dias <= 365:
        return 75.0
    if dias <= 730:
        return 60.0
    return 40.0


def _montar_resumo(
    resultado: ResultadoQualidade, consolidado: Consolidado, limite_superior: _dt.date
) -> None:
    texto = resultado.resumo_texto
    contagem = resultado.por_gravidade()
    texto.append(
        f"{resultado.total_registros} registros e {len(consolidado.colunas_dados)} colunas "
        f"analisados; nota geral de qualidade {resultado.nota_geral:.1f} "
        f"({classificar(resultado.nota_geral)})."
    )
    texto.append(
        f"{len(resultado.ocorrencias)} ocorrencias registradas em "
        f"{resultado.registros_com_problema} registros distintos "
        f"({contagem[GRAVIDADE_ALTA]} de gravidade alta, {contagem[GRAVIDADE_MEDIA]} media, "
        f"{contagem[GRAVIDADE_BAIXA]} baixa)."
    )
    piores = sorted(resultado.metricas, key=lambda m: m.nota)[:3]
    if piores:
        detalhes = "; ".join(f"{m.campo} ({m.nota:.0f})" for m in piores)
        texto.append(f"Campos com menor nota: {detalhes}.")
    if resultado.registros_duplicados:
        texto.append(
            f"{resultado.registros_duplicados} registros sao copias identicas de outros."
        )
