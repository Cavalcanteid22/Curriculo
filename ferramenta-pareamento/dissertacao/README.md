# Capítulos de dissertação

Este diretório gera dois capítulos em formato Word, segundo as normas da ABNT:

1. **`CAPITULO_PRODUTO_TECNICO.docx`** — construção do ELO-SIS
   (`montar.py`, partes `capitulo_parte1..5.py`).
2. **`CAPITULO_ROTINA_PAREAMENTO.docx`** — rotina de pareamento e
   qualificação aplicada a SICLOM × SINAN e SIM × SINAN
   (`montar2.py`, partes `cap2_parte1..5.py`).

## Geração

```bash
cd ferramenta-pareamento/dissertacao
python3 diagrama.py      # produz a figura do fluxo
python3 montar.py        # produz CAPITULO_PRODUTO_TECNICO.docx
python3 montar2.py       # produz CAPITULO_ROTINA_PAREAMENTO.docx
```

## Por que o capítulo é gerado por programa

As listagens de código reproduzidas no capítulo são **extraídas dos
arquivos-fonte no momento da geração**, e não transcritas. A consequência
prática é que qualquer alteração no programa se reflete no capítulo na próxima
geração, o que elimina a divergência — frequente em trabalhos que documentam
software — entre o que o texto afirma e o que o produto executa.

A extração usa a árvore sintática do Python (módulo `ast`), de modo que o
recorte acompanha a estrutura do código e não depende de números de linha, que
mudam a cada edição.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `gerar_capitulo.py` | Formatação ABNT e extração de código do fonte |
| `capitulo_parte1.py` | Caracterização do produto e decisões de arquitetura |
| `capitulo_parte2.py` | Leitura, qualificação, duplicidades e harmonização |
| `capitulo_parte3.py` | Perspectiva de identidade, pareamento e blocagem |
| `capitulo_parte4.py` | Produtos, interface e avaliação |
| `capitulo_parte5.py` | Achados metodológicos, limitações e considerações |
| `diagrama.py` | Figura do fluxo de processamento |
| `montar.py` | Montagem do primeiro capítulo |
| `cap2_parte1.py` | Premissas e requisitos da rotina de pareamento |
| `cap2_parte2.py` | Metodologia: padronização, chave direta, probabilístico, cortes |
| `cap2_parte3.py` | Qualidade, duplicidades e validação interna |
| `cap2_parte4.py` | Linguagem, estrutura do código e resultados das aplicações |
| `cap2_parte5.py` | Aplicabilidade, limitações e reprodutibilidade |
| `montar2.py` | Montagem do segundo capítulo |

## Ajustes prováveis antes da entrega

- **Numeração do capítulo.** O título está como nível 1 sem número. Ajuste
  para a numeração da sua dissertação (por exemplo, "6 PRODUTO TÉCNICO").
- **Numeração de figuras, tabelas e programas.** Reinicia em 1. Se o capítulo
  entrar num documento que já tem figuras, ajuste os contadores iniciais em
  `montar.py`.
- **Referências.** As obras citadas no capítulo precisam constar da lista de
  referências da dissertação. São elas: Aragão e Almeida Filho (2026), Cohen,
  Ravikumar e Fienberg (2003), Garcia, Miranda e Sousa (2022), Ghaffari
  Heshajin et al. (2024), Ghalavand et al. (2024), Organização Panamericana da
  Saúde (2016), Schmidt et al. (2020) e Winkler (1990).
- **Apêndice do código-fonte.** A seção final remete a um apêndice com o
  endereço do repositório, que precisa ser preenchido.

## Validação

O documento gerado passa na validação de esquema do formato OOXML. O template
padrão do `python-docx` grava `<w:zoom>` sem o atributo obrigatório
`w:percent`, o que viola o esquema; `gerar_capitulo.configurar()` corrige isso
antes de salvar.

## Procedência das listagens do segundo capítulo

As listagens do segundo capítulo são extraídas de
`ferramenta-pareamento/referencia/`, que é uma **implementação de referência**:
reproduz, de forma testada e verificável, os parâmetros documentados na aba de
metodologia das planilhas de pareamento entregues às áreas técnicas — os mesmos
pesos, pontos de corte, categorias e regras de aplicabilidade de campo. Não é
transcrição dos arquivos que executaram aquelas rodadas. Os casos de prova
(`teste_categorias.py`, `teste_qualidade.py`) fixam o comportamento esperado e
podem ser executados sem acesso a dado real algum.
