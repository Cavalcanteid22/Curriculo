"""Janela do aplicativo (Tkinter, que ja vem com o Python).

A tela permite escolher arquivos ou pastas, conferir e corrigir a qual sistema
cada arquivo pertence, apontar a pasta de saida e executar a rotina inteira.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import traceback
from typing import Dict, List, Optional

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as erro:  # pragma: no cover - ambiente sem interface grafica
    raise SystemExit(
        "A interface grafica precisa do Tkinter, que nao esta disponivel neste Python.\n"
        "Use a linha de comando: python consolidar.py <pasta de entrada> -s <pasta de saida>"
    ) from erro

from .config import carregar_perfil, perfil_padrao
from .leitores import EXTENSOES_SUPORTADAS
from .pipeline import executar, expandir_entradas

AUTOMATICO = "(automatico)"
CORES = {"fundo": "#F5F7FA", "destaque": "#1F4E79", "texto": "#1F2937"}


class Aplicativo:
    def __init__(self, raiz: tk.Tk) -> None:
        self.raiz = raiz
        self.arquivos: List[str] = []
        self.atribuicoes: Dict[str, str] = {}
        self.fila: "queue.Queue[tuple]" = queue.Queue()
        self.resultado = None
        self.executando = False

        raiz.title("Consolidador de Sistemas - consolidacao, qualidade e pareamento")
        raiz.geometry("1040x680")
        raiz.minsize(900, 600)
        raiz.configure(bg=CORES["fundo"])

        self.pasta_saida = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Consolidacoes"))
        self.caminho_perfil = tk.StringVar(value="")
        self.nome_a = tk.StringVar(value="")
        self.nome_b = tk.StringVar(value="")
        self.situacao = tk.StringVar(value="Pronto. Adicione os arquivos dos dois sistemas.")

        self._montar_cabecalho()
        self._montar_area_arquivos()
        self._montar_opcoes()
        self._montar_rodape()
        self.raiz.after(120, self._processar_fila)

    # -- montagem da tela --------------------------------------------------

    def _montar_cabecalho(self) -> None:
        topo = tk.Frame(self.raiz, bg=CORES["destaque"], padx=16, pady=12)
        topo.pack(fill="x")
        tk.Label(
            topo, text="Consolidador de Sistemas", bg=CORES["destaque"], fg="white",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w")
        tk.Label(
            topo,
            text="Reune os arquivos de cada sistema, analisa a qualidade, faz o pareamento "
                 "e gera a planilha com todas as abas mais o relatorio em Word.",
            bg=CORES["destaque"], fg="#D6E4F0", font=("Segoe UI", 9), justify="left",
        ).pack(anchor="w")

    def _montar_area_arquivos(self) -> None:
        moldura = tk.LabelFrame(
            self.raiz, text=" 1. Arquivos de entrada ", bg=CORES["fundo"],
            font=("Segoe UI", 10, "bold"), fg=CORES["texto"], padx=10, pady=8,
        )
        moldura.pack(fill="both", expand=True, padx=14, pady=(12, 6))

        botoes = tk.Frame(moldura, bg=CORES["fundo"])
        botoes.pack(fill="x", pady=(0, 6))
        for texto, comando in (
            ("Adicionar arquivos", self.adicionar_arquivos),
            ("Adicionar pasta", self.adicionar_pasta),
            ("Remover selecionados", self.remover_selecionados),
            ("Limpar lista", self.limpar),
        ):
            tk.Button(botoes, text=texto, command=comando, relief="groove", padx=10,
                      bg="white").pack(side="left", padx=(0, 6))
        tk.Label(botoes, text="Sistema do arquivo selecionado:", bg=CORES["fundo"]).pack(
            side="left", padx=(18, 4))
        for texto, valor in (("Sistema 1", "A"), ("Sistema 2", "B"), ("Automatico", "")):
            tk.Button(botoes, text=texto, relief="groove", padx=8, bg="white",
                      command=lambda v=valor: self.definir_sistema(v)).pack(side="left", padx=2)

        colunas = ("arquivo", "formato", "sistema", "pasta")
        self.lista = ttk.Treeview(moldura, columns=colunas, show="headings", height=12)
        for coluna, titulo, largura in (
            ("arquivo", "Arquivo", 330), ("formato", "Formato", 80),
            ("sistema", "Sistema", 120), ("pasta", "Pasta", 430),
        ):
            self.lista.heading(coluna, text=titulo)
            self.lista.column(coluna, width=largura, anchor="w")
        barra = ttk.Scrollbar(moldura, orient="vertical", command=self.lista.yview)
        self.lista.configure(yscrollcommand=barra.set)
        self.lista.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.lista.bind("<Double-1>", self._alternar_sistema)

    def _montar_opcoes(self) -> None:
        moldura = tk.LabelFrame(
            self.raiz, text=" 2. Opcoes ", bg=CORES["fundo"], font=("Segoe UI", 10, "bold"),
            fg=CORES["texto"], padx=10, pady=8,
        )
        moldura.pack(fill="x", padx=14, pady=6)

        linha = tk.Frame(moldura, bg=CORES["fundo"])
        linha.pack(fill="x", pady=2)
        tk.Label(linha, text="Pasta de saida:", bg=CORES["fundo"], width=16, anchor="w").pack(side="left")
        tk.Entry(linha, textvariable=self.pasta_saida).pack(side="left", fill="x", expand=True)
        tk.Button(linha, text="Escolher", command=self.escolher_saida, relief="groove",
                  bg="white").pack(side="left", padx=6)

        linha = tk.Frame(moldura, bg=CORES["fundo"])
        linha.pack(fill="x", pady=2)
        tk.Label(linha, text="Perfil (opcional):", bg=CORES["fundo"], width=16, anchor="w").pack(side="left")
        tk.Entry(linha, textvariable=self.caminho_perfil).pack(side="left", fill="x", expand=True)
        tk.Button(linha, text="Escolher", command=self.escolher_perfil, relief="groove",
                  bg="white").pack(side="left", padx=6)
        tk.Button(linha, text="Limpar", command=lambda: self.caminho_perfil.set(""),
                  relief="groove", bg="white").pack(side="left")

        linha = tk.Frame(moldura, bg=CORES["fundo"])
        linha.pack(fill="x", pady=2)
        tk.Label(linha, text="Nome do Sistema 1:", bg=CORES["fundo"], width=16, anchor="w").pack(side="left")
        tk.Entry(linha, textvariable=self.nome_a, width=24).pack(side="left")
        tk.Label(linha, text="Nome do Sistema 2:", bg=CORES["fundo"], padx=12).pack(side="left")
        tk.Entry(linha, textvariable=self.nome_b, width=24).pack(side="left")
        tk.Label(linha, text="(em branco = deduzido dos nomes dos arquivos)",
                 bg=CORES["fundo"], fg="#6B7280").pack(side="left", padx=8)

    def _montar_rodape(self) -> None:
        moldura = tk.LabelFrame(
            self.raiz, text=" 3. Execucao ", bg=CORES["fundo"], font=("Segoe UI", 10, "bold"),
            fg=CORES["texto"], padx=10, pady=8,
        )
        moldura.pack(fill="both", expand=True, padx=14, pady=(6, 12))

        linha = tk.Frame(moldura, bg=CORES["fundo"])
        linha.pack(fill="x")
        self.botao_executar = tk.Button(
            linha, text="Executar rotina", command=self.executar, bg=CORES["destaque"],
            fg="white", font=("Segoe UI", 11, "bold"), padx=18, pady=6, relief="raised",
        )
        self.botao_executar.pack(side="left")
        self.botao_abrir = tk.Button(
            linha, text="Abrir pasta de resultados", command=self.abrir_saida, relief="groove",
            bg="white", padx=10, state="disabled",
        )
        self.botao_abrir.pack(side="left", padx=8)
        self.progresso = ttk.Progressbar(linha, mode="indeterminate", length=220)
        self.progresso.pack(side="right")

        tk.Label(moldura, textvariable=self.situacao, bg=CORES["fundo"], anchor="w",
                 fg="#374151").pack(fill="x", pady=(6, 2))
        self.registro = tk.Text(moldura, height=9, bg="white", fg="#111827",
                                font=("Consolas", 9), wrap="word")
        self.registro.pack(fill="both", expand=True)
        self.registro.configure(state="disabled")

    # -- acoes da tela -----------------------------------------------------

    def adicionar_arquivos(self) -> None:
        tipos = [("Arquivos suportados", " ".join(f"*{e}" for e in EXTENSOES_SUPORTADAS)),
                 ("Todos os arquivos", "*.*")]
        escolhidos = filedialog.askopenfilenames(title="Selecione os arquivos", filetypes=tipos)
        self._incluir(list(escolhidos))

    def adicionar_pasta(self) -> None:
        pasta = filedialog.askdirectory(title="Selecione a pasta com os arquivos")
        if pasta:
            self._incluir(expandir_entradas([pasta]))

    def _incluir(self, caminhos: List[str]) -> None:
        novos = 0
        for caminho in caminhos:
            if caminho and caminho not in self.arquivos:
                self.arquivos.append(caminho)
                novos += 1
        self._recarregar_lista()
        if novos:
            self.situacao.set(f"{novos} arquivo(s) adicionado(s). Total: {len(self.arquivos)}.")

    def _recarregar_lista(self) -> None:
        self.lista.delete(*self.lista.get_children())
        for caminho in self.arquivos:
            atribuido = self.atribuicoes.get(caminho, "")
            rotulo = {"A": "Sistema 1", "B": "Sistema 2"}.get(atribuido, AUTOMATICO)
            self.lista.insert("", "end", iid=caminho, values=(
                os.path.basename(caminho),
                os.path.splitext(caminho)[1].lstrip(".").upper() or "-",
                rotulo,
                os.path.dirname(caminho),
            ))

    def remover_selecionados(self) -> None:
        for caminho in self.lista.selection():
            if caminho in self.arquivos:
                self.arquivos.remove(caminho)
            self.atribuicoes.pop(caminho, None)
        self._recarregar_lista()

    def limpar(self) -> None:
        self.arquivos.clear()
        self.atribuicoes.clear()
        self._recarregar_lista()
        self.situacao.set("Lista limpa.")

    def definir_sistema(self, valor: str) -> None:
        selecionados = self.lista.selection()
        if not selecionados:
            messagebox.showinfo("Consolidador", "Selecione um ou mais arquivos na lista.")
            return
        for caminho in selecionados:
            if valor:
                self.atribuicoes[caminho] = valor
            else:
                self.atribuicoes.pop(caminho, None)
        self._recarregar_lista()
        for caminho in selecionados:
            self.lista.selection_add(caminho)

    def _alternar_sistema(self, _evento=None) -> None:
        for caminho in self.lista.selection():
            atual = self.atribuicoes.get(caminho, "")
            self.atribuicoes[caminho] = {"": "A", "A": "B", "B": ""}[atual]
            if not self.atribuicoes[caminho]:
                self.atribuicoes.pop(caminho)
        self._recarregar_lista()

    def escolher_saida(self) -> None:
        pasta = filedialog.askdirectory(title="Pasta onde gravar os resultados")
        if pasta:
            self.pasta_saida.set(pasta)

    def escolher_perfil(self) -> None:
        caminho = filedialog.askopenfilename(
            title="Perfil de configuracao", filetypes=[("Perfil JSON", "*.json")]
        )
        if caminho:
            self.caminho_perfil.set(caminho)

    def abrir_saida(self) -> None:
        pasta = self.pasta_saida.get()
        if not os.path.isdir(pasta):
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(pasta)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", pasta], check=False)
            else:
                subprocess.run(["xdg-open", pasta], check=False)
        except OSError as erro:
            messagebox.showwarning("Consolidador", f"Nao foi possivel abrir a pasta: {erro}")

    # -- execucao ----------------------------------------------------------

    def executar(self) -> None:
        if self.executando:
            return
        if not self.arquivos:
            messagebox.showwarning("Consolidador", "Adicione ao menos um arquivo de cada sistema.")
            return
        self.executando = True
        self.botao_executar.configure(state="disabled", text="Processando...")
        self.progresso.start(12)
        self._escrever_registro("", limpar=True)
        # O Tkinter so pode ser lido na linha principal: os valores da tela vao
        # para a thread ja convertidos em texto comum.
        opcoes = {
            "arquivos": list(self.arquivos),
            "atribuicoes": dict(self.atribuicoes),
            "pasta_saida": self.pasta_saida.get().strip(),
            "perfil": self.caminho_perfil.get().strip(),
            "nome_a": self.nome_a.get().strip(),
            "nome_b": self.nome_b.get().strip(),
        }
        threading.Thread(
            target=self._executar_em_segundo_plano, args=(opcoes,), daemon=True
        ).start()

    def _executar_em_segundo_plano(self, opcoes: Dict[str, object]) -> None:
        try:
            caminho_perfil = str(opcoes["perfil"])
            perfil = carregar_perfil(caminho_perfil) if caminho_perfil else perfil_padrao()
            if opcoes["nome_a"]:
                perfil.sistemas[0].nome = str(opcoes["nome_a"])
            if opcoes["nome_b"]:
                perfil.sistemas[1].nome = str(opcoes["nome_b"])
            resultado = executar(
                opcoes["arquivos"], str(opcoes["pasta_saida"]), perfil=perfil,
                atribuicoes_manuais=opcoes["atribuicoes"],
                progresso=lambda mensagem: self.fila.put(("log", mensagem)),
            )
            self.fila.put(("fim", resultado))
        except Exception as erro:  # a tela nunca deve morrer por causa de um arquivo ruim
            self.fila.put(("erro", f"{type(erro).__name__}: {erro}\n{traceback.format_exc()}"))

    def _processar_fila(self) -> None:
        try:
            while True:
                tipo, dados = self.fila.get_nowait()
                if tipo == "log":
                    self._escrever_registro(dados)
                    self.situacao.set(dados)
                elif tipo == "fim":
                    self._concluir(dados)
                elif tipo == "erro":
                    self._falhar(dados)
        except queue.Empty:
            pass
        self.raiz.after(120, self._processar_fila)

    def _concluir(self, resultado) -> None:
        self.executando = False
        self.resultado = resultado
        self.progresso.stop()
        self.botao_executar.configure(state="normal", text="Executar rotina")
        self.botao_abrir.configure(state="normal")
        if not resultado.caminho_planilha:
            mensagem = "\n".join(resultado.erros) or "Nenhum resultado foi gerado."
            self._escrever_registro(f"FALHA: {mensagem}")
            messagebox.showerror("Consolidador", mensagem)
            return
        estatisticas = resultado.estatisticas()
        resumo = (
            f"{resultado.nome_a}: {estatisticas['registros_a']} registros\n"
            f"{resultado.nome_b}: {estatisticas['registros_b']} registros\n"
            f"Pares encontrados: {estatisticas['pares']}\n"
            f"Somente em {resultado.nome_a}: {estatisticas['somente_a']}\n"
            f"Somente em {resultado.nome_b}: {estatisticas['somente_b']}\n"
            f"Pares com divergencia: {estatisticas['divergentes']}\n\n"
            f"Planilha: {resultado.caminho_planilha}\n"
            f"Relatorio: {resultado.caminho_relatorio}"
        )
        self._escrever_registro("\n" + resumo)
        self.situacao.set("Concluido.")
        if resultado.erros:
            self._escrever_registro("\nArquivos com problema:\n" + "\n".join(resultado.erros))
        messagebox.showinfo("Consolidador - concluido", resumo)

    def _falhar(self, mensagem: str) -> None:
        self.executando = False
        self.progresso.stop()
        self.botao_executar.configure(state="normal", text="Executar rotina")
        self._escrever_registro(f"ERRO: {mensagem}")
        self.situacao.set("Falha na execucao.")
        messagebox.showerror("Consolidador", mensagem.splitlines()[0])

    def _escrever_registro(self, mensagem: str, limpar: bool = False) -> None:
        self.registro.configure(state="normal")
        if limpar:
            self.registro.delete("1.0", "end")
        if mensagem:
            self.registro.insert("end", mensagem + "\n")
            self.registro.see("end")
        self.registro.configure(state="disabled")


def abrir() -> None:
    raiz = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    Aplicativo(raiz)
    raiz.mainloop()
