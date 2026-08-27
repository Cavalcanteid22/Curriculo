# Comece aqui — passo a passo para quem nunca usou

Não é preciso saber programar. São **três coisas** para fazer uma vez só
(baixar, instalar o Python, abrir) e depois é sempre igual.

---

## Parte 1 — Baixar a ferramenta (uma vez só)

1. Abra no navegador:
   `https://github.com/Cavalcanteid22/Curriculo/tree/claude/health-systems-quality-assessment-9retso`
2. Clique no botão verde **`Code`** → **`Download ZIP`**.
3. O arquivo cai na pasta **Downloads**. Clique com o botão direito nele →
   **Extrair tudo** → escolha um lugar fácil, por exemplo `C:\QualiSIS`.
4. Dentro da pasta extraída, entre em **`qualidade-sis`**. É essa a pasta de trabalho.

> Guarde essa pasta num lugar fixo (não na área de trabalho de um computador só).
> Se o setor tiver pasta de rede, melhor ainda.

---

## Parte 2 — Instalar o Python (uma vez só, por computador)

O Python é gratuito e é o "motor" que faz a ferramenta rodar.

1. Acesse **https://www.python.org/downloads/**
2. Clique no botão grande **Download Python**.
3. Abra o arquivo baixado. **Na primeira tela, marque a caixinha
   `Add Python to PATH`** (fica embaixo, é fácil não ver) e só então clique em
   *Install Now*.
4. Espere terminar e feche.

> Sem permissão para instalar programas? Peça ao suporte de TI da Secretaria.
> É um software padrão, gratuito e sem risco. Diga que é "Python 3, com a opção
> Add to PATH marcada".

Para conferir se deu certo, siga para a parte 3: se abrir o menu, está tudo certo.

---

## Parte 3 — Abrir a ferramenta

Dentro da pasta `qualidade-sis`, **dê dois cliques em `EXECUTAR_WINDOWS.bat`**.

Abre uma janela preta com o menu:

```
  ANALISAR A BASE DE UM SISTEMA:
    1. ESUS_SINAN    e-SUS SINAN — notificação de agravos em plataforma web
    2. SIM           Sistema de Informação sobre Mortalidade
    3. SINAN         Sistema de Informação de Agravos de Notificação (SINAN NET)
    4. SINAN_ONLINE  SINAN Online — notificação de tuberculose e hanseníase
    5. SINASC        Sistema de Informações sobre Nascidos Vivos

  OUTRAS OPÇÕES:
    C. Painel consolidado (compara todos os sistemas já analisados)
    V. Conferir se o layout do CSV bate com o dicionário
    H. Ver o histórico de análises de um sistema
    E. EXEMPLO — testar a ferramenta com base fictícia, sem usar dado real
    S. Sair
```

A janela preta assusta, mas ela só faz perguntas. Você digita o número ou a
letra, tecla **Enter**, e pronto.

---

## Parte 4 — Primeiro teste: a letra `E`

**Antes de usar base real, digite `E` e tecle Enter.**

A ferramenta cria uma base inventada (nomes e números aleatórios, nada real),
analisa dois "envios" seguidos e abre o relatório no navegador. Serve para você
ver como fica o resultado sem risco nenhum. Leva menos de um minuto.

Ao final ela pergunta se quer abrir o relatório — responda **S**.

---

## Parte 5 — Usando a base de verdade

### 5.1 Exportar a base do sistema

No SIM, SINASC, SINAN etc., exporte a base **em CSV**, com todos os campos.
Salve numa pasta fácil de achar, por exemplo `C:\Bases\SIM_2026-07.csv`.

> **Não abra o CSV no Excel antes de analisar.** O Excel estraga datas e corta
> os zeros da frente (número da DO, CNES, CEP). Se precisar espiar, faça uma cópia.

### 5.2 Conferir o layout (só na primeira vez de cada sistema)

No menu, digite **`V`** → escolha o sistema → informe o arquivo.

Ela mostra quantos campos reconheceu. Se aparecer uma lista grande de campos
"ausentes", é porque sua exportação usa outros nomes de coluna — **me mande essa
lista** que eu ajusto a configuração. Enquanto isso a análise funciona, só não
avalia os campos que ela não reconheceu.

### 5.3 Analisar

No menu, digite o **número do sistema** (por exemplo `2` para o SIM) → Enter.

Ela pede o arquivo. Aqui vai o truque que evita digitar caminho:

> **Arraste o arquivo CSV do Explorer para dentro da janela preta e solte.**
> O caminho aparece sozinho. Depois é só teclar Enter.

Depois ela faz duas perguntas — pode teclar Enter nas duas:

* *Data da extração* — Enter usa a data do arquivo;
* *Pintar a linha inteira?* — Enter mantém só a célula com problema colorida
  (responda `s` se preferir a linha toda pintada).

Aí é esperar. Bases grandes levam alguns minutos; o andamento aparece na tela.

### 5.4 Ver o resultado

Ao terminar, ela mostra a pasta e pergunta se quer abrir. Responda **S**:
abre a pasta e o relatório.

Você vai encontrar:

| Arquivo | O que fazer com ele |
|---|---|
| `SIM_relatorio.html` | **abra primeiro** — é a leitura da situação, com gráficos |
| `SIM_inconsistencias.xlsx` | a planilha colorida, para trabalhar e mandar às unidades |
| `SIM_instrumento_qualitativo.xlsx` | preencher a cada trimestre (notas de 1 a 5) |
| os arquivos `.csv` | para tabela dinâmica, se você quiser cruzar do seu jeito |

---

## Parte 6 — A rotina, depois que pegar o jeito

| Quando | O que fazer |
|---|---|
| A cada envio da base | abrir a ferramenta, analisar cada sistema, ler o relatório, mandar a lista para as unidades |
| A cada trimestre | preencher o instrumento qualitativo e gerar o painel consolidado (letra `C`) |
| A cada semestre | conferência por amostra (ver `docs/metodologia.md`, bloco C) |

Na segunda vez que você analisar o mesmo sistema, o relatório passa a ter a
seção **"Comparativo com o envio anterior"** — é ali que aparece quanto do que
foi apontado já foi corrigido. **Por isso vale analisar todo mês, mesmo que você
não vá olhar tudo:** é o histórico que gera essa comparação.

---

## Se der problema

| O que aconteceu | O que fazer |
|---|---|
| A janela preta abre e fecha na hora | O Python não está instalado ou não foi marcada a opção *Add Python to PATH*. Refaça a parte 2. |
| "Arquivo não encontrado" | Prefira arrastar o arquivo para a janela em vez de digitar o caminho. |
| Acentos estranhos no relatório | Me avise qual sistema — é um ajuste de uma linha na configuração. |
| Tudo virou uma coluna só | O separador do CSV é diferente. Também é ajuste de uma linha. |
| Demorou muito / travou | Veja o tamanho do arquivo. Acima de 1 GB, rode fora do horário de pico. |
| Mensagem de erro que você não entende | Tire uma foto da tela e me mande — a mensagem diz onde parou. |

---

## O que NUNCA precisa fazer

* Não precisa instalar Excel especial, Access, nem nada além do Python.
* Não precisa de internet para analisar — tudo roda no seu computador.
* Não precisa mexer em nenhum arquivo de código.
* Não precisa apagar as pastas `saida` e `historico`: é delas que sai a
  comparação entre um envio e outro.

## Cuidado com os dados

As bases têm dado pessoal sensível. A ferramenta não manda nada para lugar
nenhum, mas as pastas `saida` e `historico` ficam no seu computador — mantenha
em local com acesso restrito ao setor. E, ao enviar a lista para uma unidade,
**filtre e mande só as linhas daquela unidade**.
