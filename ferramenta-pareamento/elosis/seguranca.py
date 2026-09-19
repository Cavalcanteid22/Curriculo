# -*- coding: utf-8 -*-
"""
Camada de segurança e governança da informação (ELO-SIS).

Implementa as salvaguardas declaradas na seção 5 (Aspectos Éticos) do projeto:
pseudonimização de identificadores diretos, processamento exclusivamente em
ambiente institucional e vedação à divulgação de informação identificável.

Referências: Lei nº 13.709/2018 (LGPD), art. 7º, III e art. 11, II, "b";
Resoluções CNS nº 466/2012 e nº 510/2016; Ghaffari Heshajin et al. (2024);
Abdullahi Yari et al. (2021); Carvalho Junior e Bandiera-Paiva (2018).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import platform
import socket
import stat
import sys
import threading
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------- #
# 1. MODO COFRE — bloqueio efetivo de saída de dados para a rede
# --------------------------------------------------------------------------- #

_LOOPBACK = {"127.0.0.1", "::1", "localhost", "0.0.0.0", ""}
_bloqueio_ativo = threading.Event()
_tentativas_bloqueadas: list[dict] = []
_socket_connect_original = socket.socket.connect
_socket_connect_ex_original = socket.socket.connect_ex
_getaddrinfo_original = socket.getaddrinfo


class SaidaDeRedeBloqueada(RuntimeError):
    """Levantada quando algum componente tenta abrir conexão externa."""


def _endereco_e_local(endereco) -> bool:
    if isinstance(endereco, (str, bytes, Path)):
        return True  # socket de domínio UNIX: não sai da máquina
    try:
        host = endereco[0]
    except (TypeError, IndexError):
        return False
    if host in _LOOPBACK:
        return True
    host = str(host)
    return host.startswith("127.") or host.startswith("::ffff:127.")


def _registrar_tentativa(destino) -> None:
    _tentativas_bloqueadas.append(
        {
            "momento": datetime.now().isoformat(timespec="seconds"),
            "destino": str(destino),
        }
    )


def ativar_modo_cofre() -> None:
    """Impede qualquer conexão de rede que não seja de loopback.

    Não é apenas uma declaração de intenção: substitui as primitivas de
    conexão do interpretador, de modo que qualquer biblioteca que tente
    enviar dados para fora da estação falha imediatamente e o evento fica
    registrado na trilha de auditoria.
    """
    if _bloqueio_ativo.is_set():
        return

    def connect(self, endereco):
        if not _endereco_e_local(endereco):
            _registrar_tentativa(endereco)
            raise SaidaDeRedeBloqueada(
                "ELO-SIS opera em modo cofre: conexão externa bloqueada "
                f"({endereco}). Nenhum dado é enviado para a nuvem."
            )
        return _socket_connect_original(self, endereco)

    def connect_ex(self, endereco):
        if not _endereco_e_local(endereco):
            _registrar_tentativa(endereco)
            return 1  # ECONNREFUSED simbólico
        return _socket_connect_ex_original(self, endereco)

    def getaddrinfo(host, *args, **kwargs):
        if host not in _LOOPBACK and not str(host).startswith("127."):
            _registrar_tentativa(host)
            raise SaidaDeRedeBloqueada(
                f"ELO-SIS em modo cofre: resolução de nome bloqueada ({host})."
            )
        return _getaddrinfo_original(host, *args, **kwargs)

    socket.socket.connect = connect          # type: ignore[assignment]
    socket.socket.connect_ex = connect_ex    # type: ignore[assignment]
    socket.getaddrinfo = getaddrinfo         # type: ignore[assignment]
    _bloqueio_ativo.set()


def desativar_modo_cofre() -> None:
    """Restaura as primitivas originais (uso restrito a testes)."""
    socket.socket.connect = _socket_connect_original      # type: ignore[assignment]
    socket.socket.connect_ex = _socket_connect_ex_original  # type: ignore[assignment]
    socket.getaddrinfo = _getaddrinfo_original            # type: ignore[assignment]
    _bloqueio_ativo.clear()


def modo_cofre_ativo() -> bool:
    return _bloqueio_ativo.is_set()


def tentativas_de_saida() -> list[dict]:
    return list(_tentativas_bloqueadas)


# --------------------------------------------------------------------------- #
# 2. PSEUDONIMIZAÇÃO (LGPD, art. 13, §4º)
# --------------------------------------------------------------------------- #

class Pseudonimizador:
    """Gera pseudônimos estáveis por HMAC-SHA256 com sal local.

    O sal nunca acompanha os produtos gerados: fica em arquivo de permissão
    restrita na estação. Sem o sal, o pseudônimo não é reversível nem
    comparável entre instalações — o que preserva a utilidade do pareamento
    dentro do serviço e impede reidentificação fora dele.
    """

    def __init__(self, arquivo_sal: Path | str | None = None):
        self.arquivo_sal = Path(arquivo_sal) if arquivo_sal else self._caminho_padrao()
        self._sal = self._carregar_ou_criar_sal()

    @staticmethod
    def _caminho_padrao() -> Path:
        base = Path(os.environ.get("APPDATA") or Path.home())
        return base / ".elosis" / "sal_pseudonimizacao.key"

    def _carregar_ou_criar_sal(self) -> bytes:
        if self.arquivo_sal.exists():
            return self.arquivo_sal.read_bytes()
        self.arquivo_sal.parent.mkdir(parents=True, exist_ok=True)
        sal = os.urandom(32)
        self.arquivo_sal.write_bytes(sal)
        try:
            os.chmod(self.arquivo_sal, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass  # sistemas de arquivos sem suporte a permissões POSIX
        return sal

    def pseudonimo(self, valor: str, tamanho: int = 16) -> str:
        if valor is None or str(valor).strip() == "":
            return ""
        digest = hmac.new(self._sal, str(valor).strip().upper().encode("utf-8"),
                          hashlib.sha256).digest()
        return base64.b32encode(digest).decode("ascii")[:tamanho]

    def mascarar(self, valor: str, visiveis: int = 3) -> str:
        """Mascaramento parcial para conferência humana sem exposição integral."""
        texto = "" if valor is None else str(valor).strip()
        if not texto:
            return ""
        if len(texto) <= visiveis:
            return "*" * len(texto)
        return texto[:visiveis] + "*" * (len(texto) - visiveis)


# --------------------------------------------------------------------------- #
# 3. TRILHA DE AUDITORIA
# --------------------------------------------------------------------------- #

class TrilhaAuditoria:
    """Registra, de forma local e verificável, o que foi processado.

    Cada arquivo de entrada é identificado por seu resumo criptográfico
    SHA-256, o que permite demonstrar, em auditoria, exatamente qual versão
    da base originou cada produto, sem necessidade de guardar cópia dos dados.
    """

    def __init__(self, diretorio_saida: Path | str):
        self.diretorio = Path(diretorio_saida)
        self.diretorio.mkdir(parents=True, exist_ok=True)
        self.inicio = datetime.now()
        self.eventos: list[dict] = []
        self.arquivos: list[dict] = []
        self.parametros: dict = {}
        self.ambiente = {
            "estacao": socket.gethostname(),
            "usuario_sistema": os.environ.get("USERNAME") or os.environ.get("USER") or "",
            "sistema_operacional": f"{platform.system()} {platform.release()}",
            "python": sys.version.split()[0],
            "modo_cofre": modo_cofre_ativo(),
        }

    def registrar(self, etapa: str, detalhe: str = "", **extras) -> None:
        evento = {
            "momento": datetime.now().isoformat(timespec="seconds"),
            "etapa": etapa,
            "detalhe": detalhe,
        }
        evento.update(extras)
        self.eventos.append(evento)

    def registrar_arquivo(self, caminho: Path | str, papel: str = "entrada",
                          registros: int | None = None) -> str:
        caminho = Path(caminho)
        resumo = resumo_sha256(caminho) if caminho.exists() else ""
        self.arquivos.append(
            {
                "papel": papel,
                "arquivo": caminho.name,
                "caminho": str(caminho.resolve()) if caminho.exists() else str(caminho),
                "tamanho_bytes": caminho.stat().st_size if caminho.exists() else 0,
                "sha256": resumo,
                "registros": registros if registros is not None else "",
                "momento": datetime.now().isoformat(timespec="seconds"),
            }
        )
        return resumo

    def registrar_parametros(self, **parametros) -> None:
        self.parametros.update(parametros)

    def como_dicionario(self) -> dict:
        return {
            "ferramenta": "ELO-SIS",
            "inicio": self.inicio.isoformat(timespec="seconds"),
            "fim": datetime.now().isoformat(timespec="seconds"),
            "ambiente": self.ambiente,
            "parametros": self.parametros,
            "arquivos": self.arquivos,
            "eventos": self.eventos,
            "tentativas_de_saida_de_rede_bloqueadas": tentativas_de_saida(),
        }

    def salvar(self, nome: str = "trilha_auditoria.json") -> Path:
        destino = self.diretorio / nome
        destino.write_text(
            json.dumps(self.como_dicionario(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return destino


def resumo_sha256(caminho: Path | str, bloco: int = 1024 * 1024) -> str:
    """SHA-256 calculado por blocos — suporta arquivos de qualquer tamanho."""
    digest = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for pedaco in iter(lambda: arquivo.read(bloco), b""):
            digest.update(pedaco)
    return digest.hexdigest()
