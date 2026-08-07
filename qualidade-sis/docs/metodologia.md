# Metodologia — como conduzir a avaliação da qualidade dos sistemas

Subcoordenadoria de Informação em Saúde — Secretaria Municipal da Saúde de Salvador

Este documento responde à pergunta "**como fazer esse trabalho**": como organizar a rotina,
como transformar uma lista de 40 atributos em algo mensurável, o que medir em cada um, com que
periodicidade, com quem pactuar e como saber se a avaliação está adiantando alguma coisa.

---

## 1. O problema, em uma frase

Avaliar a qualidade de um sistema de informação é responder a três perguntas diferentes,
que costumam ser tratadas como uma só:

| Pergunta | Objeto | Como se mede |
|---|---|---|
| O **dado** está bom? | a base de dados | indicadores calculados sobre o CSV |
| O **sistema** está bom? | o software e o acesso a ele | instrumento estruturado, com evidência |
| O **processo** está bom? | a rotina de notificação/digitação/correção | indicadores de fluxo e de resolutividade |

Os 40 atributos citados pelo setor se distribuem nessas três perguntas. Misturá-los num único
questionário produz avaliação subjetiva e não comparável entre envios. Separá-los permite que
a maior parte seja **calculada automaticamente** e que só o restante dependa de julgamento.

---

## 2. Os atributos organizados em três blocos

### Bloco A — mensuráveis diretamente na base (calculados pelo programa)

| Atributo | Indicador | Fórmula |
|---|---|---|
| Completude | completude essencial | campos essenciais preenchidos ÷ (registros × campos essenciais) |
| Suficiência | registros completos | registros com todos os essenciais preenchidos ÷ registros |
| Confiabilidade | não-ignorado | campos com valor informativo ÷ campos preenchidos |
| Validade | aderência ao domínio | valores dentro do domínio ÷ preenchidos em campos com domínio |
| Correção | ausência de erro detectável | campos sem erro (domínio, data, formato, faixa) ÷ preenchidos |
| Precisão | ausência de erro de faixa/formato | campos sem erro de faixa/formato ÷ preenchidos |
| Coerência | coerência interna | registros sem incoerência entre campos ÷ registros |
| Logicidade | ausência de impossibilidade lógica | registros sem incoerência nem data impossível ÷ registros |
| Singularidade | não duplicidade | registros não duplicados ÷ registros |
| Tempestividade | oportunidade | registros dentro do prazo pactuado ÷ registros com as duas datas |
| Atualidade | defasagem da base | dias entre a extração e o evento mais recente |
| Abrangência | cobertura | estratos esperados presentes ÷ estratos esperados |
| Quantidade / Volume | massa de dados | registros e registros × campos, comparados entre envios |
| Formato | conformidade de máscara | campos com máscara correta ÷ preenchidos |
| Veracidade | ausência de indício de erro material | registros sem data impossível, valor implausível ou incoerência ÷ registros |
| Inequivocidade | significado único | campos sem "ignorado" e sem código fora do domínio ÷ preenchidos |
| Compatibilidade | aderência ao layout nacional | campos do dicionário presentes na exportação ÷ campos do dicionário |
| Mensurabilidade | variáveis disponíveis para indicador | idem, restrito às variáveis que o setor usa |
| Valor informativo | densidade útil | campos preenchidos, válidos e não ignorados ÷ total de campos |
| Ordem | coerência da sequência | registros com cronologia coerente ÷ registros |

Todos aparecem no relatório com **numerador, denominador e fórmula** — qualquer número pode
ser refeito à mão a partir da planilha.

### Bloco B — avaliáveis por instrumento estruturado (planilha com fórmulas)

Clareza, Acessibilidade, Legibilidade, Pertinência, Utilidade, Compreensibilidade, Concisão,
Localizabilidade, Tempo de resposta, Segurança, Simplicidade, Credibilidade, Imparcialidade,
Importância, Significância, Conveniência, Interpretabilidade, Relevância.

Esses atributos dizem respeito ao **sistema**, não ao dado: nenhuma exportação revela se o
SINAN é fácil de usar ou se o acesso é liberado em tempo razoável. São avaliados em escala de
1 a 5, **sempre com evidência registrada**, na planilha gerada por
`python executar.py instrumento -s sinan`. A regra de ouro está embutida na planilha: nota
sem evidência deixa a linha vermelha.

Sugestões de evidência objetiva para os mais escorregadios:

* **Tempo de resposta** — cronometrar cinco operações padrão (abrir ficha, salvar notificação,
  emitir relatório, exportar base, fazer login), três vezes cada, e registrar a mediana.
* **Acessibilidade** — dias entre a solicitação de acesso e a liberação, nos últimos 6 pedidos.
* **Segurança** — existência de política de senha, trilha de auditoria, termo de sigilo assinado,
  perfil por função, e data da última revisão de perfis.
* **Simplicidade** — número de telas/passos para registrar uma notificação completa.
* **Utilidade** — quantos produtos do setor (boletins, painéis, notas técnicas) usaram o
  sistema no trimestre.
* **Credibilidade** — consulta estruturada a 8–10 técnicos que usam o dado: "você publicaria
  este número sem conferir na fonte?".

### Bloco C — atributos que só um padrão-ouro responde

**Acurácia/veracidade real** (o dado registrado corresponde ao fato) não se mede pela própria
base. Ela exige comparação com fonte externa. Proposta viável para a rotina do setor:

* amostra aleatória de **100 registros por sistema por semestre** (ou 30 por agravo prioritário);
* conferência contra prontuário, DO/DN original, laudo ou ficha de investigação;
* cálculo da **concordância por variável** (percentual de campos idênticos) e do índice kappa
  para as variáveis categóricas centrais;
* o resultado entra como evidência do atributo "Veracidade" no instrumento do Bloco B.

Com 100 registros a margem de erro fica em torno de ±10 pontos percentuais — suficiente para
detectar problema grave, insuficiente para monitorar variação fina. Se o setor precisar de
precisão maior num agravo específico, aumente a amostra apenas nele.

---

## 3. Rotina proposta

### A cada envio (mensal, ou na periodicidade em que a base é recebida)

1. Exportar a base acumulada de cada sistema em CSV, sempre com o **mesmo layout**.
2. Rodar `python executar.py analisar -s <sistema> -b <arquivo>`.
3. Abrir o relatório HTML e ler, nesta ordem: escore global → seção 8 (resolutividade) →
   seção 3 (campos) → seção 7 (estratificação) → seção 10 (providências sugeridas).
4. Filtrar a planilha por unidade notificadora e enviar a cada uma **apenas as suas linhas**,
   com prazo de retorno pactuado.
5. Arquivar os produtos na pasta do setor (a ferramenta já organiza por data).

### A cada trimestre

6. Aplicar o instrumento qualitativo (Bloco B) de cada sistema, em dupla, com validação da
   coordenação.
7. Rodar `python executar.py consolidar` e levar o painel para a reunião de monitoramento.
8. Revisar as metas do trimestre seguinte a partir dos atributos mais fracos.

### A cada semestre

9. Executar a verificação por amostra do Bloco C.
10. Revisar os arquivos de configuração: prazos pactuados mudaram? Entraram campos novos?
    Algum código de domínio foi alterado pelo Ministério?

---

## 4. Como ler os números

### Faixas de classificação

Adaptadas da literatura de avaliação de completude de sistemas de informação em saúde
(Romero & Cunha):

| Faixa | Critério | Conduta |
|---|---|---|
| Excelente | ≥ 95% | manter monitoramento |
| Bom | 90% a 94,9% | melhoria pontual |
| Regular | 80% a 89,9% | plano de ação com prazo |
| Ruim | 50% a 79,9% | prioridade do trimestre |
| Muito ruim | < 50% | intervenção imediata; suspender uso do campo em indicador |

### Escore global

Média dos indicadores do Bloco A **ponderada pelo peso de cada atributo** (o peso está em
`qualisis/tipos.py` e pode ser sobrescrito por sistema em `pesos_atributos`, na configuração).
Serve para acompanhar tendência, não para comparar sistemas de naturezas diferentes: um SIM com
89% e um SINAN com 89% não têm o mesmo significado, porque o conjunto de campos essenciais é
outro. **Compare cada sistema com ele mesmo ao longo do tempo** — é para isso que existe a
série histórica.

### Resolutividade — o indicador que mede o setor, não a base

Como a base é acumulativa, o mesmo registro reaparece a cada envio. A ferramenta acompanha
cada registro pela chave (número da DO/DN/notificação) e classifica cada inconsistência:

* **corrigida** — existia antes, o registro continua na base, o problema sumiu;
* **persistente** — existia antes e continua;
* **nova** — não existia no envio anterior;
* **sem registro** — existia antes e o registro sumiu da base (expurgo, exclusão ou mudança
  de chave) — **exige conferência**, não conta como correção.

```
Taxa de resolutividade = corrigidas ÷ (corrigidas + persistentes)
```

Interpretação prática:

* resolutividade alta e novas baixas → o processo está funcionando;
* resolutividade alta e novas altas → corrige-se bem, mas o erro continua entrando: atuar na
  origem (crítica no momento da digitação, treinamento, ajuste de ficha);
* resolutividade baixa → a devolutiva não está chegando a quem pode corrigir, ou não há prazo
  pactuado, ou falta perfil de acesso para corrigir;
* muitos registros "sem registro correspondente" → investigar o expurgo antes de qualquer
  comemoração.

---

## 5. Duplicidade: como a ferramenta procura

Três estratégias, configuráveis por sistema:

1. **chave oficial repetida** — mesmo número de DO, DN ou notificação;
2. **chave provável** — nome + data do evento + data de nascimento / nome da mãe / agravo;
3. **marcador do próprio sistema** (`NDUPLIC_N` no SINAN) ainda presente na base.

A chave provável encontra o que a chave oficial não pega (duas DO emitidas para o mesmo óbito).
Em compensação, produz **falso-positivo** — homônimos existem. Por isso o resultado é uma
**lista de trabalho para conferência**, nunca uma ordem de exclusão automática. Antes de excluir
qualquer registro, confirme no sistema de origem.

Para reduzir falso-positivo em bases muito grandes, prefira chaves com três ou mais campos e
inclua sempre uma data.

---

## 6. Tempestividade: o que medir em cada sistema

| Sistema | Intervalo | Prazo sugerido (ajuste ao pactuado) |
|---|---|---|
| SIM | óbito → cadastro no sistema | 30 dias |
| SIM | óbito → conclusão da investigação (materno/infantil) | 120 dias |
| SINASC | nascimento → cadastro no sistema | 30 dias |
| SINAN | 1º sintoma → notificação | 7 dias (imediata: 24 h, nos agravos de notificação imediata) |
| SINAN | notificação → digitação | 7 dias |
| SINAN | notificação → encerramento | 60 dias (varia por agravo) |
| SINAN Online | diagnóstico → notificação | 7 dias |
| SINAN Online | diagnóstico → encerramento | 270 dias (TB) |
| e-SUS SINAN | notificação → registro no sistema | 2 dias |

O relatório traz, para cada intervalo: percentual dentro do prazo, média, mediana, P25, P75,
P90, máximo e quantidade de intervalos negativos (que indicam erro de digitação de data, não
atraso). **Use a mediana, não a média** — a média é puxada por um punhado de registros muito
atrasados.

Os prazos ficam em `tempestividade`, no JSON de cada sistema. Se a pactuação municipal for
diferente, altere lá: o relatório inteiro se ajusta.

---

## 7. Fluxo de devolutiva (onde a avaliação vira melhoria)

```
exportação → análise → lista por unidade → prazo pactuado → nova exportação → resolutividade
```

Recomendações que fazem diferença na prática:

* **Devolva o registro, não a estatística.** "Sua unidade está com 62% de completude" não gera
  correção; a lista com o número da notificação e o campo em branco, sim.
* **Uma cor, uma ação.** Amarelo (branco) e laranja (ignorado) voltam para a unidade;
  vermelho (duplicidade) fica com o setor; azul (data) costuma ser digitação; roxo (código
  inválido) muitas vezes é problema de layout ou de versão do sistema.
* **Prazo curto e fixo** (por exemplo, 15 dias) e a mesma lista reenviada no próximo ciclo,
  destacando o que persistiu.
* **Ranking por unidade** publicado internamente — a seção 7 do relatório já entrega pronto.
* **Feche o ciclo**: o próximo relatório mostra à unidade quanto ela resolveu. Sem isso, a
  devolutiva vira burocracia.

---

## 8. Indicadores para monitorar o próprio setor

Além da qualidade das bases, vale acompanhar o trabalho da Subcoordenadoria:

| Indicador | Fórmula | Meta sugerida |
|---|---|---|
| Cobertura da avaliação | sistemas avaliados no mês ÷ sistemas sob gestão | 100% |
| Prazo da devolutiva | dias entre a extração e o envio da lista à unidade | ≤ 10 dias |
| Retorno das unidades | unidades que responderam ÷ unidades notificadas | ≥ 80% |
| Resolutividade | corrigidas ÷ (corrigidas + persistentes) | ≥ 70% |
| Redução do passivo | ocorrências persistentes deste envio ÷ do envio anterior | < 1 |
| Qualificação | profissionais capacitados ÷ digitadores ativos | ≥ 90% ao ano |

---

## 9. Limitações que devem ser declaradas no relatório

* A ferramenta detecta **inconsistência**, não **erro**: um dado pode estar coerente e mesmo
  assim ser falso. Só a verificação por amostra (Bloco C) aborda isso.
* Campos ausentes na exportação não são avaliados — a seção 11 do relatório lista quais são,
  e isso deve ser lido junto com o escore.
* Duplicidade provável é hipótese a conferir, não conclusão.
* O escore global é uma síntese com escolha de pesos; a leitura correta é indicador a indicador.
* Alterações de layout entre versões dos sistemas quebram a comparabilidade histórica —
  registre a data de cada mudança no histórico do setor.

---

## 10. Referências de apoio

* Ministério da Saúde. *Manual de Instruções para o preenchimento da Declaração de Óbito* e
  *da Declaração de Nascido Vivo*.
* Ministério da Saúde/SVS. *Guia de Vigilância em Saúde* (prazos de notificação, encerramento
  e critérios de confirmação por agravo).
* RIPSA. *Indicadores básicos para a saúde no Brasil: conceitos e aplicações* — atributos de
  qualidade de dados.
* Romero DE, Cunha CB. *Avaliação da qualidade das variáveis epidemiológicas e demográficas
  do Sistema de Informações sobre Nascidos Vivos* — origem das faixas de classificação.
* Lei nº 13.709/2018 (LGPD) — tratamento de dados pessoais sensíveis em saúde.
* Portaria de consolidação vigente sobre notificação compulsória — prazos oficiais.
