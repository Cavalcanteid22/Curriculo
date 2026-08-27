# QualiSIS — avaliação da qualidade dos sistemas de informação em saúde

Ferramenta da **Subcoordenadoria de Informação em Saúde — SMS Salvador** para avaliar
rotineiramente a qualidade das bases do **SIM, SINAN, SINASC, e-SUS SINAN e SINAN Online**.

A partir do CSV exportado de cada sistema, o programa:

1. **pinta cada inconsistência com uma cor** numa planilha Excel — uma cor por tipo
   (vermelho = duplicidade, amarelo = campo em branco, laranja = ignorado, e assim por diante);
2. **calcula os indicadores dos atributos de qualidade** (completude, confiabilidade, validade,
   tempestividade, coerência, singularidade…) com numerador, denominador e fórmula explícitos;
3. **compara o envio atual com o anterior** e mede a **resolutividade** — quanto do que foi
   apontado na última análise já foi corrigido, o que persiste e o que é novo;
4. **gera relatório HTML** pronto para imprimir, anexar a processo e apresentar em reunião;
5. **gera o painel consolidado** comparando todos os sistemas do setor.

Roda com **Python puro** — sem pandas, sem instalar nada, sem precisar de administrador.
Lê as bases em fluxo, então funciona com arquivos grandes e acumulativos em máquina comum.

---

> **Nunca usou?** Comece por [`COMECE_AQUI.md`](COMECE_AQUI.md) — passo a passo
> ilustrado, do download à primeira análise, sem linha de comando.

## Instalação

Só é preciso ter Python 3.8 ou superior (Windows: baixe em python.org e marque
"Add Python to PATH" na instalação). Copie a pasta `qualidade-sis` para o computador
ou para a pasta de rede do setor. Pronto.

Para conferir:

```bash
python executar.py listar
```

No Windows dá para usar o atalho: duplo clique em **`EXECUTAR_WINDOWS.bat`** abre o menu.

---

## Uso no dia a dia

### 1. Conferir o layout da exportação (só na primeira vez de cada sistema)

```bash
python executar.py validar -s sim -b C:\bases\SIM_2026.csv
```

Mostra codificação, separador, quais campos do dicionário foram reconhecidos e quais colunas
da base não estão previstas. Se algum campo aparecer como ausente só porque a exportação usa
outro nome, cadastre o apelido em `configs/sim.json`, em `apelidos_colunas` — **não é preciso
mexer em código**.

### 2. Analisar a base

```bash
python executar.py analisar -s sim -b C:\bases\SIM_2026.csv
```

Opções úteis:

| Opção | Para que serve |
|---|---|
| `--data-extracao 31/07/2026` | data real da extração (padrão: data do arquivo) |
| `--pintar-linha-inteira` | pinta a linha toda com a cor da inconsistência mais grave |
| `--limite 5000` | processa só as 5.000 primeiras linhas (teste rápido) |
| `--instrumento` | gera também a planilha de avaliação qualitativa |
| `--max-linhas-excel 0` | não limitar o número de linhas exportadas para o Excel |
| `--sem-excel` / `--sem-html` / `--sem-csv` | gerar só o que interessa |

### 3. Ler os produtos

Tudo vai para `saida/<sistema>/<data_hora>/`:

| Arquivo | O que é |
|---|---|
| `SIM_inconsistencias.xlsx` | planilha colorida, célula a célula, com abas de resumo |
| `SIM_relatorio.html` | relatório completo com gráficos (abre em qualquer navegador) |
| `SIM_ocorrencias.csv` | uma linha por inconsistência — pronto para tabela dinâmica |
| `SIM_resumo_campos.csv` | completude, ignorados e erros de cada variável |
| `SIM_indicadores.csv` | indicadores por atributo de qualidade |
| `SIM_tempestividade.csv` | prazos, medianas e percentis |
| `SIM_serie_mensal.csv` | evolução mensal |
| `SIM_estratos.csv` | por unidade notificadora / distrito / agravo |
| `SIM_comparativo_envios.csv` | resolutividade desde o envio anterior |
| `SIM_instrumento_qualitativo.xlsx` | instrumento com fórmulas para os atributos não mensuráveis na base |

### 4. Painel consolidado do setor

```bash
python executar.py consolidar
```

Compara os cinco sistemas lado a lado: escore de cada um, matriz atributo × sistema,
composição das inconsistências, evolução entre avaliações e resolutividade.

### 5. Histórico

```bash
python executar.py historico -s sim
```

---

## As cores das inconsistências

| Cor | Tipo | Significado |
|---|---|---|
| 🟥 Vermelho | Duplicidade | registro repetido pela chave do sistema ou por chave provável (nome + data + mãe) |
| 🟨 Amarelo | Campo em branco | campo essencial sem preenchimento |
| 🟧 Laranja | Ignorado / Não informado | preenchido com 9, 99, 999, "IGNORADO" — completo, porém sem informação |
| 🟪 Roxo | Código inválido | valor fora do domínio do dicionário (categoria, CID, município, CNES) |
| 🟦 Azul | Data inválida ou incoerente | data inexistente, no futuro ou fora de ordem (nascimento depois do óbito) |
| 🟩 Verde-água | Incoerência entre campos | combinação impossível (homem com óbito puerperal, parto vaginal + cesárea) |
| 🩷 Rosa | Formato inválido | CNS, CPF, CEP, telefone ou máscara fora do padrão |
| 🟢 Verde | Valor fora de faixa | peso, idade, Apgar, consultas fora do plausível |
| ⬜ Cinza | Fora do prazo | notificação, digitação ou encerramento fora do prazo pactuado |

A mesma legenda está na aba **Legenda** da planilha e no relatório HTML.

---

## Como adaptar às regras do setor

Tudo o que é específico de cada sistema está nos arquivos `configs/*.json`:
campos, rótulos, domínios de resposta, códigos de ignorado, faixas numéricas, chaves de
duplicidade, prazos e regras cruzadas. Editar esses arquivos **não exige programação** —
a referência completa está em [`docs/dicionario_regras.md`](docs/dicionario_regras.md).

Casos comuns:

* **incluir um campo novo na crítica** → acrescente-o em `campos`;
* **mudar um prazo pactuado** → altere `prazo_dias` em `tempestividade`;
* **tornar um campo obrigatório na sua avaliação** → `"essencial": true`;
* **acrescentar uma crítica nova** → um item em `regras_cruzadas` (7 tipos disponíveis);
* **avaliar por distrito sanitário** → inclua a coluna de distrito em `campos_estratificacao`.

---

## Documentação

| Documento | Conteúdo |
|---|---|
| [`COMECE_AQUI.md`](COMECE_AQUI.md) | **passo a passo para quem nunca usou** — download, instalação do Python, primeiro teste |
| [`docs/metodologia.md`](docs/metodologia.md) | **como conduzir o trabalho**: os 40 atributos organizados em blocos, indicadores e fórmulas, rotina mensal/trimestral, fluxo de devolutiva, amostra de verificação, governança |
| [`docs/guia_rapido.md`](docs/guia_rapido.md) | passo a passo operacional, do export do sistema à devolutiva à unidade |
| [`docs/dicionario_regras.md`](docs/dicionario_regras.md) | referência técnica dos arquivos de configuração |

---

## Ver antes de rodar

A pasta [`exemplos/demonstracao/`](exemplos/demonstracao/) já traz os produtos prontos,
gerados a partir de base fictícia: o relatório HTML, a planilha colorida, o instrumento
qualitativo e o painel consolidado. Abra e veja como fica.

## Dados de teste

Para conhecer a ferramenta sem usar base real:

```bash
python exemplos/gerar_exemplos.py
python executar.py analisar -s sim -b exemplos/bases/SIM_envio1.csv
python executar.py analisar -s sim -b exemplos/bases/SIM_envio2.csv   # traz a resolutividade
python executar.py consolidar
```

As bases de exemplo são **fictícias** (nomes e números gerados aleatoriamente).

Depois de editar qualquer arquivo de `configs/`, rode o teste de fumaça — ele processa
tudo em base fictícia e confere se nada quebrou:

```bash
python testes/teste_rapido.py
```

## Desempenho medido

Em máquina comum, sem otimização especial: **150 mil registros do SIM (26 MB, 46 colunas)
em 82 segundos, com 51 MB de memória**. O consumo de memória cresce com o número de chaves
de duplicidade configuradas, não com o tamanho do arquivo — bases de milhões de linhas
processam sem problema.

---

## Proteção de dados

As bases contêm dados pessoais sensíveis. A ferramenta **não envia nada para a internet** —
todo o processamento é local. Ainda assim:

* mantenha `saida/` e `historico/` em pasta com acesso restrito ao setor;
* o `historico/` guarda apenas **hashes** das chaves (não guarda nome nem número da DO/DN),
  o suficiente para comparar envios sem replicar dado identificado;
* ao enviar a lista de inconsistências para uma unidade, envie somente as linhas daquela
  unidade (filtre a planilha antes);
* registre o tratamento no inventário de dados pessoais do órgão, conforme a LGPD.
