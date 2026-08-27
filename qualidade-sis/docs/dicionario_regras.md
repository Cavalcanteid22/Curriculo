# Referência dos arquivos de configuração

Cada sistema é descrito por um arquivo JSON em `configs/`. É ali que moram o dicionário de
dados, os domínios de resposta, os prazos e as críticas. **Alterar esses arquivos não exige
programação** — exige cuidado com a sintaxe do JSON (vírgulas, aspas, chaves).

Depois de editar, confira se o arquivo continua válido:

```bash
python executar.py listar
```

Se houver erro de sintaxe, a mensagem aponta a linha.

---

## Estrutura geral

```json
{
  "sistema": "SIM",
  "nome_completo": "Sistema de Informação sobre Mortalidade",
  "orgao": "Subcoordenadoria de Informação em Saúde — SMS Salvador",
  "csv": {"separador": null, "encoding": null},
  "chave_registro": ["NUMERODO"],
  "data_referencia": "DTOBITO",
  "campos_estratificacao": ["CODESTAB", "LOCOCOR"],
  "apelidos_colunas": {"NUM_DO": "NUMERODO"},
  "parametros": { },
  "chaves_duplicidade": [ ],
  "tempestividade": [ ],
  "campos": { },
  "regras_cruzadas": [ ],
  "pesos_atributos": { }
}
```

| Chave | O que faz |
|---|---|
| `csv.separador` / `csv.encoding` | `null` = detectar automaticamente; ou force `";"`, `"cp1252"` |
| `chave_registro` | campos que identificam o registro entre envios (base da resolutividade) |
| `data_referencia` | data do evento, usada na série mensal e na atualidade |
| `campos_estratificacao` | por onde estratificar (unidade, distrito, agravo, local) |
| `apelidos_colunas` | traduz o nome da coluna da exportação para o nome usado nas regras |
| `pesos_atributos` | sobrescreve o peso de um atributo no escore global |

### `parametros`

| Parâmetro | Efeito |
|---|---|
| `data_minima_plausivel` | data anterior a esta é marcada como implausível (padrão global) |
| `defasagem_aceitavel_dias` | usado no indicador de Atualidade |
| `campo_abrangencia` | campo usado no indicador de Abrangência |
| `estratos_esperados` | lista de valores que deveriam aparecer (ex.: códigos dos distritos) |

---

## Campos

```json
"PESO": {
  "rotulo": "Peso ao nascer (g)",
  "tipo": "inteiro",
  "obrigatorio": true,
  "essencial": true,
  "bloco": "Recém-nascido",
  "min": 200,
  "max": 7000,
  "ignorado": ["9999", "0"]
}
```

| Propriedade | Significado |
|---|---|
| `rotulo` | nome legível, usado em relatórios e planilhas |
| `tipo` | `texto`, `data`, `inteiro`, `decimal` ou `categorico` |
| `obrigatorio` | campo de preenchimento obrigatório na ficha |
| `essencial` | entra no cálculo de Completude e Suficiência (padrão: igual a `obrigatorio`) |
| `bloco` | agrupamento temático nos relatórios |
| `dominio` | valores válidos, como `{"1": "Sim", "2": "Não"}` — fora disso vira **código inválido** |
| `ignorado` | códigos que significam "ignorado/não informado" — viram **laranja** |
| `min` / `max` | faixa plausível para campos numéricos |
| `regex` | máscara obrigatória (ex.: `"^[0-9]{6,12}$"`) |
| `formato_descricao` | texto explicativo exibido quando a máscara falha |
| `validador` | validação pronta: `cpf`, `cns`, `cid10`, `ibge`, `cnes`, `cep` |
| `tamanho` + `so_digitos` | exige tamanho fixo (contando só dígitos, se `so_digitos`) |
| `formatos` | formatos de data aceitos (padrão cobre DD/MM/AAAA, AAAA-MM-DD, AAAAMMDD) |
| `data_minima` / `data_maxima` | limites plausíveis específicos daquela data |

Códigos textuais de ignorado (`IGNORADO`, `NÃO INFORMADO`, `NI`, `-`…) já são reconhecidos
automaticamente; para desligar, use `"ignorado_texto_padrao": false`.

---

## Chaves de duplicidade

```json
"chaves_duplicidade": [
  {"id": "DUP_NUMERODO", "nome": "Número da DO repetido", "campos": ["NUMERODO"]},
  {"id": "DUP_PROVAVEL", "nome": "Provável duplicidade",
   "campos": ["NOME", "DTOBITO", "DTNASC"]}
]
```

Os valores são normalizados (sem acento, sem espaço, sem pontuação; datas convertidas para
formato único) antes da comparação. Registros com **qualquer** campo da chave vazio não entram
naquela chave — evita que "todos os vazios" virem duplicata.

Cada chave configurada custa memória em bases grandes. Duas ou três chaves bastam.

---

## Tempestividade

```json
"tempestividade": [
  {"id": "DIGITACAO",
   "rotulo": "Oportunidade da digitação (óbito → cadastro no SIM)",
   "data_inicial": "DTOBITO", "data_final": "DTCADASTRO", "prazo_dias": 30}
]
```

Registros com intervalo maior que `prazo_dias` recebem **cinza** (fora do prazo);
intervalo negativo recebe **azul** (data incoerente). O relatório traz média, mediana, P25,
P75, P90 e a distribuição do atraso por faixa.

---

## Regras cruzadas — os sete tipos

Toda regra aceita: `id`, `descricao` (texto que aparece no relatório) e
`tipo_inconsistencia` (a cor: `em_branco`, `ignorado`, `codigo_invalido`, `data_invalida`,
`incoerencia`, `formato_invalido`, `fora_de_faixa`, `duplicidade`, `fora_do_prazo`).

### 1. `ordem_datas` — a segunda data não pode vir antes da primeira

```json
{"id": "SIM001", "tipo": "ordem_datas", "campos": ["DTNASC", "DTOBITO"],
 "descricao": "Data de nascimento deve ser anterior ou igual à data do óbito.",
 "tipo_inconsistencia": "data_invalida"}
```

Aceita ainda `min_dias` e `max_dias` para exigir um intervalo dentro de uma faixa
(ex.: última menstruação → nascimento entre 140 e 320 dias).

### 2. `condicional_obrigatorio` — se A, então B precisa estar preenchido

```json
{"id": "SNC010", "tipo": "condicional_obrigatorio",
 "se": {"campo": "IDANOMAL", "valores": ["1"]},
 "entao_preenchido": ["CODANOMAL"],
 "descricao": "Anomalia informada exige o código CID-10.",
 "tipo_inconsistencia": "em_branco"}
```

### 3. `condicional_proibido` — se A, então B não pode ter certos valores

```json
{"id": "SIM010", "tipo": "condicional_proibido",
 "se": {"campo": "SEXO", "valores": ["1"]},
 "entao_campo": "OBITOGRAV", "valores_proibidos": ["1"],
 "descricao": "Sexo masculino não pode ter óbito na gravidez.",
 "tipo_inconsistencia": "incoerencia"}
```

Com `"proibido_preenchido": true`, o campo não pode ter valor **algum**.

### 4. `condicional_valores` — se A, então B só pode ter certos valores

```json
{"tipo": "condicional_valores",
 "se": {"campo": "CONSULTAS", "valores": ["1"]},
 "entao_campo": "CONSPRENAT", "valores_esperados": ["0"]}
```

### 5. `faixa_condicional` — faixa numérica que só vale em certa condição

```json
{"tipo": "faixa_condicional",
 "se": {"campo": "GESTACAO", "valores": ["5", "6"]},
 "campo": "PESO", "min": 1500, "max": 6500}
```

### 6. `comparacao_numerica` — comparar dois campos numéricos

```json
{"tipo": "comparacao_numerica", "campo_a": "QTDPARTNOR", "campo_b": "QTDGESTANT",
 "operador": "<="}
```

Operadores: `<=`, `<`, `>=`, `>`, `==`, `!=`.

### 7. `coerencia_valores` — combinações proibidas explícitas

```json
{"tipo": "coerencia_valores",
 "combinacoes_proibidas": [{"OBITOGRAV": "1", "OBITOPUERP": "1"}]}
```

### A condição `se`

```json
"se": {"campo": "SEXO", "valores": ["1", "M"]}
"se": {"campo": "DT_ENCERRA", "preenchido": true}
"se": [{"campo": "SEXO", "valores": ["2"]}, {"campo": "IDADE", "valores": ["410", "411"]}]
```

Lista de condições = todas precisam ser verdadeiras. Aceita ainda
`valores_diferentes_de` e `"modo": "qualquer"` (basta uma).

---

## Criar a configuração de um sistema novo

1. Copie o JSON mais parecido (por exemplo `sinan.json` → `meu_sistema.json`).
2. Troque `sistema`, `nome_completo` e `chave_registro`.
3. Rode `python executar.py validar -s meu_sistema -b base.csv` e ajuste os nomes dos campos
   até o número de "reconhecidos" ficar alto.
4. Ajuste domínios e códigos de ignorado conforme o dicionário oficial do sistema.
5. Acrescente as críticas que o setor já faz manualmente hoje — cada uma vira uma regra.
6. Rode com `--limite 2000` para conferir se as críticas estão disparando como esperado antes
   de processar a base inteira.

---

## Desempenho e memória

* A leitura é em fluxo: o tamanho do arquivo não é limite.
* O consumo de memória vem das **chaves de duplicidade** e da comparação entre envios —
  aproximadamente 100 MB por milhão de registros por chave configurada.
* A planilha Excel é limitada a `--max-linhas-excel` linhas (padrão 200.000); o CSV de
  ocorrências nunca é truncado.
* Para bases muito grandes, uma execução mensal por sistema, fora do horário de pico, resolve.
