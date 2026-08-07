# Demonstração

Produtos gerados a partir das bases **fictícias** de `exemplos/bases` (400 registros),
só para você ver como cada arquivo fica antes de rodar com base real:

| Arquivo | O que é |
|---|---|
| `SIM_relatorio.html` | relatório completo do SIM, já com a comparação entre dois envios |
| `SIM_inconsistencias.xlsx` | planilha com as linhas inconsistentes pintadas por tipo |
| `SIM_instrumento_qualitativo.xlsx` | instrumento de avaliação com fórmulas, lista suspensa e formatação condicional |
| `painel_consolidado.html` | painel comparativo entre sistemas |

Nenhum dado é real: nomes, números de DO/DN e notificações são gerados aleatoriamente.
Para regerar: `python exemplos/gerar_exemplos.py --registros 400`.
