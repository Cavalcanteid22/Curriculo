# -*- coding: utf-8 -*-
"""
Interface gráfica do ELO-SIS.

Construída com a biblioteca tkinter, que acompanha a instalação padrão do
Python — a ferramenta precisa executar em estações institucionais sem
permissão para instalar componentes adicionais, e sem depender de navegador
ou de servidor local.

O desenho segue três decisões:

  1. o caminho principal tem três passos visíveis (escolher as bases, escolher
     onde salvar, executar), e todo o restante fica recolhido em "opções
     avançadas", com valores padrão adequados ao uso corrente;
  2. o programa nunca fica sem resposta: o processamento corre em linha de
     execução própria, e a barra de progresso informa a etapa em curso;
  3. as mensagens dizem o que houve e o que fazer, em vez de reproduzir o
     erro técnico.
"""

from __future__ import annotations

import queue
import threading
import traceback
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .leitura import contar_registros
from .perfis import PERSPECTIVAS, identificar_sistema
from .pipeline import Configuracao, executar
from .planilha import gerar_planilha
from .relatorio import gerar_relatorio

AZUL = "#1F4E79"
AZUL_CLARO = "#2a78d6"
CINZA = "#52514e"
FUNDO = "#fcfcfb"
VERDE = "#0ca30c"
VERMELHO = "#d03b3b"

TIPOS_DE_ARQUIVO = [
    ("Todos os formatos aceitos",
     "*.dbf *.DBF *.csv *.CSV *.xlsx *.XLSX *.xls *.xlsm *.pdf *.PDF *.txt"),
    ("Bases DATASUS (DBF)", "*.dbf *.DBF"),
    ("Texto separado (CSV)", "*.csv *.CSV *.txt *.tsv"),
    ("Planilhas Excel", "*.xlsx *.XLSX *.xls *.xlsm"),
    ("Documentos PDF", "*.pdf *.PDF"),
    ("Todos os arquivos", "*.*"),
]


class JanelaPrincipal(ttk.Frame):
    def __init__(self, raiz: tk.Tk):
        super().__init__(raiz, padding=0)
        self.raiz = raiz
        self.arquivos: list[Path] = []
        self.diretorio_saida = tk.StringVar(value=str(Path.home() / "ELO-SIS"))
        self.fila: queue.Queue = queue.Queue()
        self.em_execucao = False
        self.produtos: list[Path] = []

        self.limiar = tk.DoubleVar(value=0.90)
        self.limiar_revisao = tk.DoubleVar(value=0.85)
        self.limiar_duplicidade = tk.DoubleVar(value=0.92)
        self.ano = tk.IntVar(value=2024)
        self.populacao = tk.IntVar(value=2_418_005)
        self.horizonte = tk.IntVar(value=6)
        self.pseudonimizar = tk.BooleanVar(value=False)
        self.gerar_planilha_var = tk.BooleanVar(value=True)
        self.gerar_relatorio_var = tk.BooleanVar(value=True)
        self.perspectiva = tk.StringVar(value="automática")
        self.referencia = tk.StringVar(value="")

        self._configurar_estilo()
        self._montar()
        self.pack(fill="both", expand=True)
        self.after(120, self._processar_fila)

    # ------------------------------------------------------------------ #
    # Aparência
    # ------------------------------------------------------------------ #

    def _configurar_estilo(self) -> None:
        # Atenção: os tamanhos de fonte precisam ser inteiros. O Tk aceita
        # valores fracionários sem erro, mas renderiza o rótulo com 2 px de
        # largura, o que oculta o texto silenciosamente.
        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        self.raiz.configure(bg=FUNDO)
        estilo.configure("TFrame", background=FUNDO)
        estilo.configure("TLabel", background=FUNDO, foreground="#0b0b0b",
                         font=("Segoe UI", 10))
        estilo.configure("Titulo.TLabel", font=("Segoe UI", 17, "bold"),
                         foreground=AZUL)
        estilo.configure("Subtitulo.TLabel", font=("Segoe UI", 9),
                         foreground=CINZA)
        estilo.configure("Passo.TLabel", font=("Segoe UI", 11, "bold"),
                         foreground=AZUL)
        estilo.configure("Nota.TLabel", font=("Segoe UI", 8),
                         foreground=CINZA)
        estilo.configure("TButton", font=("Segoe UI", 10), padding=6)
        estilo.configure("Executar.TButton", font=("Segoe UI", 11, "bold"),
                         padding=10)
        estilo.configure("TCheckbutton", background=FUNDO,
                         font=("Segoe UI", 9))
        estilo.configure("TLabelframe", background=FUNDO)
        estilo.configure("TLabelframe.Label", background=FUNDO,
                         foreground=AZUL, font=("Segoe UI", 10, "bold"))
        estilo.configure("TNotebook", background=FUNDO)
        estilo.configure("Horizontal.TProgressbar", background=AZUL_CLARO)

    def _montar(self) -> None:
        cabecalho = ttk.Frame(self, padding=(20, 16, 20, 8))
        cabecalho.pack(fill="x")
        ttk.Label(cabecalho, text="ELO-SIS", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(cabecalho,
                  text=("Qualificação, harmonização e pareamento de bases dos "
                        "sistemas de informação em saúde"),
                  style="Subtitulo.TLabel").pack(anchor="w")
        ttk.Label(cabecalho,
                  text=("Processamento integralmente local — nenhum dado sai "
                        "desta estação de trabalho."),
                  style="Nota.TLabel").pack(anchor="w", pady=(2, 0))

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20)

        corpo = ttk.Frame(self, padding=(20, 12, 20, 8))
        corpo.pack(fill="both", expand=True)

        self._montar_passo_bases(corpo)
        self._montar_passo_saida(corpo)
        self._montar_avancado(corpo)
        self._montar_execucao(corpo)

    # ------------------------------------------------------------------ #
    # Passo 1 — bases
    # ------------------------------------------------------------------ #

    def _montar_passo_bases(self, pai) -> None:
        quadro = ttk.Frame(pai)
        quadro.pack(fill="both", expand=True, pady=(0, 10))

        linha = ttk.Frame(quadro)
        linha.pack(fill="x")
        ttk.Label(linha, text="1. Escolha as bases de dados",
                  style="Passo.TLabel").pack(side="left")
        ttk.Button(linha, text="Adicionar arquivos…",
                   command=self._adicionar).pack(side="right", padx=(6, 0))
        ttk.Button(linha, text="Remover",
                   command=self._remover).pack(side="right", padx=(6, 0))
        ttk.Button(linha, text="Gerar bases de exemplo",
                   command=self._gerar_exemplo).pack(side="right")

        ttk.Label(quadro,
                  text=("Formatos aceitos: DBF (exportação do DATASUS), CSV, "
                        "Excel e PDF. Arquivos grandes são lidos por blocos."),
                  style="Nota.TLabel").pack(anchor="w", pady=(2, 6))

        caixa = ttk.Frame(quadro)
        caixa.pack(fill="both", expand=True)
        colunas = ("arquivo", "sistema", "registros", "tamanho")
        self.lista = ttk.Treeview(caixa, columns=colunas, show="headings",
                                  height=5, selectmode="extended")
        for coluna, titulo, largura in (
                ("arquivo", "Arquivo", 330), ("sistema", "Sistema", 110),
                ("registros", "Registros", 110), ("tamanho", "Tamanho", 110)):
            self.lista.heading(coluna, text=titulo)
            self.lista.column(coluna, width=largura,
                              anchor="w" if coluna == "arquivo" else "center")
        barra = ttk.Scrollbar(caixa, orient="vertical",
                              command=self.lista.yview)
        self.lista.configure(yscrollcommand=barra.set)
        self.lista.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")

    # ------------------------------------------------------------------ #
    # Passo 2 — saída
    # ------------------------------------------------------------------ #

    def _montar_passo_saida(self, pai) -> None:
        quadro = ttk.Frame(pai)
        quadro.pack(fill="x", pady=(0, 10))
        ttk.Label(quadro, text="2. Escolha onde salvar os resultados",
                  style="Passo.TLabel").pack(anchor="w")
        linha = ttk.Frame(quadro)
        linha.pack(fill="x", pady=(4, 0))
        ttk.Entry(linha, textvariable=self.diretorio_saida).pack(
            side="left", fill="x", expand=True)
        ttk.Button(linha, text="Escolher pasta…",
                   command=self._escolher_saida).pack(side="left", padx=(6, 0))

    # ------------------------------------------------------------------ #
    # Opções avançadas
    # ------------------------------------------------------------------ #

    def _montar_avancado(self, pai) -> None:
        self.avancado_visivel = tk.BooleanVar(value=False)
        linha = ttk.Frame(pai)
        linha.pack(fill="x")
        self.botao_avancado = ttk.Button(
            linha, text="▸ Opções avançadas", width=24,
            command=self._alternar_avancado)
        self.botao_avancado.pack(side="left")
        ttk.Label(linha,
                  text="Os valores padrão atendem ao uso corrente.",
                  style="Nota.TLabel").pack(side="left", padx=(8, 0))

        self.quadro_avancado = ttk.Frame(pai, padding=(0, 8, 0, 0))

        pareamento = ttk.LabelFrame(self.quadro_avancado, text="Pareamento",
                                    padding=10)
        pareamento.pack(fill="x", pady=(0, 8))
        self._campo(pareamento, 0, "Limiar de pareamento:", self.limiar,
                    "Pares com escore igual ou superior são aceitos "
                    "automaticamente.")
        self._campo(pareamento, 1, "Limiar de revisão manual:",
                    self.limiar_revisao,
                    "Entre este valor e o limiar de pareamento, o par vai "
                    "para conferência humana.")
        self._campo(pareamento, 2, "Limiar de duplicidade:",
                    self.limiar_duplicidade,
                    "Similaridade a partir da qual dois registros da mesma "
                    "base são tidos por prováveis duplicatas.")

        linha_perspectiva = ttk.Frame(pareamento)
        linha_perspectiva.grid(row=3, column=0, columnspan=3, sticky="w",
                               pady=(6, 0))
        ttk.Label(linha_perspectiva,
                  text="Identidade no SINASC:").pack(side="left")
        combo = ttk.Combobox(
            linha_perspectiva, textvariable=self.perspectiva, width=18,
            state="readonly",
            values=["automática"] + [PERSPECTIVAS[p]["rotulo"]
                                     for p in PERSPECTIVAS])
        combo.pack(side="left", padx=(8, 8))
        ttk.Label(linha_perspectiva,
                  text=("Automática: recém-nascido ao parear com o SIM, mãe "
                        "ao parear com o SINAN."),
                  style="Nota.TLabel").pack(side="left")

        analise = ttk.LabelFrame(self.quadro_avancado,
                                 text="Análise e produtos", padding=10)
        analise.pack(fill="x")
        self._campo(analise, 0, "Ano de referência:", self.ano,
                    "Ano considerado nas séries temporais e nos indicadores.")
        self._campo(analise, 1, "População de referência:", self.populacao,
                    "Denominador dos coeficientes (Salvador, Censo 2022).")
        self._campo(analise, 2, "Meses a projetar:", self.horizonte,
                    "Horizonte das projeções.")

        linha_referencia = ttk.Frame(analise)
        linha_referencia.grid(row=3, column=0, columnspan=3, sticky="ew",
                              pady=(6, 0))
        ttk.Label(linha_referencia,
                  text="Amostra de referência:").pack(side="left")
        ttk.Entry(linha_referencia, textvariable=self.referencia,
                  width=38).pack(side="left", padx=(8, 4))
        ttk.Button(linha_referencia, text="…", width=3,
                   command=self._escolher_referencia).pack(side="left")
        ttk.Label(linha_referencia,
                  text=("Opcional — permite calcular sensibilidade e valor "
                        "preditivo positivo."),
                  style="Nota.TLabel").pack(side="left", padx=(8, 0))

        opcoes = ttk.Frame(analise)
        opcoes.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Checkbutton(opcoes, text="Gerar planilha de resultados",
                        variable=self.gerar_planilha_var).pack(side="left")
        ttk.Checkbutton(opcoes, text="Gerar relatório analítico",
                        variable=self.gerar_relatorio_var).pack(side="left",
                                                                padx=(16, 0))
        ttk.Checkbutton(opcoes,
                        text="Pseudonimizar identificadores na planilha",
                        variable=self.pseudonimizar).pack(side="left",
                                                          padx=(16, 0))

    def _campo(self, pai, linha: int, rotulo: str, variavel, nota: str) -> None:
        ttk.Label(pai, text=rotulo).grid(row=linha, column=0, sticky="w",
                                         pady=2)
        ttk.Entry(pai, textvariable=variavel, width=12).grid(
            row=linha, column=1, sticky="w", padx=(8, 8), pady=2)
        ttk.Label(pai, text=nota, style="Nota.TLabel").grid(
            row=linha, column=2, sticky="w", pady=2)

    def _alternar_avancado(self) -> None:
        if self.avancado_visivel.get():
            self.quadro_avancado.pack_forget()
            self.botao_avancado.configure(text="▸ Opções avançadas")
            self.avancado_visivel.set(False)
        else:
            self.quadro_avancado.pack(fill="x", before=self.quadro_execucao)
            self.botao_avancado.configure(text="▾ Opções avançadas")
            self.avancado_visivel.set(True)

    # ------------------------------------------------------------------ #
    # Passo 3 — execução
    # ------------------------------------------------------------------ #

    def _montar_execucao(self, pai) -> None:
        self.quadro_execucao = ttk.Frame(pai, padding=(0, 12, 0, 0))
        self.quadro_execucao.pack(fill="x")

        ttk.Label(self.quadro_execucao, text="3. Executar a análise",
                  style="Passo.TLabel").pack(anchor="w")

        linha = ttk.Frame(self.quadro_execucao)
        linha.pack(fill="x", pady=(6, 0))
        self.botao_executar = ttk.Button(
            linha, text="Analisar e gerar produtos",
            style="Executar.TButton", command=self._executar)
        self.botao_executar.pack(side="left")
        self.botao_abrir = ttk.Button(linha, text="Abrir pasta de resultados",
                                      command=self._abrir_pasta,
                                      state="disabled")
        self.botao_abrir.pack(side="left", padx=(8, 0))

        self.progresso = ttk.Progressbar(self.quadro_execucao, mode="determinate",
                                         maximum=100)
        self.progresso.pack(fill="x", pady=(10, 4))
        self.mensagem = ttk.Label(self.quadro_execucao,
                                  text="Aguardando as bases de dados.",
                                  style="Subtitulo.TLabel")
        self.mensagem.pack(anchor="w")

        self.resumo = tk.Text(self.quadro_execucao, height=6, wrap="word",
                              font=("Consolas", 9), relief="flat",
                              background="#f4f4f2", foreground="#0b0b0b",
                              state="disabled")
        self.resumo.pack(fill="both", expand=True, pady=(8, 0))

    # ------------------------------------------------------------------ #
    # Ações
    # ------------------------------------------------------------------ #

    def _adicionar(self) -> None:
        escolhidos = filedialog.askopenfilenames(
            title="Selecione as bases de dados",
            filetypes=TIPOS_DE_ARQUIVO)
        novos = 0
        for caminho in escolhidos:
            caminho = Path(caminho)
            if caminho in self.arquivos:
                continue
            self.arquivos.append(caminho)
            novos += 1
            self._inserir_na_lista(caminho)
        if novos:
            self._atualizar_mensagem(
                f"{len(self.arquivos)} base(s) selecionada(s). "
                f"Confira a identificação de cada sistema antes de executar.")

    def _inserir_na_lista(self, caminho: Path) -> None:
        try:
            tamanho = caminho.stat().st_size
            texto_tamanho = (f"{tamanho / 1_048_576:.1f} MB"
                             if tamanho >= 1_048_576
                             else f"{tamanho / 1024:.0f} KB")
        except OSError:
            texto_tamanho = "—"

        registros = contar_registros(caminho)
        texto_registros = (f"{registros:,}".replace(",", ".")
                           if registros >= 0 else "a apurar")

        sistema = "a identificar"
        try:
            from .leitura import ler_base
            amostra = ler_base(caminho, limite=5)
            sistema = identificar_sistema(list(amostra.columns),
                                          caminho.name).sigla
        except Exception:
            pass

        self.lista.insert("", "end", values=(caminho.name, sistema,
                                             texto_registros, texto_tamanho))

    def _remover(self) -> None:
        for item in self.lista.selection():
            indice = self.lista.index(item)
            if 0 <= indice < len(self.arquivos):
                self.arquivos.pop(indice)
            self.lista.delete(item)
        self._atualizar_mensagem(f"{len(self.arquivos)} base(s) selecionada(s).")

    def _escolher_saida(self) -> None:
        escolhido = filedialog.askdirectory(title="Pasta para os resultados")
        if escolhido:
            self.diretorio_saida.set(escolhido)

    def _escolher_referencia(self) -> None:
        escolhido = filedialog.askopenfilename(
            title="Amostra de referência (colunas SISTEMA, ID_PESSOA, REGISTRO)",
            filetypes=[("Planilhas e texto", "*.csv *.xlsx *.xls"),
                       ("Todos os arquivos", "*.*")])
        if escolhido:
            self.referencia.set(escolhido)

    def _gerar_exemplo(self) -> None:
        destino = filedialog.askdirectory(
            title="Onde salvar as bases fictícias de exemplo")
        if not destino:
            return
        try:
            from .dados_ficticios import salvar_bases
            self._atualizar_mensagem("Gerando bases fictícias…")
            self.update_idletasks()
            caminhos = salvar_bases(destino, formato="csv")
        except Exception as erro:
            messagebox.showerror("ELO-SIS", f"Não foi possível gerar as bases "
                                            f"de exemplo.\n\n{erro}")
            return

        for sigla, caminho in caminhos.items():
            if sigla == "GABARITO":
                self.referencia.set(str(caminho))
                continue
            if caminho not in self.arquivos:
                self.arquivos.append(caminho)
                self._inserir_na_lista(caminho)

        messagebox.showinfo(
            "ELO-SIS",
            "Bases fictícias geradas e adicionadas à lista.\n\n"
            "Elas contêm defeitos deliberados — duplicidades, incompletude, "
            "códigos fora de domínio e erros de digitação — para que se possa "
            "conhecer o comportamento da ferramenta antes de usá-la com bases "
            "reais.\n\nO gabarito de pareamento foi indicado automaticamente "
            "como amostra de referência, o que permite calcular a "
            "sensibilidade e o valor preditivo positivo.")
        self._atualizar_mensagem("Bases de exemplo prontas. Pode executar.")

    def _executar(self) -> None:
        if self.em_execucao:
            return
        if not self.arquivos:
            messagebox.showwarning(
                "ELO-SIS",
                "Selecione ao menos uma base de dados.\n\nSe quiser conhecer a "
                "ferramenta antes de usar bases reais, use o botão “Gerar "
                "bases de exemplo”.")
            return

        destino = Path(self.diretorio_saida.get().strip()
                       or Path.home() / "ELO-SIS")
        try:
            destino.mkdir(parents=True, exist_ok=True)
        except OSError as erro:
            messagebox.showerror(
                "ELO-SIS",
                f"Não foi possível usar a pasta indicada para os "
                f"resultados.\n\n{erro}\n\nEscolha outra pasta.")
            return

        rotulo_perspectiva = self.perspectiva.get()
        perspectivas = {}
        for chave, definicao in PERSPECTIVAS.items():
            if definicao["rotulo"] == rotulo_perspectiva:
                perspectivas = {"SINASC": chave}

        configuracao = Configuracao(
            arquivos=list(self.arquivos),
            diretorio_saida=destino,
            limiar_pareamento=float(self.limiar.get()),
            limiar_revisao=float(self.limiar_revisao.get()),
            limiar_duplicidade=float(self.limiar_duplicidade.get()),
            ano_referencia=int(self.ano.get()),
            populacao_referencia=int(self.populacao.get()),
            horizonte_projecao=int(self.horizonte.get()),
            pseudonimizar_saida=bool(self.pseudonimizar.get()),
            gerar_planilha=bool(self.gerar_planilha_var.get()),
            gerar_relatorio=bool(self.gerar_relatorio_var.get()),
            arquivo_referencia=(Path(self.referencia.get())
                                if self.referencia.get().strip() else None),
            perspectivas=perspectivas,
        )

        self.em_execucao = True
        self.botao_executar.configure(state="disabled",
                                      text="Processando…")
        self.botao_abrir.configure(state="disabled")
        self.progresso.configure(value=0)
        self._limpar_resumo()

        threading.Thread(target=self._trabalhar, args=(configuracao,),
                         daemon=True).start()

    def _trabalhar(self, configuracao: Configuracao) -> None:
        """Executa o fluxo em linha de execução própria."""
        try:
            def progresso(passo: str, fracao: float) -> None:
                self.fila.put(("progresso", (passo, fracao)))

            resultado = executar(configuracao, progresso)
            produtos = []
            if configuracao.gerar_planilha:
                self.fila.put(("progresso", ("Gerando a planilha…", 0.88)))
                produtos.append(gerar_planilha(resultado))
            if configuracao.gerar_relatorio:
                self.fila.put(("progresso",
                               ("Gerando o relatório analítico…", 0.94)))
                produtos.append(gerar_relatorio(resultado))
            produtos.append(resultado.trilha.salvar())
            self.fila.put(("concluido", (resultado, produtos)))
        except Exception as erro:
            self.fila.put(("erro", (erro, traceback.format_exc())))

    def _processar_fila(self) -> None:
        try:
            while True:
                tipo, conteudo = self.fila.get_nowait()
                if tipo == "progresso":
                    passo, fracao = conteudo
                    self.progresso.configure(value=fracao * 100)
                    self._atualizar_mensagem(passo)
                elif tipo == "concluido":
                    self._concluir(*conteudo)
                elif tipo == "erro":
                    self._falhar(*conteudo)
        except queue.Empty:
            pass
        self.after(120, self._processar_fila)

    def _concluir(self, resultado, produtos) -> None:
        self.em_execucao = False
        self.produtos = produtos
        self.progresso.configure(value=100)
        self.botao_executar.configure(state="normal",
                                      text="Analisar e gerar produtos")
        self.botao_abrir.configure(state="normal")
        self._atualizar_mensagem(
            f"Concluído em {resultado.tempo_total:.1f} segundos. "
            f"Nenhum dado saiu desta estação.")

        linhas = ["RESUMO DA ANÁLISE", "-" * 72,
                  f"{'Base':<10}{'Registros':>10}{'Escore':>9}"
                  f"{'Verdes':>9}{'Amarelas':>10}{'Vermelhas':>11}"]
        for linha in resultado.resumo_executivo():
            linhas.append(
                f"{linha['BASE']:<10}{linha['REGISTROS']:>10,}"
                f"{linha['ESCORE_DE_QUALIDADE']:>9.2f}"
                f"{linha['LINHAS_VERDES']:>9,}{linha['LINHAS_AMARELAS']:>10,}"
                f"{linha['LINHAS_VERMELHAS']:>11,}".replace(",", "."))

        if resultado.pareamentos:
            linhas += ["", "PAREAMENTOS", "-" * 72]
            for pareamento in resultado.pareamentos:
                r = pareamento.resumo()
                linhas.append(
                    f"{r['RELACIONAMENTO']:<16}"
                    f"determinísticos: {r['PARES_DETERMINISTICOS']:>5}   "
                    f"probabilísticos: {r['PARES_PROBABILISTICOS']:>5}   "
                    f"revisão: {r['PARES_PARA_REVISAO_MANUAL']:>5}")

        if resultado.validacoes:
            linhas += ["", "DESEMPENHO", "-" * 72]
            for validacao in resultado.validacoes:
                linhas.append(
                    f"{validacao.relacionamento:<16}"
                    f"sensibilidade: {100 * validacao.sensibilidade:5.1f}%   "
                    f"VPP: {100 * validacao.valor_preditivo_positivo:5.1f}%")

        if resultado.avisos:
            linhas += ["", "AVISOS", "-" * 72]
            linhas += [f"• {a}" for a in resultado.avisos]

        linhas += ["", "PRODUTOS GERADOS", "-" * 72]
        linhas += [f"• {Path(p).name}" for p in produtos]

        self._escrever_resumo("\n".join(linhas))

        messagebox.showinfo(
            "ELO-SIS",
            f"Análise concluída em {resultado.tempo_total:.1f} segundos.\n\n"
            f"Foram gerados {len(produtos)} arquivos na pasta de resultados.\n\n"
            f"Comece pela planilha: a aba 00_LEIA-ME explica como ler as cores "
            f"e como conduzir o trabalho de correção.")

    def _falhar(self, erro: Exception, detalhe: str) -> None:
        self.em_execucao = False
        self.progresso.configure(value=0)
        self.botao_executar.configure(state="normal",
                                      text="Analisar e gerar produtos")
        self._atualizar_mensagem("A análise não pôde ser concluída.")
        self._escrever_resumo(detalhe)
        messagebox.showerror(
            "ELO-SIS",
            f"A análise não pôde ser concluída.\n\n{erro}\n\n"
            f"Verifique se os arquivos selecionados são bases de dados "
            f"válidas e se não estão abertos em outro programa. O detalhamento "
            f"técnico aparece na janela de resumo.")

    def _abrir_pasta(self) -> None:
        destino = Path(self.diretorio_saida.get())
        try:
            webbrowser.open(destino.resolve().as_uri())
        except Exception:
            messagebox.showinfo("ELO-SIS",
                                f"Os resultados estão em:\n\n{destino.resolve()}")

    # ------------------------------------------------------------------ #
    # Auxiliares de interface
    # ------------------------------------------------------------------ #

    def _atualizar_mensagem(self, texto: str) -> None:
        self.mensagem.configure(text=texto)

    def _limpar_resumo(self) -> None:
        self.resumo.configure(state="normal")
        self.resumo.delete("1.0", "end")
        self.resumo.configure(state="disabled")

    def _escrever_resumo(self, texto: str) -> None:
        self.resumo.configure(state="normal")
        self.resumo.delete("1.0", "end")
        self.resumo.insert("1.0", texto)
        self.resumo.configure(state="disabled")


def abrir_interface() -> int:
    raiz = tk.Tk()
    raiz.title(f"ELO-SIS {__version__} — Pareamento de bases dos sistemas "
               f"de informação em saúde")
    raiz.geometry("1020x900")
    raiz.minsize(900, 700)
    JanelaPrincipal(raiz)
    raiz.mainloop()
    return 0
