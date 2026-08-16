# Consolidador de Sistemas

Aplicativo para executar, de forma rotineira e automática, a consolidação de arquivos de
**dois sistemas**, a **análise de atributos de qualidade** de cada base, o **pareamento**
entre elas e a **comparação** do que existe em um sistema e não existe no outro.

Cada execução gera **dois arquivos**:

| Arquivo | Conteúdo |
| --- | --- |
| `Consolidacao_<Sistema1>_x_<Sistema2>_<data>.xlsx` | Planilha com 9 abas (as 7 pedidas + resumo executivo + auditoria da leitura) |
| `Consolidacao_<Sistema1>_x_<Sistema2>_<data>.docx` | Relatório analítico, descritivo e comparativo, em Word |

## Abas da planilha

1. **Resumo** — painel executivo: volumes, notas de qualidade e resultado do pareamento.
2. **Consolidado \<Sistema 1\>** — todos os registros do primeiro sistema, com a origem de cada
   linha (arquivo e linha) e a situação no pareamento.
3. **Consolidado \<Sistema 2\>** — o mesmo para o segundo sistema.
4. **Qualidade \<Sistema 1\>** — notas por dimensão, indicadores por campo e a lista completa de
   inconsistências, registro a registro.
5. **Qualidade \<Sistema 2\>** — o mesmo para o segundo sistema.
6. **Pareamento** — os pares encontrados, com critério, escore e comparação campo a campo
   (**as divergências saem realçadas em amarelo**).
7. **Somente em \<Sistema 1\>** — o que existe no primeiro e não foi localizado no segundo,
   **realçado em laranja**, com a coluna "Por que consta como ausente" e o registro mais parecido.
8. **Somente em \<Sistema 2\>** — o inverso, **realçado em azul**.
9. **Arquivos lidos** — qual arquivo virou qual sistema, por qual critério e com qual confiança.

## Instalação

Nenhuma. Basta ter **Python 3.8 ou superior** instalado
([python.org/downloads](https://www.python.org/downloads/) — na instalação, marque
"Add Python to PATH"). O aplicativo não usa nenhuma biblioteca externa: lê e grava
`.xlsx` e `.docx` diretamente.

## Como usar (janela)

- **Windows:** duplo clique em `Consolidador.bat` (ou em `executar.py`).
- **Linux/macOS:** `python3 executar.py`

Na janela:

1. **Adicionar arquivos** ou **Adicionar pasta** — pode misturar formatos à vontade.
2. Conferir a coluna **Sistema**. Fica `(automatico)` por padrão; para corrigir, selecione a
   linha e clique em **Sistema 1** / **Sistema 2** (ou dê duplo clique para alternar).
3. Escolher a **pasta de saída** (e, se houver, o **perfil**).
4. **Executar rotina**. Ao final, o resumo aparece na tela e o botão
   **Abrir pasta de resultados** leva aos dois arquivos gerados.

## Como usar (linha de comando)

```bash
python consolidar.py minha_pasta_de_entradas -s minha_pasta_de_saidas

# arquivos avulsos
python consolidar.py rel_siga.html base_rhnet.dbf folha.xlsx -s saidas

# forçando qual arquivo é de qual sistema
python consolidar.py entradas --sistema-a "SIGA*" --sistema-b "RHNET*"

# usando um perfil salvo e nomeando os sistemas
python consolidar.py entradas -p perfis/meu_perfil.json --nome-a "Folha" --nome-b "RH"

# gerando um perfil a partir do que a rotina descobriu sozinha
python consolidar.py entradas --salvar-perfil perfis/meu_perfil.json
```

## Formatos de entrada aceitos

`.xlsx`, `.xlsm`, `.ods`, `.csv`, `.txt`, `.tsv`, `.dbf`, `.html`, `.htm`, `.json`, `.xml`.

A leitura já resolve as chatices do dia a dia:

- separador do CSV (`;`, `,`, tabulação ou `|`) e codificação (UTF-8, ANSI/Windows-1252) detectados
  automaticamente;
- planilhas com título, data de emissão e linhas em branco **antes** do cabeçalho real;
- relatórios em HTML quebrados em vários blocos por página, com `colspan` e `rowspan`;
- DBF com nomes de campo truncados em 10 caracteres (`NOMECOMPL` é reconhecido como
  `Nome completo`), datas `AAAAMMDD` e registros marcados como excluídos;
- números no padrão brasileiro (`1.234,56`, `R$ 2.000,00`, `(150,25)` como negativo).

> Arquivos `.xls` antigos (Excel 97-2003) não são lidos diretamente: abra no Excel e salve como
> `.xlsx` ou `.csv`.

## Como o aplicativo sabe qual arquivo é de qual sistema

1. **Com perfil:** pelas regras configuradas — padrão do nome do arquivo, nome da aba e colunas
   esperadas de cada sistema.
2. **Sem perfil (modo automático):** os arquivos são agrupados em dois conjuntos por semelhança
   de cabeçalho e de nome de arquivo; o nome do sistema é deduzido do trecho comum aos nomes dos
   arquivos (por exemplo `SIGA_servidores_2026-07.csv` → sistema **SIGA**).

Em qualquer caso, a atribuição pode ser corrigida na tela, e a aba **Arquivos lidos** registra o
critério e a confiança de cada decisão.

## Dimensões de qualidade avaliadas

| Dimensão | O que mede | Exemplo do que é apontado |
| --- | --- | --- |
| Completude | Campos preenchidos | CPF em branco |
| Unicidade | Repetição indevida | Mesma matrícula em dois registros; registro duplicado |
| Validade | Formato e domínio | CPF/CNPJ com dígito errado, e-mail inválido, valor fora da lista |
| Consistência | Coerência entre campos | Fim da vigência anterior ao início |
| Padronização | Escrita uniforme | `SAO PAULO`, `São Paulo` e espaços duplicados |
| Acurácia | Plausibilidade | Data em 1899, valor muito fora da faixa (outlier) |
| Atualidade | Idade da informação | Base cujo registro mais novo é antigo |

Cada campo recebe nota de 0 a 100 e cada ocorrência é classificada em gravidade
**Alta**, **Média** ou **Baixa**, com o registro de origem (arquivo e linha) para conferência.

## Como funciona o pareamento

Três passadas, da mais segura para a mais tolerante:

1. **Chave primária** — igualdade exata do valor normalizado (CPF/CNPJ pelos dígitos, códigos sem
   pontuação, sem diferença de acento ou caixa).
2. **Chaves alternativas** — outros campos (ou combinação de campos) definidos no perfil ou
   deduzidos automaticamente.
3. **Similaridade** — comparação aproximada (Jaro-Winkler + palavras) para os registros que
   sobraram, com bloqueio por palavra para não comparar todos contra todos. Acima de 90% o par é
   *provável*; entre 78% e 90% é marcado como **duvidoso, para conferência manual**.

Registros que casam com mais de um do outro lado são marcados com a multiplicidade
(ex.: `2:1 (revisar duplicidade)`), porque isso indica duplicidade na origem.

## Perfil (opcional, mas recomendado para a rotina)

O perfil é um arquivo `.json` que fixa as regras: nome dos sistemas, como reconhecer os arquivos,
o de-para dos nomes de coluna, o tipo e a obrigatoriedade de cada campo, as chaves do pareamento e
as regras de consistência. Veja `perfis/exemplo_dois_sistemas.json`.

O caminho mais curto: rode uma vez sem perfil, confira o resultado e depois gere o ponto de partida
com `--salvar-perfil`; em seguida ajuste os nomes dos campos canônicos no arquivo gerado.

## Volume suportado

Não há limite fixo. Como referência medida nesta versão, duas bases de 17 mil registros cada
(34 mil no total, com 6 colunas) são processadas por completo — leitura, qualidade, pareamento,
planilha e relatório — em cerca de **1 minuto e 20 segundos**, gerando uma planilha de 5 MB.
Arquivos do dia a dia (centenas ou poucos milhares de linhas) rodam em segundos.

## Estrutura do projeto

```
consolidador/
├── executar.py                  # abre a janela
├── consolidar.py                # linha de comando
├── Consolidador.bat             # atalho para Windows
├── perfis/                      # perfis de configuração
├── exemplos/entradas/           # arquivos de demonstração (CSV, XLSX, HTML, DBF)
├── testes/
│   ├── gerar_dados_exemplo.py   # recria os arquivos de demonstração
│   └── teste_ponta_a_ponta.py   # 29 testes automatizados
└── nucleo/
    ├── leitores.py              # leitura de cada formato
    ├── deteccao.py              # de qual sistema é cada arquivo
    ├── normalizacao.py          # consolidação e de-para de colunas
    ├── qualidade.py             # análise dos atributos de qualidade
    ├── pareamento.py            # pareamento entre os sistemas
    ├── relatorio_xlsx.py        # montagem da planilha
    ├── relatorio_docx.py        # montagem do relatório
    ├── xlsx_writer.py           # gravação de .xlsx sem bibliotecas externas
    ├── docx_writer.py           # gravação de .docx sem bibliotecas externas
    └── pipeline.py              # orquestração das etapas
```

## Demonstração e testes

```bash
python testes/gerar_dados_exemplo.py exemplos/entradas   # recria os arquivos de exemplo
python consolidar.py exemplos/entradas -s exemplos/saidas
python testes/teste_ponta_a_ponta.py                     # 29 testes
```

Os arquivos de exemplo trazem problemas de propósito (CPF inválido, chave em branco, registro
duplicado, data em 1899, valor fora da faixa, grafias diferentes, registros que só existem em um
dos sistemas e um registro sem chave que só pode ser pareado por semelhança de nome), para que dê
para conferir cada parte do resultado.
