# -*- coding: utf-8 -*-
"""Linguagem, código, resultados e aplicabilidade."""

from cap2_parte1 import _codigo
from gerar_capitulo import citacao, lista, p, programa, tabela, titulo


def escrever(d, n):
    titulo(d, "Linguagem e código", 2, nova_pagina=True)

    titulo(d, "Linguagem de programação", 3)

    p(d, "Adotou-se a linguagem Python, na versão 3.11. A escolha considerou "
         "quatro fatores.")

    p(d, "O primeiro é a adequação ao domínio. Python dispõe de bibliotecas "
         "maduras para a manipulação de dados tabulares, para a leitura dos "
         "formatos em que os sistemas exportam suas bases e para a produção "
         "de planilhas formatadas, que é o produto final da rotina.")

    p(d, "O segundo é a disponibilidade de métricas de similaridade de "
         "cadeias de caracteres em implementação eficiente. A biblioteca "
         "rapidfuzz, empregada no cálculo da similaridade nominal, é escrita "
         "em C++ com interface em Python, o que torna viável o volume de "
         "comparações exigido pelo pareamento probabilístico.")

    p(d, "O terceiro é a legibilidade. Tratando-se de produto destinado a ser "
         "mantido pela equipe do serviço, o código foi escrito com "
         "identificadores em português e comentários que registram a "
         "justificativa das decisões, e não apenas a descrição das operações. "
         "Em rotinas de qualificação de bases, a razão de um ponto de corte "
         "costuma ser mais difícil de recuperar do que a sua implementação.")

    p(d, "O quarto é a gratuidade e a ausência de restrição de licença, "
         "condição relevante para adoção em serviço público.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Bibliotecas empregadas e respectiva finalidade",
        ["Biblioteca", "Finalidade"],
        [["pandas", "Leitura e manipulação das bases"],
         ["rapidfuzz", "Similaridade entre cadeias de caracteres"],
         ["openpyxl", "Geração das planilhas com formatação e fórmulas"],
         ["dbfread / simpledbf", "Leitura dos arquivos DBF exportados pelo SINAN"],
         ["datetime (biblioteca padrão)", "Conversão e comparação de datas"],
         ["unicodedata (biblioteca padrão)", "Remoção de acentuação na padronização"]],
        "Fonte: elaboração própria.", larguras=[5.5, 9.5])

    titulo(d, "Estrutura do código", 3)

    p(d, "A rotina organiza-se em dois módulos, correspondentes às duas "
         "funções do produto.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Módulos da implementação de referência",
        ["Módulo", "Responsabilidade", "Funções principais"],
        [["pareamento_siclom_sinan.py",
          "Padronização, similaridade, blocagem e categorização",
          "padronizar_nome, normalizar_numero_sinan, similaridade_nome, "
          "pontuar_data, escore_composto, candidatos, comparar, classificar"],
         ["qualidade_sinan.py",
          "Atributos de qualidade, regras e duplicidades",
          "medir_incompletude, classificar_incompletude, "
          "prioridade_da_pendencia, verificar_campos, verificar_regras, "
          "detectar_duplicidades"]],
        "Fonte: elaboração própria.", larguras=[4.2, 4.8, 6.0], corpo=8)

    p(d, "A separação obedece a um critério: cada módulo deve poder ser "
         "lido, testado e modificado isoladamente. A verificação de qualidade "
         "não depende do pareamento, e pode ser executada sobre uma base "
         "isolada; o pareamento depende da padronização, mas não da "
         "verificação de qualidade.")

    titulo(d, "Verificação do código", 3)

    p(d, "As funções de decisão foram submetidas a verificação com casos "
         "construídos para representar cada situação prevista. A verificação "
         "da classificação emprega nove casos, correspondentes às sete "
         "categorias e a duas variações do vínculo direto — com e sem zeros à "
         "esquerda no número declarado.")

    n["programa"] = programa(
        d, n["programa"], "Casos de verificação da classificação",
        '''CASOS = [
    # (descrição, usuário, categoria esperada)
    ("número declarado e confere",
     Usuario("u1", "MARIA JOSE DA SILVA", "ANA SILVA", date(1980, 5, 10), "100"),
     "1"),
    ("número declarado com zeros à esquerda",
     Usuario("u1b", "MARIA JOSE DA SILVA", "ANA SILVA", date(1980, 5, 10), "0000100"),
     "1"),
    ("número inexistente, mas nome e data conferem",
     Usuario("u2", "JOAO PEDRO SANTOS", "RITA SANTOS", date(1975, 3, 22), "999999"),
     "2"),
    ("sem número, nome e data conferem",
     Usuario("u3", "CARLA MENDES LIMA", "LUCIA LIMA", date(1990, 8, 1), ""),
     "3"),
    ("sem número, nome confere, data diverge",
     Usuario("u4a", "PAULO ROBERTO DIAS", "EDNA DIAS", date(1970, 1, 1), ""),
     "4A"),
    ("número existe mas é de outro paciente",
     Usuario("u4b", "FERNANDO ALVES COSTA", "MARTA COSTA", date(1995, 6, 30), "500"),
     "4B"),
    ("número inexistente, nome similar, data diverge",
     Usuario("u5", "TEREZA CRISTINA ROCHA", "IVONE ROCHA", date(1991, 9, 9), "888888"),
     "5"),
    ("número inexistente e nenhum nome parecido",
     Usuario("u6", "RICARDO NUNES BARROS", "SONIA BARROS", date(1982, 4, 4), "777777"),
     "6"),
    ("sem número e sem correspondência",
     Usuario("u7", "BEATRIZ GOMES PIRES", "CLARA PIRES", date(1993, 7, 19), ""),
     "7"),
]''',
        "referencia/teste_categorias.py", corpo=7)

    p(d, "As nove situações são classificadas corretamente. A verificação da "
         "qualidade, por sua vez, confere a escala de classificação, a soma "
         "do branco com o ignorado, o cálculo sobre a população aplicável, a "
         "derivação da prioridade, as regras de consistência e a "
         "classificação das duplicidades pelo intervalo.")

    # ------------------------------------------------------------------ #
    titulo(d, "Resultados das duas aplicações", 2, nova_pagina=True)

    titulo(d, "SICLOM × SINAN — UDM Comércio, outubro de 2026", 3)

    n["tabela"] = tabela(
        d, n["tabela"],
        "Resultado do pareamento entre SICLOM e SINAN",
        ["Cód.", "Categoria", "N", "%"],
        [["1", "Confirmado — vínculo direto", "190", "21,1"],
         ["2", "Número não localizado, nome e data conferem", "56", "6,2"],
         ["3", "Correspondência provável por nome e data", "121", "13,4"],
         ["4A", "Revisão manual — data não confere", "8", "0,9"],
         ["4B", "Revisão manual — número de outro paciente", "3", "0,3"],
         ["5", "Nome similar, data diverge ou ausente", "3", "0,3"],
         ["6", "Sem correspondência, número informado inválido", "137", "15,2"],
         ["7", "Sem correspondência e sem número", "382", "42,4"],
         ["", "TOTAL", "900", "100,0"]],
        "Fonte: elaboração própria.", larguras=[1.2, 8.3, 2.0, 2.0], corpo=8)

    p(d, "Três leituras merecem destaque.")

    p(d, "A primeira é que 367 usuários (40,8%) obtiveram correspondência "
         "identificável, dos quais 177 — as categorias 2 e 3 somadas — não "
         "teriam sido localizados sem o pareamento probabilístico. Esse é o "
         "ganho direto atribuível ao método sobre a simples conferência do "
         "número declarado.")

    p(d, "A segunda é que 511 cadastros (56,8%) não traziam número de "
         "notificação preenchido. O dado qualifica o problema: o vínculo "
         "entre os sistemas existe formalmente, mas não é operado na maior "
         "parte dos casos.")

    p(d, "A terceira é que 519 usuários (57,7%) ficaram sem correspondência, "
         "dos quais 199 haviam sido cadastrados antes de 2022 — ou seja, "
         "possivelmente notificados antes da janela temporal coberta pela "
         "base disponível. Conforme a segunda premissa, esses registros não "
         "são apresentados como subnotificação, mas encaminhados à busca "
         "ativa, priorizada pelos 70 usuários que tiveram dispensação recente "
         "de medicamento e permanecem sem notificação localizada.")

    p(d, "Quanto à qualidade, 4.197 das 4.213 notificações (99,6%) "
         "apresentaram ao menos uma pendência, das quais 687 (16,3%) de alta "
         "prioridade. No cadastro do SICLOM, 569 usuários (63,2%) "
         "apresentaram pendência, sendo 553 de alta prioridade.")

    titulo(d, "SIM × SINAN — janeiro a setembro de 2026", 3)

    p(d, "A segunda aplicação relacionou óbitos registrados no SIM com "
         "notificações do SINAN, em dezesseis agravos, totalizando 1.344 "
         "registros. A estrutura do produto difere da anterior: organiza-se "
         "por agravo, em uma aba para cada, de modo que cada área técnica "
         "receba apenas o que lhe compete.")

    p(d, "Cada aba organiza-se em quatro blocos de colunas, que correspondem "
         "a quatro momentos do fluxo de trabalho:")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Estrutura das abas do produto SIM × SINAN",
        ["Bloco", "Colunas", "Função"],
        [["Informações do SIM",
          "NUMERODO, NUMERODV, DTOBITO, NOME, NOMEMAE, DTNASC, LOCOCOR, "
          "CODESTAB, NOME_ESTAB, CAUSABAS, NOME_DOENÇA",
          "Identificação do óbito"],
         ["Pesquisa SUIS", "STATUS, NOTIFICAÇÃO SINAN, OBSERVAÇÃO_SUIS",
          "Resultado do pareamento"],
         ["Resposta da área técnica", "SITUAÇÃO, ENCAMINHAMENTO",
          "Campos reservados ao retorno"],
         ["Análise de qualidade e recomendações",
          "INCONSISTÊNCIAS ENCONTRADAS, EXPLICAÇÃO / FUNDAMENTAÇÃO TÉCNICA, "
          "SUGESTÕES DE CORREÇÃO E AÇÕES RECOMENDADAS, RESPONSÁVEL PELA AÇÃO, "
          "PRIORIDADE",
          "Achados e encaminhamento"]],
        "Fonte: elaboração própria.", larguras=[3.2, 6.8, 5.0], corpo=8)

    p(d, "A existência de bloco reservado à resposta da área técnica decorre "
         "da quinta premissa. O produto não é relatório a ser lido, mas "
         "instrumento a ser preenchido: a planilha retorna à SUIS com a "
         "situação apurada e o encaminhamento adotado, o que fecha o ciclo e "
         "permite medir, na rodada seguinte, o que foi efetivamente corrigido.")

    p(d, "O vocabulário do campo de resultado é controlado, e os seus valores "
         "correspondem a situações distintas de vigilância — entre as mais "
         "frequentes, óbito notificado sem campo de evolução preenchido, "
         "óbito no SINAN sem declaração de óbito localizada no SIM, "
         "encerramento como óbito por outras causas e possível homonímia a "
         "conferir.")

    p(d, "As inconsistências são assinaladas com indicação da origem — SIM, "
         "SINAN ou pareamento —, o que permite à área técnica dirigir a "
         "correção ao sistema correspondente. A distribuição de prioridade "
         "foi de 582 registros em prioridade alta, 439 em média e 66 em "
         "baixa.")
