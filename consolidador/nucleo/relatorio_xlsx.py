"""Montagem da planilha final com todas as abas pedidas.

Abas geradas, nesta ordem:

1. Resumo ........................ painel executivo da execucao
2. Consolidado <Sistema 1> ....... todos os registros do primeiro sistema
3. Consolidado <Sistema 2> ....... todos os registros do segundo sistema
4. Qualidade <Sistema 1> ......... indicadores + ocorrencias
5. Qualidade <Sistema 2> ......... indicadores + ocorrencias
6. Pareamento .................... registros casados, campo a campo
7. Somente em <Sistema 1> ........ o que existe no 1 e nao existe no 2
8. Somente em <Sistema 2> ........ o que existe no 2 e nao existe no 1
9. Arquivos lidos ................ auditoria da origem dos dados
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import texto as tx
from .normalizacao import COL_ARQUIVO, COL_ID, COL_LINHA, Consolidado
from .pareamento import Par, ResultadoPareamento
from .qualidade import (GRAVIDADE_ALTA, GRAVIDADE_BAIXA, GRAVIDADE_MEDIA,
                        DIMENSOES, ResultadoQualidade, classificar)
from .resultado import ResultadoGeral
from .xlsx_writer import Estilo, Planilha

# Paleta
AZUL = "1F4E79"
AZUL_MEDIO = "2E75B6"
AZUL_CLARO = "DDEBF7"
CINZA_CLARO = "F2F2F2"
VERMELHO = "FADBD8"
VERMELHO_TEXTO = "922B21"
AMBAR = "FFF2CC"
AMBAR_TEXTO = "7F6000"
VERDE = "E2EFDA"
VERDE_TEXTO = "375623"
LARANJA = "FCE4D6"
ROXO_CLARO = "E4DFEC"

# Estilos reutilizados
E_TITULO = Estilo(negrito=True, tamanho=14, cor=AZUL)
E_SUBTITULO = Estilo(italico=True, tamanho=9, cor="595959")
E_CABECALHO = Estilo(negrito=True, cor="FFFFFF", fundo=AZUL, borda=True, quebra=True,
                     alinhamento="center", vertical="center")
E_CABECALHO_A = E_CABECALHO.com(fundo=AZUL_MEDIO)
E_CABECALHO_B = E_CABECALHO.com(fundo="548235")
E_DADO = Estilo(borda=True, vertical="top")
E_DADO_ZEBRA = E_DADO.com(fundo="FAFAFA")
E_NUMERO = E_DADO.com(formato="decimal", alinhamento="right")
E_DATA = E_DADO.com(formato="data", alinhamento="center")
E_ROTULO = Estilo(negrito=True, cor="404040")
E_SECAO = Estilo(negrito=True, tamanho=11, cor="FFFFFF", fundo=AZUL_MEDIO, borda=True,
                 alinhamento="left")
E_ALERTA_ALTO = E_DADO.com(fundo=VERMELHO, cor=VERMELHO_TEXTO)
E_ALERTA_MEDIO = E_DADO.com(fundo=AMBAR, cor=AMBAR_TEXTO)
E_ALERTA_BAIXO = E_DADO.com(fundo=CINZA_CLARO)
E_OK = E_DADO.com(fundo=VERDE, cor=VERDE_TEXTO)
E_DIVERGENTE = E_DADO.com(fundo=AMBAR, cor=AMBAR_TEXTO, negrito=True)
E_SOMENTE_A = E_DADO.com(fundo=LARANJA, cor=VERMELHO_TEXTO)
E_SOMENTE_B = E_DADO.com(fundo=AZUL_CLARO, cor="1F4E79")

ESTILO_GRAVIDADE = {
    GRAVIDADE_ALTA: E_ALERTA_ALTO,
    GRAVIDADE_MEDIA: E_ALERTA_MEDIO,
    GRAVIDADE_BAIXA: E_ALERTA_BAIXO,
}
LIMITE_COLUNAS_PAREAMENTO = 25


def gerar(resultado: ResultadoGeral, caminho: str) -> str:
    planilha = Planilha()
    planilha.titulo = f"Consolidacao {resultado.nome_a} x {resultado.nome_b}"
    _aba_resumo(planilha, resultado)
    for consolidado, qualidade, lado in (
        (resultado.consolidado_a, resultado.qualidade_a, "A"),
        (resultado.consolidado_b, resultado.qualidade_b, "B"),
    ):
        if consolidado:
            _aba_consolidado(planilha, consolidado, resultado, lado)
    for consolidado, qualidade in (
        (resultado.consolidado_a, resultado.qualidade_a),
        (resultado.consolidado_b, resultado.qualidade_b),
    ):
        if consolidado and qualidade:
            _aba_qualidade(planilha, consolidado, qualidade)
    if resultado.pareamento:
        _aba_pareamento(planilha, resultado)
        _aba_somente(planilha, resultado, "A")
        _aba_somente(planilha, resultado, "B")
    _aba_arquivos(planilha, resultado)
    planilha.salvar(caminho)
    return caminho


# --------------------------------------------------------------------------
# Apoio
# --------------------------------------------------------------------------


def _nome_aba(prefixo: str, nome: str) -> str:
    disponivel = 31 - len(prefixo) - 1
    return f"{prefixo} {nome[:disponivel]}".strip()


def _valor_tipado(bruto: Any, tipo: str) -> Tuple[Any, Optional[Estilo]]:
    """Converte para numero/data quando possivel, devolvendo o estilo adequado."""
    texto = tx.limpar(bruto)
    if not texto:
        return "", None
    if tipo == "numero":
        numero = tx.para_numero(texto)
        if numero is not None:
            return numero, E_NUMERO
    elif tipo == "data":
        data = tx.para_data(texto)
        if data is not None:
            return data, E_DATA
    return texto, None


def _titulo_aba(aba, titulo: str, subtitulo: str, colunas: int) -> int:
    aba.escrever(0, 0, titulo, E_TITULO)
    aba.escrever(1, 0, subtitulo, E_SUBTITULO)
    if colunas > 1:
        aba.mesclar(0, 0, 0, colunas - 1)
        aba.mesclar(1, 0, 1, colunas - 1)
    aba.pular_linha(3)
    return 3


def _escrever_cabecalho(aba, linha: int, colunas: Sequence[str], estilo: Estilo = E_CABECALHO) -> None:
    for indice, nome in enumerate(colunas):
        aba.escrever(linha, indice, nome, estilo)
    aba.alturas[linha] = 30.0


def _estilo_nota(nota: float) -> Estilo:
    if nota >= 95:
        return E_OK
    if nota >= 85:
        return E_DADO.com(fundo="EBF7E4")
    if nota >= 70:
        return E_ALERTA_MEDIO
    return E_ALERTA_ALTO


# --------------------------------------------------------------------------
# Aba 1 - Resumo
# --------------------------------------------------------------------------


def _aba_resumo(planilha: Planilha, resultado: ResultadoGeral) -> None:
    aba = planilha.aba("Resumo")
    estatisticas = resultado.estatisticas()
    linha = _titulo_aba(
        aba,
        f"Consolidacao e analise comparativa: {resultado.nome_a} x {resultado.nome_b}",
        f"Gerado em {resultado.inicio:%d/%m/%Y as %H:%M} - "
        f"{len(resultado.arquivos)} arquivo(s) processado(s) em {resultado.duracao_segundos:.1f}s",
        6,
    )

    aba.escrever(linha, 0, "1. Volumes", E_SECAO)
    aba.mesclar(linha, 0, linha, 5)
    linha += 1
    cabecalho = ["Indicador", resultado.nome_a, resultado.nome_b]
    _escrever_cabecalho(aba, linha, cabecalho)
    linha += 1
    dados_volume = [
        ("Registros consolidados", estatisticas["registros_a"], estatisticas["registros_b"]),
        ("Colunas identificadas",
         len(resultado.consolidado_a.colunas_dados) if resultado.consolidado_a else 0,
         len(resultado.consolidado_b.colunas_dados) if resultado.consolidado_b else 0),
        ("Arquivos de origem",
         len(resultado.consolidado_a.arquivos) if resultado.consolidado_a else 0,
         len(resultado.consolidado_b.arquivos) if resultado.consolidado_b else 0),
        ("Registros pareados com o outro sistema",
         estatisticas["registros_a"] - estatisticas["somente_a"],
         estatisticas["registros_b"] - estatisticas["somente_b"]),
        ("Registros exclusivos", estatisticas["somente_a"], estatisticas["somente_b"]),
        ("Cobertura do pareamento",
         f"{estatisticas['cobertura_a']:.1f}%", f"{estatisticas['cobertura_b']:.1f}%"),
    ]
    for rotulo, valor_a, valor_b in dados_volume:
        aba.escrever(linha, 0, rotulo, E_DADO.com(negrito=True))
        aba.escrever(linha, 1, valor_a, E_DADO.com(alinhamento="center"))
        aba.escrever(linha, 2, valor_b, E_DADO.com(alinhamento="center"))
        linha += 1
    linha += 1

    aba.escrever(linha, 0, "2. Qualidade dos dados por dimensao (0 a 100)", E_SECAO)
    aba.mesclar(linha, 0, linha, 5)
    linha += 1
    _escrever_cabecalho(aba, linha, ["Dimensao", resultado.nome_a, resultado.nome_b, "Leitura"])
    linha += 1
    explicacoes = {
        "Completude": "Percentual de campos efetivamente preenchidos",
        "Unicidade": "Ausencia de duplicidade de chave e de registros repetidos",
        "Validade": "Conformidade de formato e de dominio (CPF, datas, listas)",
        "Consistencia": "Coerencia entre campos do mesmo registro",
        "Padronizacao": "Mesma informacao sempre escrita da mesma forma",
        "Acuracia": "Ausencia de valores implausiveis e de outliers",
        "Atualidade": "Quao recente e a informacao mais nova da base",
    }
    for dimensao in DIMENSOES:
        nota_a = resultado.qualidade_a.notas_dimensao.get(dimensao, 0.0) if resultado.qualidade_a else 0.0
        nota_b = resultado.qualidade_b.notas_dimensao.get(dimensao, 0.0) if resultado.qualidade_b else 0.0
        aba.escrever(linha, 0, dimensao, E_DADO.com(negrito=True))
        aba.escrever(linha, 1, round(nota_a, 1), _estilo_nota(nota_a).com(alinhamento="center"))
        aba.escrever(linha, 2, round(nota_b, 1), _estilo_nota(nota_b).com(alinhamento="center"))
        aba.escrever(linha, 3, explicacoes[dimensao], E_DADO)
        linha += 1
    nota_a = resultado.qualidade_a.nota_geral if resultado.qualidade_a else 0.0
    nota_b = resultado.qualidade_b.nota_geral if resultado.qualidade_b else 0.0
    aba.escrever(linha, 0, "NOTA GERAL", E_DADO.com(negrito=True, fundo=CINZA_CLARO))
    aba.escrever(linha, 1, round(nota_a, 1), _estilo_nota(nota_a).com(negrito=True, alinhamento="center"))
    aba.escrever(linha, 2, round(nota_b, 1), _estilo_nota(nota_b).com(negrito=True, alinhamento="center"))
    aba.escrever(linha, 3, f"{classificar(nota_a)} x {classificar(nota_b)}",
                 E_DADO.com(negrito=True))
    linha += 2

    aba.escrever(linha, 0, "3. Pareamento entre os sistemas", E_SECAO)
    aba.mesclar(linha, 0, linha, 5)
    linha += 1
    _escrever_cabecalho(aba, linha, ["Situacao", "Registros", "Observacao"])
    linha += 1
    pareamento = resultado.pareamento
    contagem = pareamento.contagem_por_tipo() if pareamento else {}
    itens_pareamento = [
        ("Pares encontrados", estatisticas["pares"],
         "; ".join(f"{tipo}: {quantidade}" for tipo, quantidade in contagem.items()) or "-"),
        ("Pares com divergencia de conteudo", estatisticas["divergentes"],
         "Mesmo registro, informacao diferente entre os sistemas"),
        (f"Somente em {resultado.nome_a}", estatisticas["somente_a"],
         f"Nao localizados em {resultado.nome_b}"),
        (f"Somente em {resultado.nome_b}", estatisticas["somente_b"],
         f"Nao localizados em {resultado.nome_a}"),
    ]
    for rotulo, valor, observacao in itens_pareamento:
        estilo = E_DADO
        if "Somente" in rotulo and valor:
            estilo = E_SOMENTE_A if resultado.nome_a in rotulo else E_SOMENTE_B
        elif "divergencia" in rotulo and valor:
            estilo = E_DIVERGENTE
        aba.escrever(linha, 0, rotulo, E_DADO.com(negrito=True))
        aba.escrever(linha, 1, valor, estilo.com(alinhamento="center"))
        aba.escrever(linha, 2, observacao, E_DADO)
        linha += 1
    if pareamento and pareamento.chaves_usadas:
        linha += 1
        aba.escrever(linha, 0, "Chave(s) utilizada(s):", E_ROTULO)
        aba.escrever(linha, 1, "; ".join(f"{a} = {b}" for a, b in pareamento.chaves_usadas),
                     Estilo(quebra=True))
        aba.mesclar(linha, 1, linha, 5)
        linha += 1

    avisos = list(resultado.avisos)
    if resultado.deteccao:
        avisos.extend(resultado.deteccao.avisos)
    if pareamento:
        avisos.extend(pareamento.avisos)
    if avisos:
        linha += 1
        aba.escrever(linha, 0, "4. Alertas da execucao", E_SECAO)
        aba.mesclar(linha, 0, linha, 5)
        linha += 1
        for aviso in avisos:
            aba.escrever(linha, 0, f"- {aviso}", E_ALERTA_MEDIO.com(quebra=True))
            aba.mesclar(linha, 0, linha, 5)
            linha += 1

    for coluna, largura in enumerate((46, 18, 18, 52, 14, 14)):
        aba.largura(coluna, largura)


# --------------------------------------------------------------------------
# Abas 2 e 3 - Consolidados
# --------------------------------------------------------------------------


def _aba_consolidado(
    planilha: Planilha, consolidado: Consolidado, resultado: ResultadoGeral, lado: str
) -> None:
    aba = planilha.aba(_nome_aba("Consolidado", consolidado.nome))
    pareamento = resultado.pareamento
    if pareamento:
        pareados = {p.id_a if lado == "A" else p.id_b for p in pareamento.pares}
        divergentes = {
            (p.id_a if lado == "A" else p.id_b) for p in pareamento.pares if p.divergencias
        }
    else:
        pareados, divergentes = set(), set()
    nome_oposto = resultado.nome_b if lado == "A" else resultado.nome_a
    ocorrencias = resultado.qualidade_a if lado == "A" else resultado.qualidade_b
    problemas: Dict[str, int] = {}
    if ocorrencias:
        for ocorrencia in ocorrencias.ocorrencias:
            if ocorrencia.gravidade == GRAVIDADE_ALTA:
                problemas[ocorrencia.id_registro] = problemas.get(ocorrencia.id_registro, 0) + 1

    colunas = [COL_ID] + consolidado.colunas_dados + [COL_ARQUIVO, COL_LINHA]
    cabecalho = colunas + ["Situacao no pareamento", "Alertas de qualidade (gravidade alta)"]
    linha = _titulo_aba(
        aba,
        f"Consolidado - {consolidado.nome}",
        f"{len(consolidado.tabela.linhas)} registros reunidos de "
        f"{len(consolidado.arquivos)} arquivo(s)/aba(s). "
        f"A coluna 'Situacao no pareamento' compara com {nome_oposto}.",
        len(cabecalho),
    )
    estilo_cabecalho = E_CABECALHO_A if lado == "A" else E_CABECALHO_B
    _escrever_cabecalho(aba, linha, cabecalho, estilo_cabecalho)
    linha_cabecalho = linha
    linha += 1

    tipos = {c.nome: c.tipo for c in consolidado.campos}
    for numero, registro in enumerate(consolidado.tabela.linhas):
        base = E_DADO if numero % 2 == 0 else E_DADO_ZEBRA
        for indice, coluna in enumerate(colunas):
            valor, estilo_tipo = _valor_tipado(registro.get(coluna), tipos.get(coluna, "texto"))
            estilo = base if estilo_tipo is None else estilo_tipo.com(fundo=base.fundo)
            aba.escrever(linha, indice, valor, estilo)
        identificador = registro.get(COL_ID)
        if not pareamento:
            situacao, estilo_situacao = "Pareamento nao executado", base
        elif identificador in divergentes:
            situacao = f"Pareado com divergencia de conteudo"
            estilo_situacao = E_DIVERGENTE
        elif identificador in pareados:
            situacao, estilo_situacao = f"Pareado com {nome_oposto}", E_OK
        else:
            situacao = f"SOMENTE neste sistema (ausente em {nome_oposto})"
            estilo_situacao = E_SOMENTE_A if lado == "A" else E_SOMENTE_B
        aba.escrever(linha, len(colunas), situacao, estilo_situacao)
        alertas = problemas.get(identificador, 0)
        aba.escrever(
            linha, len(colunas) + 1, alertas or "",
            (E_ALERTA_ALTO if alertas else base).com(alinhamento="center"),
        )
        linha += 1

    aba.larguras_automaticas(minima=10, maxima=40)
    aba.largura(len(colunas), 34)
    aba.largura(len(colunas) + 1, 14)
    aba.congelar(linha_cabecalho + 1, 1)
    aba.aplicar_autofiltro(linha_cabecalho, 0, len(cabecalho) - 1)


# --------------------------------------------------------------------------
# Abas 4 e 5 - Qualidade
# --------------------------------------------------------------------------


def _aba_qualidade(planilha: Planilha, consolidado: Consolidado, qualidade: ResultadoQualidade) -> None:
    aba = planilha.aba(_nome_aba("Qualidade", consolidado.nome))
    cabecalho_indicadores = [
        "Campo", "Tipo", "Chave", "Registros", "Preenchidos", "Completude %",
        "Distintos", "Unicidade %", "Invalidos", "Fora do dominio",
        "Divergencias de grafia", "Implausiveis", "Nota (0-100)", "Classificacao",
        "Exemplos de valor com problema",
    ]
    linha = _titulo_aba(
        aba,
        f"Analise de atributos de qualidade - {consolidado.nome}",
        f"Nota geral {qualidade.nota_geral:.1f} ({classificar(qualidade.nota_geral)}) - "
        f"{len(qualidade.ocorrencias)} ocorrencias em {qualidade.registros_com_problema} "
        f"de {qualidade.total_registros} registros.",
        len(cabecalho_indicadores),
    )

    aba.escrever(linha, 0, "A. Notas por dimensao", E_SECAO)
    aba.mesclar(linha, 0, linha, 6)
    linha += 1
    _escrever_cabecalho(aba, linha, ["Dimensao", "Nota", "Classificacao", "Ocorrencias"])
    linha += 1
    contagem_dimensao = qualidade.por_dimensao()
    for dimensao in DIMENSOES:
        nota = qualidade.notas_dimensao.get(dimensao, 0.0)
        aba.escrever(linha, 0, dimensao, E_DADO.com(negrito=True))
        aba.escrever(linha, 1, round(nota, 1), _estilo_nota(nota).com(alinhamento="center"))
        aba.escrever(linha, 2, classificar(nota), _estilo_nota(nota))
        aba.escrever(linha, 3, contagem_dimensao.get(dimensao, 0), E_DADO.com(alinhamento="center"))
        linha += 1
    linha += 1

    aba.escrever(linha, 0, "B. Indicadores por campo", E_SECAO)
    aba.mesclar(linha, 0, linha, len(cabecalho_indicadores) - 1)
    linha += 1
    _escrever_cabecalho(aba, linha, cabecalho_indicadores)
    linha += 1
    for metrica in sorted(qualidade.metricas, key=lambda m: m.nota):
        valores = [
            metrica.campo, metrica.tipo, "SIM" if metrica.chave else "",
            metrica.total, metrica.preenchidos, round(metrica.completude, 1),
            metrica.distintos, round(metrica.unicidade, 1), metrica.invalidos,
            metrica.fora_dominio, metrica.variacoes_grafia, metrica.implausiveis,
            metrica.nota, metrica.classificacao, "; ".join(metrica.exemplos),
        ]
        for indice, valor in enumerate(valores):
            estilo = E_DADO
            if indice == 5:
                estilo = _estilo_nota(metrica.completude).com(alinhamento="center")
            elif indice == 12:
                estilo = _estilo_nota(metrica.nota).com(negrito=True, alinhamento="center")
            elif indice == 13:
                estilo = _estilo_nota(metrica.nota)
            elif indice in (8, 9, 10, 11) and isinstance(valor, int) and valor > 0:
                estilo = E_ALERTA_MEDIO.com(alinhamento="center")
            elif isinstance(valor, (int, float)):
                estilo = E_DADO.com(alinhamento="center")
            aba.escrever(linha, indice, valor, estilo)
        linha += 1
    linha += 2

    aba.escrever(linha, 0, "C. Ocorrencias detalhadas (inconsistencias registro a registro)", E_SECAO)
    aba.mesclar(linha, 0, linha, len(cabecalho_indicadores) - 1)
    linha += 1
    cabecalho_ocorrencias = [
        "Gravidade", "Dimensao", "Campo", "Descricao da inconsistencia", "Valor encontrado",
        "ID do registro", "Arquivo de origem", "Linha no arquivo",
    ]
    _escrever_cabecalho(aba, linha, cabecalho_ocorrencias)
    linha_filtro = linha
    linha += 1
    ordem_gravidade = {GRAVIDADE_ALTA: 0, GRAVIDADE_MEDIA: 1, GRAVIDADE_BAIXA: 2}
    ocorrencias = sorted(
        qualidade.ocorrencias,
        key=lambda o: (ordem_gravidade.get(o.gravidade, 3), o.dimensao, o.campo, o.id_registro),
    )
    if not ocorrencias:
        aba.escrever(linha, 0, "Nenhuma inconsistencia encontrada.", E_OK)
        linha += 1
    for ocorrencia in ocorrencias:
        estilo = ESTILO_GRAVIDADE.get(ocorrencia.gravidade, E_DADO)
        valores = [
            ocorrencia.gravidade, ocorrencia.dimensao, ocorrencia.campo, ocorrencia.descricao,
            ocorrencia.valor, ocorrencia.id_registro, ocorrencia.arquivo, ocorrencia.linha,
        ]
        for indice, valor in enumerate(valores):
            aba.escrever(linha, indice, valor, estilo if indice == 0 else E_DADO)
        linha += 1

    for coluna, largura in enumerate((26, 14, 22, 52, 26, 14, 26, 12, 12, 12, 14, 12, 12, 14, 34)):
        aba.largura(coluna, largura)
    aba.aplicar_autofiltro(linha_filtro, 0, len(cabecalho_ocorrencias) - 1)


# --------------------------------------------------------------------------
# Aba 6 - Pareamento
# --------------------------------------------------------------------------


def _aba_pareamento(planilha: Planilha, resultado: ResultadoGeral) -> None:
    pareamento: ResultadoPareamento = resultado.pareamento
    aba = planilha.aba("Pareamento")
    mapa = pareamento.mapa_campos[:LIMITE_COLUNAS_PAREAMENTO]
    cabecalho_fixo = [
        "ID " + resultado.nome_a[:12], "ID " + resultado.nome_b[:12], "Tipo de pareamento",
        "Escore", "Chave utilizada", "Valor da chave", "Situacao", "Qtd. divergencias",
        "Campos divergentes", "Multiplicidade",
    ]
    cabecalho = list(cabecalho_fixo)
    for par_campos in mapa:
        cabecalho.append(f"{par_campos.campo_a} ({resultado.nome_a[:10]})")
        cabecalho.append(f"{par_campos.campo_b} ({resultado.nome_b[:10]})")

    linha = _titulo_aba(
        aba,
        f"Pareamento entre {resultado.nome_a} e {resultado.nome_b}",
        f"{pareamento.total_pares} pares; {pareamento.pares_divergentes} com divergencia de "
        f"conteudo. Celulas em amarelo indicam campos com valores diferentes entre os sistemas.",
        len(cabecalho),
    )
    _escrever_cabecalho(aba, linha, cabecalho)
    linha_cabecalho = linha
    linha += 1

    for numero, par in enumerate(pareamento.pares):
        base = E_DADO if numero % 2 == 0 else E_DADO_ZEBRA
        divergentes = {d.campo_a for d in par.divergencias}
        estilo_situacao = E_DIVERGENTE if par.divergencias else E_OK
        valores = [
            par.id_a, par.id_b, par.tipo, round(par.escore, 3), par.chave_usada,
            par.valor_chave, par.situacao, len(par.divergencias),
            "; ".join(
                f"{d.campo_a}: '{d.valor_a or '(vazio)'}' x '{d.valor_b or '(vazio)'}'"
                for d in par.divergencias[:6]
            ),
            par.multiplicidade,
        ]
        for indice, valor in enumerate(valores):
            estilo = base
            if indice == 6:
                estilo = estilo_situacao
            elif indice == 7 and valor:
                estilo = E_DIVERGENTE.com(alinhamento="center")
            elif indice == 3:
                estilo = base.com(alinhamento="center")
            elif indice == 9 and par.multiplicidade != "1:1":
                estilo = E_ALERTA_MEDIO
            aba.escrever(linha, indice, valor, estilo)
        coluna = len(cabecalho_fixo)
        for par_campos in mapa:
            valor_a = tx.limpar(par.linha_a.get(par_campos.campo_a))
            valor_b = tx.limpar(par.linha_b.get(par_campos.campo_b))
            estilo = E_DIVERGENTE if par_campos.campo_a in divergentes else base
            aba.escrever(linha, coluna, valor_a, estilo)
            aba.escrever(linha, coluna + 1, valor_b, estilo)
            coluna += 2
        linha += 1

    if not pareamento.pares:
        aba.escrever(linha, 0, "Nenhum par foi identificado entre os dois sistemas.", E_ALERTA_ALTO)
        linha += 1

    aba.larguras_automaticas(minima=12, maxima=38)
    aba.largura(8, 52)
    aba.congelar(linha_cabecalho + 1, 2)
    aba.aplicar_autofiltro(linha_cabecalho, 0, len(cabecalho) - 1)

    # Legenda das cores
    linha += 1
    aba.escrever(linha, 0, "Legenda:", E_ROTULO)
    aba.escrever(linha, 1, "Amarelo = valor divergente entre os sistemas", E_DIVERGENTE)
    aba.escrever(linha, 2, "Verde = registro identico nos campos comparados", E_OK)


# --------------------------------------------------------------------------
# Abas 7 e 8 - Exclusivos de cada sistema
# --------------------------------------------------------------------------


def _campos_do_candidato(pareamento: ResultadoPareamento, lado: str) -> List[str]:
    """Campos do outro sistema que ajudam a decidir se e a mesma pessoa."""
    campos: List[str] = []
    for par_a, par_b in pareamento.campos_similaridade:
        campos.append(par_b if lado == "A" else par_a)
    for par in pareamento.mapa_campos:
        if len(campos) >= 5:
            break
        nome = par.campo_b if lado == "A" else par.campo_a
        if nome not in campos:
            campos.append(nome)
    return campos[:5]


def _aba_somente(planilha: Planilha, resultado: ResultadoGeral, lado: str) -> None:
    pareamento: ResultadoPareamento = resultado.pareamento
    if lado == "A":
        consolidado, nao_pareados = resultado.consolidado_a, pareamento.somente_a
        nome, nome_oposto, estilo_destaque = resultado.nome_a, resultado.nome_b, E_SOMENTE_A
    else:
        consolidado, nao_pareados = resultado.consolidado_b, pareamento.somente_b
        nome, nome_oposto, estilo_destaque = resultado.nome_b, resultado.nome_a, E_SOMENTE_B
    if consolidado is None:
        return

    aba = planilha.aba(_nome_aba("Somente em", nome))
    colunas = [COL_ID] + consolidado.colunas_dados + [COL_ARQUIVO, COL_LINHA]
    # Colunas do candidato: sem elas, a conferencia obriga a abrir o outro
    # sistema para descobrir o que estava diferente.
    campos_candidato = _campos_do_candidato(pareamento, lado)
    cabecalho = colunas + [
        "Por que consta como ausente", "Semelhanca com o mais parecido",
        "ID do mais parecido",
    ] + [f"{campo} em {nome_oposto[:14]} (mais parecido)" for campo in campos_candidato]
    total = len(consolidado.tabela.linhas)
    percentual = (100.0 * len(nao_pareados) / total) if total else 0.0
    linha = _titulo_aba(
        aba,
        f"Registros que existem em {nome} e nao foram localizados em {nome_oposto}",
        f"{len(nao_pareados)} de {total} registros ({percentual:.1f}%). "
        f"Todas as linhas estao realcadas; a coluna 'Por que consta como ausente' descreve o motivo.",
        len(cabecalho),
    )
    _escrever_cabecalho(aba, linha, cabecalho,
                        E_CABECALHO_A if lado == "A" else E_CABECALHO_B)
    linha_cabecalho = linha
    linha += 1

    tipos = {c.nome: c.tipo for c in consolidado.campos}
    for item in nao_pareados:
        for indice, coluna in enumerate(colunas):
            valor, estilo_tipo = _valor_tipado(item.linha.get(coluna), tipos.get(coluna, "texto"))
            estilo = estilo_destaque if estilo_tipo is None else estilo_tipo.com(
                fundo=estilo_destaque.fundo, cor=estilo_destaque.cor
            )
            aba.escrever(linha, indice, valor, estilo)
        aba.escrever(linha, len(colunas), item.motivo, estilo_destaque.com(quebra=True))
        aba.escrever(
            linha, len(colunas) + 1,
            f"{item.escore_candidato:.0%}" if item.escore_candidato else "",
            (E_ALERTA_MEDIO if item.escore_candidato >= 0.85 else E_DADO).com(alinhamento="center"),
        )
        aba.escrever(linha, len(colunas) + 2,
                     tx.limpar(item.linha_candidata.get(COL_ID)), E_DADO)
        for deslocamento, campo in enumerate(campos_candidato):
            aba.escrever(linha, len(colunas) + 3 + deslocamento,
                         tx.limpar(item.linha_candidata.get(campo)), E_DADO)
        linha += 1

    if not nao_pareados:
        aba.escrever(linha, 0,
                     f"Todos os registros de {nome} foram localizados em {nome_oposto}.", E_OK)
        aba.mesclar(linha, 0, linha, max(len(cabecalho) - 1, 1))

    aba.larguras_automaticas(minima=10, maxima=40)
    aba.largura(len(colunas), 56)
    aba.largura(len(colunas) + 1, 14)
    aba.congelar(linha_cabecalho + 1, 1)
    aba.aplicar_autofiltro(linha_cabecalho, 0, len(cabecalho) - 1)


# --------------------------------------------------------------------------
# Aba 9 - Arquivos lidos
# --------------------------------------------------------------------------


def _aba_arquivos(planilha: Planilha, resultado: ResultadoGeral) -> None:
    aba = planilha.aba("Arquivos lidos")
    cabecalho = [
        "Arquivo", "Formato", "Sistema atribuido", "Confianca da identificacao",
        "Tabelas/abas", "Registros", "Como foi identificado", "Erro",
    ]
    linha = _titulo_aba(
        aba, "Auditoria da leitura dos arquivos",
        "Registro de cada arquivo processado, do sistema atribuido e do criterio usado.",
        len(cabecalho),
    )
    _escrever_cabecalho(aba, linha, cabecalho)
    linha_cabecalho = linha
    linha += 1
    for arquivo in resultado.arquivos:
        estilo = E_ALERTA_ALTO if arquivo.erro else E_DADO
        confianca = f"{arquivo.confianca:.0%}" if arquivo.confianca else ""
        estilo_confianca = estilo
        if arquivo.confianca and arquivo.confianca < 0.6 and not arquivo.erro:
            estilo_confianca = E_ALERTA_MEDIO
        valores = [
            arquivo.nome, arquivo.extensao, arquivo.sistema, confianca, arquivo.tabelas,
            arquivo.registros, arquivo.justificativa, arquivo.erro,
        ]
        for indice, valor in enumerate(valores):
            aba.escrever(linha, indice, valor,
                         estilo_confianca if indice == 3 else estilo)
        linha += 1
    for coluna, largura in enumerate((38, 10, 22, 14, 12, 12, 60, 40)):
        aba.largura(coluna, largura)
    aba.congelar(linha_cabecalho + 1, 0)
    aba.aplicar_autofiltro(linha_cabecalho, 0, len(cabecalho) - 1)
