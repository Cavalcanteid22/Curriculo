"""Carregamento e validação dos arquivos de configuração de cada sistema.

Cada sistema (SIM, SINAN, SINASC, e-SUS SINAN, SINAN Online) é descrito por um
arquivo JSON em ``configs/``. O arquivo traduz o dicionário de dados oficial em
regras que o programa sabe executar — **nenhuma linha de Python precisa ser
alterada para incluir um campo, um domínio ou uma nova crítica**.
"""

from __future__ import annotations

import json
import os
import re

from .leitura import normalizar_coluna

PASTA_PADRAO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs")

FORMATOS_DATA_PADRAO = [
    "%d/%m/%Y", "%Y-%m-%d", "%Y%m%d", "%d-%m-%Y", "%d/%m/%y",
    "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
]

IGNORADOS_PADRAO_TEXTO = {
    "IGNORADO", "IGNORADA", "IGN", "NAO INFORMADO", "NÃO INFORMADO",
    "NAO INFORMADA", "NÃO INFORMADA", "SEM INFORMACAO", "SEM INFORMAÇÃO",
    "NI", "N/I", "NAO SE APLICA", "NÃO SE APLICA", "-", "--", "...",
}


class ErroConfig(Exception):
    pass


def _data_iso(texto):
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(texto), fmt).date()
        except ValueError:
            continue
    raise ErroConfig(f"Data inválida na configuração: {texto!r} (use AAAA-MM-DD)")


class ConfigSistema:
    """Configuração de um sistema de informação."""

    def __init__(self, dados, caminho=None):
        self.caminho = caminho
        self.dados = dados
        self.sigla = dados.get("sistema") or "SISTEMA"
        self.nome = dados.get("nome_completo", self.sigla)
        self.descricao = dados.get("descricao", "")
        self.orgao = dados.get("orgao", "Subcoordenadoria de Informação em Saúde — SMS Salvador")

        csvcfg = dados.get("csv", {})
        self.separador = csvcfg.get("separador")
        self.encoding = csvcfg.get("encoding")
        self.mapa_colunas = {
            normalizar_coluna(k): normalizar_coluna(v)
            for k, v in dados.get("apelidos_colunas", {}).items()
        }

        self.campos = {normalizar_coluna(k): self._normalizar_campo(k, v)
                       for k, v in dados.get("campos", {}).items()}
        self.chave_registro = [normalizar_coluna(c) for c in dados.get("chave_registro", [])]
        self.chaves_duplicidade = dados.get("chaves_duplicidade", [])
        for ch in self.chaves_duplicidade:
            ch["campos"] = [normalizar_coluna(c) for c in ch.get("campos", [])]
        self.regras_cruzadas = dados.get("regras_cruzadas", [])
        self.tempestividade = dados.get("tempestividade", [])
        self.data_referencia = normalizar_coluna(dados.get("data_referencia", "")) or None
        self.campos_estratificacao = [normalizar_coluna(c)
                                      for c in dados.get("campos_estratificacao", [])]
        self.parametros = dados.get("parametros", {})
        self.limites_faixa = dados.get("faixas_classificacao", {})
        self.pesos_atributos = dados.get("pesos_atributos", {})

    # ------------------------------------------------------------------ #
    def _normalizar_campo(self, nome, spec):
        spec = dict(spec or {})
        spec.setdefault("rotulo", nome)
        spec.setdefault("tipo", "texto")
        spec.setdefault("obrigatorio", False)
        spec.setdefault("essencial", spec.get("obrigatorio", False))
        spec.setdefault("bloco", "Geral")
        dominio = spec.get("dominio")
        if isinstance(dominio, list):
            dominio = {str(v): str(v) for v in dominio}
        if isinstance(dominio, dict):
            dominio = {str(k).strip().upper(): v for k, v in dominio.items()}
        spec["dominio"] = dominio
        spec["ignorado"] = {str(v).strip().upper() for v in spec.get("ignorado", [])}
        if spec.get("ignorado_texto_padrao", True):
            spec["ignorado"] |= IGNORADOS_PADRAO_TEXTO
        if spec["tipo"] == "data":
            spec.setdefault("formatos", FORMATOS_DATA_PADRAO)
            for chave in ("data_minima", "data_maxima"):
                if spec.get(chave):
                    spec["_" + chave] = _data_iso(spec[chave])
        if spec.get("regex"):
            spec["_regex"] = re.compile(spec["regex"])
        return spec

    # ------------------------------------------------------------------ #
    @property
    def campos_essenciais(self):
        return [c for c, s in self.campos.items() if s.get("essencial")]

    @property
    def campos_obrigatorios(self):
        return [c for c, s in self.campos.items() if s.get("obrigatorio")]

    def blocos(self):
        saida = {}
        for campo, spec in self.campos.items():
            saida.setdefault(spec.get("bloco", "Geral"), []).append(campo)
        return saida

    def rotulo(self, campo):
        spec = self.campos.get(campo)
        return spec["rotulo"] if spec else campo

    def validar_contra_base(self, colunas_base):
        """Compara as colunas do CSV com as colunas esperadas na configuração."""
        colunas = set(colunas_base)
        esperadas = set(self.campos)
        return {
            "ausentes": sorted(esperadas - colunas),
            "nao_previstas": sorted(colunas - esperadas),
            "cobertas": sorted(esperadas & colunas),
        }


def carregar(sistema_ou_caminho, pasta=None):
    """Carrega a configuração pela sigla (``sim``) ou pelo caminho do arquivo."""
    pasta = pasta or PASTA_PADRAO
    caminho = sistema_ou_caminho
    if not os.path.exists(caminho):
        cand = os.path.join(pasta, f"{str(sistema_ou_caminho).lower()}.json")
        if os.path.exists(cand):
            caminho = cand
        else:
            disponiveis = ", ".join(sorted(listar(pasta))) or "(nenhuma)"
            raise ErroConfig(
                f"Configuração '{sistema_ou_caminho}' não encontrada. "
                f"Configurações disponíveis: {disponiveis}"
            )
    with open(caminho, "r", encoding="utf-8") as fh:
        dados = json.load(fh)
    return ConfigSistema(dados, caminho=caminho)


def listar(pasta=None):
    """Lista as siglas de sistemas configurados."""
    pasta = pasta or PASTA_PADRAO
    if not os.path.isdir(pasta):
        return []
    return [os.path.splitext(f)[0] for f in sorted(os.listdir(pasta)) if f.endswith(".json")]
