# Guia rápido — do export do sistema à devolutiva à unidade

Roteiro operacional. Se você só quer usar a ferramenta, este é o único documento necessário.

---

## Passo 1 — Exportar a base em CSV

| Sistema | Caminho usual da exportação | Cuidados |
|---|---|---|
| SIM / SINASC | Tabwin/TabNet a partir do arquivo DBF, ou exportação do sistema local | exporte **todos** os campos, não só os do relatório |
| SINAN NET | Exportação → "Exportar para arquivo texto/CSV" | mantenha o mesmo conjunto de campos entre um envio e outro |
| SINAN Online / e-SUS SINAN | relatório/exportação da própria plataforma web | prefira CSV a XLSX |

Regras que evitam retrabalho:

* Use **sempre o mesmo layout** — a comparação entre envios depende disso.
* Não abra o CSV no Excel antes de analisar: o Excel altera datas e corta zeros à esquerda
  (número de DO, CNES, CEP). Se precisar conferir, abra uma **cópia**.
* Se a exportação sair em `.dbf`, converta antes (Tabwin: *Arquivo → Exportar → CSV*).
* Nome do arquivo com data ajuda: `SIM_2026-07.csv`.

## Passo 2 — Conferir o layout (só na primeira vez)

```bash
python executar.py validar -s sim -b C:\bases\SIM_2026-07.csv
```

Se aparecerem campos "ausentes" que na verdade existem com outro nome, abra
`configs/sim.json` e acrescente em `apelidos_colunas`:

```json
"apelidos_colunas": {
  "DATA_DO_OBITO": "DTOBITO",
  "NUM_DO": "NUMERODO"
}
```

## Passo 3 — Analisar

```bash
python executar.py analisar -s sim -b C:\bases\SIM_2026-07.csv --data-extracao 31/07/2026
```

Leva de segundos a poucos minutos, conforme o tamanho. O progresso aparece na tela a cada
200 mil registros.

## Passo 4 — Ler o relatório (10 minutos)

Abra `SIM_relatorio.html` e leia nesta ordem:

1. **Escore global** (topo) — a tendência importa mais que o valor absoluto.
2. **Seção 8 — resolutividade** — o que foi corrigido desde o envio anterior. Se estiver
   abaixo de 50%, o problema é o fluxo de devolutiva, não a base.
3. **Seção 3 — campos com mais inconsistências** — é a lista do que cobrar.
4. **Seção 7 — estratificação** — quais unidades/distritos concentram o problema.
5. **Seção 10 — providências sugeridas** — rascunho pronto do plano de ação.

## Passo 5 — Trabalhar a planilha

Abra `SIM_inconsistencias.xlsx`, aba **Inconsistências**:

* a coluna `_TIPOS` diz o que há de errado na linha; `_DETALHE` explica campo a campo;
* use o **filtro** da coluna `_TIPOS` para separar por tipo de problema;
* a célula colorida é exatamente o campo com problema;
* `_GRAVIDADE` ordena do mais grave para o menos grave — comece por baixo dessa ordenação;
* para mandar à unidade: filtre pela coluna da unidade notificadora (CNES) e copie para uma
  planilha nova. **Envie só as linhas da unidade.**

O que fazer com cada cor:

| Cor | Quem resolve | Ação |
|---|---|---|
| Vermelho — duplicidade | setor | conferir no sistema de origem e excluir/vincular |
| Amarelo — em branco | unidade notificadora | completar a ficha e redigitar |
| Laranja — ignorado | unidade notificadora | buscar a informação; "ignorado" é último recurso |
| Roxo — código inválido | setor + digitação | conferir tabela de domínio e versão do sistema |
| Azul — data | digitação | corrigir a data no sistema |
| Verde-água — incoerência | unidade + setor | conferir documento-fonte |
| Rosa — formato | digitação | corrigir CNS/CPF/CEP |
| Verde — fora de faixa | unidade | conferir peso/idade/Apgar no prontuário |
| Cinza — fora do prazo | fluxo | atuar no processo, não no registro |

## Passo 6 — Registrar e repetir

No próximo envio, rode de novo. O relatório passa a mostrar automaticamente a comparação com
este. A cada trimestre:

```bash
python executar.py instrumento -s sim      # avaliação qualitativa do sistema
python executar.py consolidar              # painel comparativo entre os sistemas
```

---

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| "Configuração não encontrada" | sigla errada | `python executar.py listar` mostra as válidas |
| Acentos estranhos no relatório | codificação incomum | force em `configs/<sistema>.json`: `"csv": {"encoding": "cp1252"}` |
| Tudo vira uma coluna só | separador não detectado | force: `"csv": {"separador": ";"}` |
| Muitos campos "ausentes" | exportação com nomes diferentes | cadastre em `apelidos_colunas` |
| Tudo aparece como fora do prazo | data de extração errada | use `--data-extracao` |
| Planilha muito pesada | base grande | `--max-linhas-excel 50000` e use o CSV de ocorrências para o volume total |
| Comparação não aparece | é a primeira execução, ou a chave do registro está vazia | confira `chave_registro` na configuração |
| "MemoryError" | base muito grande e muitas chaves de duplicidade | reduza `chaves_duplicidade` para as duas mais importantes |

## Onde ficam as coisas

```
qualidade-sis/
├── executar.py              ← o programa
├── configs/                 ← dicionário e regras de cada sistema (editável)
├── saida/<sistema>/<data>/  ← produtos de cada execução
├── historico/<sistema>/     ← assinatura dos envios (para comparar) — apenas hashes
├── exemplos/                ← bases fictícias para treinar
└── docs/                    ← esta documentação
```
