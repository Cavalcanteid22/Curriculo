# Capítulo de dissertação — Produto técnico

Este diretório gera o capítulo que descreve a construção do ELO-SIS, em
formato Word e segundo as normas da ABNT.

## Geração

```bash
cd ferramenta-pareamento/dissertacao
python3 diagrama.py      # produz a figura do fluxo
python3 montar.py        # produz CAPITULO_PRODUTO_TECNICO.docx
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
| `montar.py` | Montagem do documento |

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
