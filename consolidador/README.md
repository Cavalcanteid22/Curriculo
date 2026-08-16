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

`.xlsx`, `.xlsm`, `.xls`, `.ods`, `.csv`, `.txt`, `.tsv`, `.dbf`, `.html`, `.htm`, `.json`,
`.xml` e `.zip` (pasta compactada com um ou mais dos anteriores).

O formato é reconhecido **pelo conteúdo, não pela extensão** — o que resolve o caso mais comum
dos sistemas públicos: o relatório vem com nome `RELATORIO_5.xls` mas por dentro é HTML.

A leitura já resolve as chatices do dia a dia:

- separador do CSV (`;`, `,`, tabulação ou `|`) e codificação (UTF-8, ANSI/Windows-1252) detectados
  automaticamente;
- planilhas com título, data de emissão e linhas em branco **antes** do cabeçalho real;
- relatórios em HTML quebrados em vários blocos por página, com `colspan` e `rowspan`;
- DBF com nomes de campo truncados em 10 caracteres (`NOMECOMPL` é reconhecido como
  `Nome completo`), datas `AAAAMMDD` e registros marcados como excluídos;
- números no padrão brasileiro (`1.234,56`, `R$ 2.000,00`, `(150,25)` como negativo);
- relatórios de sistema com brasão, título do órgão e data de emissão antes do cabeçalho real,
  e com o cabeçalho repetido a cada quebra de página (as repetições não viram registros);
- blocos de identificação no meio do relatório (`Nome do usuário: FULANO`,
  `DISPENSADOR: ... DATA DISPENSA: ...`) viram **colunas** aplicadas aos registros seguintes;
- planilha "salva como página da web" pelo Excel: o arquivo índice é seguido até a pasta
  `..._arquivos/sheet001.htm`. Se a pasta não estiver junto, a mensagem explica as três saídas
  (usar o arquivo como veio do sistema, salvar como `.xlsx`, ou compactar arquivo + pasta em um
  `.zip` e usar o `.zip` como entrada);
- `Planilha XML 2003` do Excel (SpreadsheetML).

> Só não é lido o `.xls` **binário** de verdade (Excel 97-2003 salvo como pasta de trabalho):
> nesse caso a mensagem pede para abrir no Excel e salvar como `.xlsx` ou `.csv`.

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
   sobraram, com bloqueio pelas palavras mais raras para não comparar todos contra todos.

**Semelhança de nome, sozinha, não fecha um par.** Homônimos e nomes próximos são comuns
(`MARIA DOS SANTOS SILVA` × `MARIA SANTOS DA SILVA`), e em base de saúde ou de pessoal um
falso par é pior do que nenhum. Por isso, havendo outro campo comparável, ao menos um precisa
coincidir — de preferência um campo discriminante (data de nascimento, código, documento);
campos com poucos valores possíveis, como `TIPO` ou `SITUAÇÃO`, contam menos e sozinhos não
confirmam nada. Sem nenhum campo de apoio, só um casamento praticamente perfeito é aceito.
Acima de 90% e confirmado, o par é *provável*; o resto é marcado como
**duvidoso, para conferência manual**.

A chave **não precisa ser única nos dois sistemas**: é comum um deles trazer uma linha por
atendimento/dispensação e o outro uma linha por pessoa. Nesse caso o pareamento é 1:N e cada
par sai marcado com a multiplicidade.

Registros que casam com mais de um do outro lado são marcados com a multiplicidade
(ex.: `2:1 (revisar duplicidade)`), porque isso indica duplicidade na origem.

## Perfil (opcional, mas recomendado para a rotina)

O perfil é um arquivo `.json` que fixa as regras: nome dos sistemas, como reconhecer os arquivos,
o de-para dos nomes de coluna, o tipo e a obrigatoriedade de cada campo, as chaves do pareamento e
as regras de consistência. Veja `perfis/exemplo_dois_sistemas.json`.

O caminho mais curto: rode uma vez sem perfil, confira o resultado e depois gere o ponto de partida
com `--salvar-perfil`; em seguida ajuste os nomes dos campos canônicos no arquivo gerado.

Perfis prontos incluídos:

| Perfil | Para que serve |
| --- | --- |
| `perfis/exemplo_dois_sistemas.json` | Modelo comentado, com todas as opções |
| `perfis/siclom_cadastrados_x_ativos.json` | Cruzamento entre o relatório de usuários cadastrados (`.xls` que é HTML) e a planilha de usuários ativos, pareando por nome + data de nascimento + nome da mãe, já que não há CPF nos dois lados |
| `perfis/siclom_hepatites_x_sinan.json` | Conferência "todo paciente ativo no SICLOM Hepatites deveria estar notificado no SINAN": pareia por CPF e, na falta dele, por nome + data de nascimento ou nome + nome da mãe |
| `perfis/siclom_dispensacoes_x_ativos.json` | Confere a lista de usuários ativos contra o que foi efetivamente dispensado (uma linha por dispensação × uma linha por pessoa: pareamento 1:N) |

### A conferência SICLOM × SINAN, passo a passo

1. No SICLOM Hepatites, exporte o relatório de usuários (cadastrados ou ativos) **do agravo que
   vai conferir** — HBV ou HCV — e do período desejado. O arquivo vem como `RELATORIO_N.xls`.
2. No SINAN/Hepatonet, exporte as notificações **do mesmo agravo e do mesmo período**.
3. Abra o aplicativo, adicione os dois arquivos, escolha o perfil
   `perfis/siclom_hepatites_x_sinan.json` e execute.
4. A aba **"Somente em SICLOM Hepatites"** é a resposta da rotina: os pacientes que retiram
   medicamento e não foram localizados nas notificações. A coluna "Por que consta como ausente"
   distingue quem simplesmente não existe no SINAN de quem tem lá um registro parecido (provável
   erro de digitação no nome ou na data), que aparece com o percentual de semelhança.

> Exporte os dois lados para o **mesmo agravo**. Uma lista de HCV comparada com uma de HBV não
> tem interseção nenhuma, e o resultado será "tudo exclusivo dos dois lados".

## Dados pessoais e sigilo

O aplicativo funciona inteiramente na sua máquina: não envia nada para a internet, não usa
serviço externo e não guarda cópia dos arquivos. Ainda assim, **os arquivos de entrada e os
resultados costumam conter dados pessoais e de saúde** — nome, CPF, endereço, telefone,
diagnóstico. Guarde as pastas de entrada e de saída fora de qualquer pasta sincronizada
publicamente (e nunca dentro de um repositório do GitHub), e compartilhe os relatórios apenas
com quem tem competência para vê-los. Por isso as pastas `dados/`, `entradas/` e `saidas/` na
raiz do aplicativo já estão ignoradas pelo controle de versão.

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
│   └── teste_ponta_a_ponta.py   # 36 testes automatizados
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
python testes/teste_ponta_a_ponta.py                     # 36 testes
```

Os arquivos de exemplo trazem problemas de propósito (CPF inválido, chave em branco, registro
duplicado, data em 1899, valor fora da faixa, grafias diferentes, registros que só existem em um
dos sistemas e um registro sem chave que só pode ser pareado por semelhança de nome), para que dê
para conferir cada parte do resultado.
