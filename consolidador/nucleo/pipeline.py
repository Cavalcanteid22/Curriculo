"""Orquestracao da rotina completa, do arquivo de entrada aos dois produtos finais."""

from __future__ import annotations

import datetime as _dt
import os
import re
from typing import Callable, Dict, Iterable, List, Optional

from . import leitores, relatorio_docx, relatorio_xlsx
from .config import Perfil, carregar_perfil, perfil_padrao
from .deteccao import detectar
from .normalizacao import consolidar
from .pareamento import parear
from .qualidade import analisar
from .resultado import ArquivoLido, ResultadoGeral
from .tabela import Tabela

Progresso = Callable[[str], None]


def expandir_entradas(caminhos: Iterable[str]) -> List[str]:
    """Aceita arquivos e pastas; devolve a lista de arquivos suportados."""
    encontrados: List[str] = []
    for caminho in caminhos:
        caminho = os.path.expanduser(caminho.strip().strip('"').strip("'"))
        if os.path.isdir(caminho):
            for raiz, _pastas, arquivos in os.walk(caminho):
                for nome in sorted(arquivos):
                    if nome.startswith("~$") or nome.startswith("."):
                        continue
                    if os.path.splitext(nome)[1].lower() in leitores.EXTENSOES_SUPORTADAS:
                        encontrados.append(os.path.join(raiz, nome))
        elif os.path.isfile(caminho):
            encontrados.append(caminho)
    vistos, unicos = set(), []
    for caminho in encontrados:
        real = os.path.abspath(caminho)
        if real not in vistos:
            vistos.add(real)
            unicos.append(caminho)
    return unicos


def executar(
    caminhos: Iterable[str],
    pasta_saida: str,
    perfil: Optional[Perfil] = None,
    caminho_perfil: str = "",
    atribuicoes_manuais: Optional[Dict[str, str]] = None,
    prefixo_saida: str = "",
    progresso: Optional[Progresso] = None,
) -> ResultadoGeral:
    """Executa a rotina inteira e grava a planilha e o relatorio."""
    avisar = progresso or (lambda mensagem: None)
    if perfil is None:
        perfil = carregar_perfil(caminho_perfil) if caminho_perfil else perfil_padrao()
    resultado = ResultadoGeral(perfil=perfil)

    arquivos = expandir_entradas(caminhos)
    if not arquivos:
        resultado.erros.append("Nenhum arquivo suportado foi encontrado nas entradas informadas.")
        resultado.fim = _dt.datetime.now()
        return resultado

    avisar(f"Lendo {len(arquivos)} arquivo(s)...")
    tabelas: List[Tabela] = []
    for caminho in arquivos:
        nome = os.path.basename(caminho)
        extensao = os.path.splitext(caminho)[1].lower().lstrip(".")
        registro = ArquivoLido(caminho=caminho, nome=nome, extensao=extensao)
        try:
            lidas = leitores.ler_arquivo(caminho)
            registro.tabelas = len(lidas)
            registro.registros = sum(len(t.linhas) for t in lidas)
            if not lidas:
                registro.erro = "Arquivo sem tabelas com dados."
                resultado.avisos.append(f"{nome}: nenhuma tabela com dados foi encontrada.")
            tabelas.extend(lidas)
            avisar(f"  {nome}: {registro.registros} registro(s) em {registro.tabelas} tabela(s).")
        except Exception as erro:  # falha de um arquivo nao derruba a rotina
            registro.erro = f"{type(erro).__name__}: {erro}"
            resultado.erros.append(f"{nome}: {registro.erro}")
            avisar(f"  {nome}: ERRO - {registro.erro}")
        resultado.arquivos.append(registro)

    if not tabelas:
        resultado.erros.append("Nenhuma tabela pode ser lida: a rotina foi interrompida.")
        resultado.fim = _dt.datetime.now()
        return resultado

    avisar("Identificando a qual sistema pertence cada arquivo...")
    deteccao = detectar(tabelas, perfil, atribuicoes_manuais)
    resultado.deteccao = deteccao
    por_caminho: Dict[str, List] = {}
    for detectada in deteccao.detectadas:
        por_caminho.setdefault(detectada.tabela.origem, []).append(detectada)
    for registro in resultado.arquivos:
        detectadas = por_caminho.get(registro.caminho, [])
        if detectadas:
            melhor = max(detectadas, key=lambda d: d.confianca)
            registro.sistema = deteccao.nomes_sistemas.get(melhor.sistema_id, melhor.sistema_id)
            registro.confianca = melhor.confianca
            registro.justificativa = melhor.justificativa

    avisar("Consolidando cada sistema em uma planilha unica...")
    resultado.consolidado_a = consolidar(
        deteccao.por_sistema("A"), perfil, "A", deteccao.nomes_sistemas.get("A", "Sistema A")
    )
    resultado.consolidado_b = consolidar(
        deteccao.por_sistema("B"), perfil, "B", deteccao.nomes_sistemas.get("B", "Sistema B")
    )
    avisar(
        f"  {resultado.consolidado_a.nome}: {len(resultado.consolidado_a.tabela.linhas)} registros | "
        f"{resultado.consolidado_b.nome}: {len(resultado.consolidado_b.tabela.linhas)} registros"
    )

    avisar("Analisando os atributos de qualidade...")
    resultado.qualidade_a = analisar(resultado.consolidado_a, perfil)
    resultado.qualidade_b = analisar(resultado.consolidado_b, perfil)

    avisar("Pareando os registros dos dois sistemas...")
    resultado.pareamento = parear(resultado.consolidado_a, resultado.consolidado_b, perfil)
    estatisticas = resultado.estatisticas()
    avisar(
        f"  {estatisticas['pares']} par(es); {estatisticas['somente_a']} so em "
        f"{resultado.nome_a}; {estatisticas['somente_b']} so em {resultado.nome_b}."
    )

    os.makedirs(pasta_saida, exist_ok=True)
    prefixo = prefixo_saida or _prefixo_padrao(resultado)
    resultado.caminho_planilha = os.path.join(pasta_saida, f"{prefixo}.xlsx")
    resultado.caminho_relatorio = os.path.join(pasta_saida, f"{prefixo}.docx")

    avisar("Gerando a planilha com as abas...")
    relatorio_xlsx.gerar(resultado, resultado.caminho_planilha)
    avisar("Gerando o relatorio analitico...")
    relatorio_docx.gerar(resultado, resultado.caminho_relatorio)

    resultado.fim = _dt.datetime.now()
    avisar(f"Concluido em {resultado.duracao_segundos:.1f}s.")
    return resultado


def gerar_perfil(resultado: ResultadoGeral) -> Perfil:
    """Transforma o que a rotina descobriu sozinha em um perfil reutilizavel.

    Depois de conferir o resultado uma vez, o usuario salva o perfil e as
    proximas execucoes passam a usar sempre as mesmas regras.
    """
    from .config import CampoConfig, SistemaConfig

    perfil = Perfil(nome=f"{resultado.nome_a} x {resultado.nome_b}")
    perfil.observacoes = (
        "Perfil gerado automaticamente a partir da execucao de "
        f"{resultado.inicio:%d/%m/%Y %H:%M}. Ajuste nomes, chaves e regras conforme a rotina."
    )
    mapa = resultado.pareamento.mapa_campos if resultado.pareamento else []
    canonicos = {par.campo_a: par.campo_b for par in mapa}

    for identificador, consolidado in (("A", resultado.consolidado_a), ("B", resultado.consolidado_b)):
        if not consolidado:
            continue
        mapeamento: Dict[str, List[str]] = {}
        for campo_a, campo_b in canonicos.items():
            nome_local = campo_a if identificador == "A" else campo_b
            mapeamento[campo_a] = [nome_local]
        perfil.sistemas.append(SistemaConfig(
            id=identificador,
            nome=consolidado.nome,
            padroes_arquivo=_padroes_de_arquivo(consolidado),
            colunas_esperadas=list(consolidado.colunas_dados),
            mapeamento=mapeamento,
        ))
    if resultado.consolidado_a:
        for campo in resultado.consolidado_a.campos:
            perfil.campos.append(CampoConfig(
                nome=campo.nome, tipo=campo.tipo, obrigatorio=campo.obrigatorio,
                chave=campo.chave, unico=campo.unico, dominio=list(campo.dominio),
            ))
    if resultado.pareamento:
        chaves = [a for a, _b in resultado.pareamento.chaves_usadas]
        perfil.pareamento.chaves_primarias = chaves[:1]
        perfil.pareamento.chaves_alternativas = [[c] for c in chaves[1:]]
        perfil.pareamento.campos_similaridade = [a for a, _b in resultado.pareamento.campos_similaridade]
        perfil.pareamento.campos_comparacao = [p.campo_a for p in mapa]
    return perfil


def _padroes_de_arquivo(consolidado) -> List[str]:
    nomes = [os.path.splitext(a["arquivo"])[0] for a in consolidado.arquivos]
    if not nomes:
        return []
    prefixo = os.path.commonprefix(nomes).strip(" -_.")
    if len(prefixo) >= 3:
        return [f"^{re.escape(prefixo)}"]
    return [f"^{re.escape(nome)}" for nome in nomes]


def _prefixo_padrao(resultado: ResultadoGeral) -> str:
    def limpar(nome: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "-", nome).strip("-")[:20] or "Sistema"

    carimbo = resultado.inicio.strftime("%Y-%m-%d_%H%M")
    return f"Consolidacao_{limpar(resultado.nome_a)}_x_{limpar(resultado.nome_b)}_{carimbo}"
