# ELO-SIS

**Ferramenta de qualificação, harmonização e pareamento de bases dos sistemas
de informação em saúde — SIM, SINAN e SINASC.**

Produto técnico do projeto de intervenção *“O Desafio da Interoperabilidade em
Sistemas: proposta para linkage entre SIM, SINAN e SINASC”*, do Mestrado
Profissional em Saúde Coletiva com área de concentração em Informação e Saúde
Digital do Instituto de Saúde Coletiva da Universidade Federal da Bahia.

---

## O que a ferramenta faz

A partir das bases exportadas pelos sistemas, a ferramenta executa seis etapas
e entrega dois produtos.

| Etapa | O que faz |
|---|---|
| **1. Leitura** | Abre arquivos em DBF, CSV, Excel e PDF; identifica o sistema de origem pela assinatura de campos |
| **2. Qualificação** | Avalia completude, acurácia, consistência e oportunidade; classifica cada registro em verde, amarelo ou vermelho |
| **3. Duplicidades** | Distingue duplicata técnica, de conteúdo e provável |
| **4. Harmonização** | Padroniza as variáveis e torna comparáveis os campos que cada sistema registra de modo distinto |
| **5. Pareamento** | Estágio determinístico por chave composta, seguido de estágio probabilístico por Jaro-Winkler ponderado |
| **6. Análise** | Indicadores de desempenho, ganho de completude, estatística descritiva, indicadores epidemiológicos e projeções |

**Produtos entregues:**

- **Planilha** (`.xlsx`) com 28 abas: as bases nativas registro a registro com
  as linhas pintadas e colunas analíticas ao final, a qualificação por
  dimensão, as duplicidades, os pareamentos, os não pareados, os indicadores e
  as recomendações consolidadas.
- **Relatório analítico-descritivo** (`.docx`) em normas da ABNT, com
  metodologia, análise, cálculos estatísticos e epidemiológicos, gráficos,
  projeções, análises comparativas e orientações para as áreas técnicas.
- **Trilha de auditoria** (`.json`) com os resumos criptográficos dos arquivos
  processados e os parâmetros da execução.

---

## Proteção dos dados

**Nenhum dado sai da estação de trabalho.** Isso não é uma declaração de
intenção: a ferramenta opera em *modo cofre*, substituindo em tempo de execução
as primitivas de conexão do interpretador Python. Qualquer tentativa de conexão
externa — por qualquer componente do programa — falha imediatamente e fica
registrada na trilha de auditoria, que informa quantas tentativas foram
bloqueadas.

Demais salvaguardas:

- pseudonimização opcional dos identificadores diretos, por HMAC-SHA256 com sal
  local de permissão restrita, que nunca acompanha os produtos gerados;
- identificação de cada arquivo de entrada pelo resumo SHA-256, o que permite
  demonstrar em auditoria qual versão da base originou cada produto **sem
  guardar cópia dos dados**;
- nenhuma telemetria, nenhum envio de estatísticas de uso, nenhuma verificação
  de atualização pela rede.

Base legal: Lei nº 13.709/2018 (LGPD), art. 7º, III e art. 11, II, “b” —
execução de políticas públicas por órgão da administração pública, restrita à
finalidade declarada no projeto. Observam-se, ainda, as Resoluções CNS
nº 466/2012 e nº 510/2016.

---

## Instalação

Requer **Python 3.9 ou superior**.

**Windows** — dê dois cliques em `executar_windows.bat`. Na primeira execução,
as bibliotecas necessárias são instaladas automaticamente.

**Linux ou macOS**

```bash
./executar_linux_mac.sh
```

**Instalação manual**

```bash
pip install -r requirements.txt
python -m elosis
```

---

## Uso

### Interface gráfica (recomendada)

```bash
python -m elosis
```

O caminho principal tem três passos: escolher as bases, escolher onde salvar e
executar. Tudo o mais fica recolhido em *opções avançadas*, cujos valores padrão
atendem ao uso corrente.

> **Primeira vez?** Use o botão **“Gerar bases de exemplo”**. A ferramenta cria
> bases fictícias do SIM, do SINAN e do SINASC com defeitos deliberados —
> duplicidades, incompletude, códigos fora de domínio, datas impossíveis e erros
> de digitação — e um gabarito de pareamento. Assim é possível conhecer o
> comportamento da ferramenta antes de usá-la com bases reais, e verificar a
> sensibilidade e o valor preditivo positivo contra um resultado conhecido.

### Linha de comando

```bash
# Análise completa
python -m elosis analisar sim.dbf sinan.dbf sinasc.dbf -s resultados/

# Com aferição de desempenho contra amostra de referência
python -m elosis analisar *.dbf -s resultados/ --referencia amostra_revisada.csv

# Ajustando os limiares
python -m elosis analisar *.dbf --limiar 0.92 --limiar-revisao 0.87

# Base anual completa: abas restritas aos registros com pendência
python -m elosis analisar *.dbf -s resultados/ --apenas-pendencias

# Gerando bases fictícias para treinamento
python -m elosis gerar-exemplo -s bases_exemplo/ --formato dbf
```

`python -m elosis analisar --help` lista todas as opções.

---

## Arquivos grandes

A ferramenta foi construída para bases anuais completas. A leitura é feita por
blocos, o leitor DBF opera por fluxo e o pareamento usa blocagem, de modo que a
memória permanece em patamar compatível com estações de trabalho comuns.

Ordens de grandeza observadas em teste com 135 mil registros distribuídos em
três bases (61 mil no SINAN, 26 mil no SIM, 48 mil no SINASC), em máquina
modesta:

| Etapa | Tempo aproximado |
|---|---|
| Leitura e qualificação das três bases | menos de 1 minuto |
| Pareamento (três relacionamentos) | 3 a 5 minutos |
| Geração da planilha e do relatório | 3 a 6 minutos |

O maior custo está na escrita das abas das bases, proporcional ao número de
células. Para bases anuais completas, recomenda-se a opção **“incluir apenas
registros com pendência”** (`--apenas-pendencias` na linha de comando): as abas
passam a conter somente os registros amarelos e vermelhos, reduzindo o arquivo
a cerca de um quinto. Nada se perde para o trabalho de correção — os registros
verdes são, por definição, os que nada exigem —, e a aba assinala a restrição
no próprio subtítulo, mantendo as contagens referidas à base completa.

Se a estação dispuser de pouca memória, a opção `--limite N` lê apenas os
primeiros N registros de cada base, o que permite verificar a configuração
antes da execução completa.

---

## Como ler as cores

| Cor | Significado | O que fazer |
|---|---|---|
| 🟩 **Verde** | Sem inconsistências detectadas | Registro apto ao uso analítico e ao pareamento |
| 🟨 **Amarelo** | Provável inconsistência | Verificação manual antes do uso |
| 🟥 **Vermelho** | Inconsistência real | Correção na base nativa, a partir do documento-fonte |

A cor é atribuída pela **regra da gravidade máxima**: basta uma inconsistência
real para que a linha seja vermelha; na ausência desta, uma provável a torna
amarela.

A distinção entre real e provável não é de grau, mas de natureza. Uma data
inexistente no calendário é erro objetivo; uma similaridade elevada entre dois
nomes é indício que demanda confirmação humana.

---

## Decisões metodológicas

**Limiar de 0,90 com faixa de revisão em 0,85.** Um par é aceito quando o escore
Jaro-Winkler ponderado (0,4 para o nome; 0,3 para o nome da mãe; 0,3 para a data
de nascimento) atinge 0,90. Entre 0,85 e 0,90 — intervalo de sensibilidade de
±0,05 — o par vai para conferência humana. O procedimento é deliberadamente
conservador: em vigilância, o falso-positivo propaga-se silenciosamente aos
indicadores, enquanto o par em revisão permanece visível.

**Perspectiva de identidade no SINASC.** A Declaração de Nascido Vivo registra
duas pessoas: o recém-nascido e a mãe. Qual delas é o sujeito do pareamento
depende da pergunta: o recém-nascido na vigilância do óbito infantil
(SINASC × SIM), a mãe na investigação da transmissão vertical (SINASC × SINAN).
A ferramenta seleciona a perspectiva conforme o par de bases, admitindo fixação
manual. Sem essa distinção, o procedimento compara o nome de um recém-nascido
com o de um adulto e não encontra par algum — erro que se manifesta como
resultado vazio, e não como falha.

**Redistribuição de peso.** Quando uma variável principal falta em um dos
registros, seu peso é redistribuído entre as presentes, e não descontado.
Descontá-lo penalizaria o registro pela incompletude da base, e não pela
ausência de evidência de identidade.

**Blocagem.** O estágio probabilístico não compara todos com todos — duas bases
de cem mil registros exigiriam dez bilhões de comparações. As comparações são
restritas a subconjuntos definidos por chaves múltiplas (código fonético do
nome com o ano de nascimento, data de nascimento integral, código fonético do
nome da mãe). Basta a coincidência em uma das chaves.

**Completude bruta e completude útil.** A ferramenta reporta as duas em
separado. Um campo preenchido com código de ignorado consta como preenchido nas
estatísticas usuais, sem que a informação exista. A diferença entre as duas
medidas é a dimensão desse problema.

---

## Limitações

- **O pareamento não é interoperabilidade.** Opera sobre dados já produzidos,
  sem alterar os sistemas nem os padrões que os regem. Amplia a capacidade
  analítica sem resolver a fragmentação que o torna necessário.
- **A qualidade do linkage depende da qualidade das bases.** Registros com
  chaves ausentes ou múltiplos erros simultâneos permanecem não pareados,
  qualquer que seja o limiar.
- **Erros sistemáticos não são detectáveis.** Um campo consistentemente mal
  preenchido em toda a rede notificadora passa por todas as verificações.
- **A extração de PDF é aproximada.** PDF é formato de apresentação, não de
  intercâmbio: valores podem vir truncados ou deslocados de coluna. A ferramenta
  sinaliza as bases assim obtidas. Sempre que possível, solicite a exportação em
  CSV, DBF ou Excel na origem.
- **Os limiares requerem nova aferição** para outros agravos, períodos ou
  recortes territoriais.

---

## Estrutura do código

```
elosis/
├── seguranca.py        Modo cofre, pseudonimização e trilha de auditoria
├── dbf.py              Leitor DBF em Python puro (dBase III/IV, FoxPro)
├── leitura.py          Leitura unificada de CSV, DBF, Excel e PDF
├── normalizacao.py     Pré-processamento (Garcia, Miranda e Sousa, 2022)
├── similaridade.py     Jaro-Winkler, Levenshtein e código fonético
├── perfis.py           Perfis do SIM, SINAN e SINASC; domínios e obrigatórios
├── qualidade.py        Atributos de qualidade (Ghalavand et al., 2024)
├── duplicidades.py     Duplicata técnica, de conteúdo e provável
├── harmonizacao.py     Harmonização (Schmidt et al., 2020)
├── pareamento.py       Pareamento determinístico e probabilístico
├── indicadores.py      Desempenho, estatística e epidemiologia
├── graficos.py         Gráficos do relatório
├── planilha.py         Planilha de resultados
├── relatorio.py        Relatório analítico em normas da ABNT
├── pipeline.py         Orquestração do fluxo
├── dados_ficticios.py  Gerador de bases fictícias e gabarito
├── gui.py              Interface gráfica
└── cli.py              Interface de linha de comando
```

Sem dependência de rede. O leitor DBF e as métricas de similaridade foram
escritos em Python puro para que a ferramenta execute em estações
institucionais sem permissão de instalação de componentes adicionais.

---

## Referências principais

BOGAERT, P. et al. Identifying common enablers and barriers in European health
information systems. **Health Policy**, v. 125, n. 12, p. 1517-1526, 2021.

GARCIA, K. K. S.; MIRANDA, C. B. de; SOUSA, F. N. e F. de. Procedures for
health data linkage: applications in health surveillance. **Epidemiologia e
Serviços de Saúde**, v. 31, n. 3, e20211272, 2022.

GHALAVAND, H. et al. Common data quality elements for health information
systems: a systematic review. **BMC Medical Informatics and Decision Making**,
v. 24, n. 1, art. 243, 2024.

SCHMIDT, C. O. et al. Definitions, components and processes of data
harmonisation in healthcare: a scoping review. **BMC Medical Informatics and
Decision Making**, v. 20, n. 1, art. 222, 2020.

A lista completa consta do relatório gerado.
