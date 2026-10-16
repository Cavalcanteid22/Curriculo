# -*- coding: utf-8 -*-
"""Metodologia: pareamento."""

from cap2_parte1 import _codigo, _constantes
from gerar_capitulo import (citacao, lista, p, programa, tabela, titulo)


def escrever(d, n):
    titulo(d, "Metodologia", 2, nova_pagina=True)

    titulo(d, "Fontes e recorte", 3)

    n["tabela"] = tabela(
        d, n["tabela"],
        "Fontes utilizadas nas duas aplicações",
        ["Aplicação", "Base A", "Base B", "Recorte"],
        [["SICLOM × SINAN",
          "SICLOM — relatórios de usuários cadastrados e formulários de "
          "dispensação da UDM Comércio (900 usuários)",
          "SINAN/HEPANET — 4.213 notificações de hepatites virais",
          "Emissão de 05/10/2026; notificações de 03/01/2022 a 01/10/2026"],
         ["SIM × SINAN",
          "SIM — óbitos de residentes com causa básica relacionada a agravo "
          "de notificação",
          "SINAN — notificações dos agravos correspondentes",
          "Janeiro a setembro de 2026; dezesseis agravos"]],
        "Fonte: elaboração própria, a partir dos produtos entregues à SUIS.",
        larguras=[2.8, 4.6, 4.3, 3.8], corpo=8)

    titulo(d, "Padronização", 3)

    p(d, "A comparação de campos nominais exige padronização prévia. Adotam-se "
         "a conversão para caixa alta, a remoção de acentos e de caracteres "
         "não alfabéticos e a eliminação de espaços duplicados. As datas são "
         "convertidas para tipo de data, o que permite a comparação "
         "cronológica e o cálculo de intervalos.")

    p(d, "Os valores originais são preservados nas saídas. A padronização "
         "existe para a comparação, e não para substituir o dado registrado: "
         "a área técnica precisa ver o valor tal como consta no sistema para "
         "poder conferi-lo no documento-fonte.")

    n["programa"] = programa(
        d, n["programa"], "Padronização de campos nominais",
        _codigo("pareamento_siclom_sinan", "padronizar_nome"),
        "referencia/pareamento_siclom_sinan.py")

    p(d, "O número da notificação recebe tratamento específico. O SICLOM o "
         "registra como texto digitado pelo operador; o SINAN o armazena com "
         "preenchimento de zeros à esquerda. Sem a normalização, vínculos "
         "declarados corretamente deixariam de ser reconhecidos — e seriam "
         "contabilizados como divergência.")

    n["programa"] = programa(
        d, n["programa"], "Normalização do número da notificação",
        _codigo("pareamento_siclom_sinan", "normalizar_numero_sinan"),
        "referencia/pareamento_siclom_sinan.py")

    titulo(d, "Pareamento por chave direta", 3)

    p(d, "O primeiro estágio emprega o número da notificação declarado no "
         "SICLOM. Conforme a premissa já enunciada, o vínculo só é confirmado "
         "quando o nome do paciente constante da notificação apresenta "
         "similaridade igual ou superior a 80, ou quando a data de nascimento "
         "coincide exatamente.")

    p(d, "Quando o número existe na base mas identifica outro paciente, o "
         "caso é classificado em categoria própria e encaminhado à correção "
         "do cadastro. Quando o número não existe na base, o registro segue "
         "para o estágio seguinte.")

    titulo(d, "Pareamento probabilístico", 3)

    p(d, "O segundo estágio aplica-se aos registros que o primeiro não "
         "resolveu — nas duas aplicações, a maioria: no SICLOM, 511 dos 900 "
         "cadastros não traziam número de notificação preenchido.")

    p(d, "A similaridade entre cadeias nominais é calculada pela razão de "
         "tokens ordenados (token_sort_ratio), implementada na biblioteca "
         "rapidfuzz. A escolha da métrica responde a uma característica dos "
         "cadastros: a inversão entre prenome e sobrenome é frequente, e uma "
         "métrica sensível à ordem dos componentes a trataria como "
         "divergência. A razão de tokens ordenados compara os componentes do "
         "nome após ordená-los, o que a torna insensível à inversão.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Comportamento da métrica de similaridade adotada",
        ["Par comparado", "Similaridade", "Situação reconhecida"],
        [["ANA LIMA / LIMA ANA", "100,0", "Inversão de ordem"],
         ["MARIA JOSE DA SILVA / MARIA JOSE SILVA", "91,4", "Supressão de preposição"],
         ["JOAO P SANTOS / JOAO PEDRO SANTOS", "86,7", "Abreviação do nome do meio"],
         ["SOUZA / SOUSA", "80,0", "Variação fonética de grafia"]],
        "Fonte: elaboração própria, valores obtidos com rapidfuzz 3.14.",
        larguras=[6.6, 3.0, 5.4])

    p(d, "O escore composto pondera cinco componentes. A decomposição do nome "
         "em primeiro nome e último sobrenome, além do nome completo, "
         "justifica-se porque eles erram de modo distinto: o primeiro nome "
         "raramente é abreviado, ao passo que o sobrenome final é o que mais "
         "sofre supressão nos cadastros.")

    n["programa"] = programa(
        d, n["programa"], "Pesos do escore composto",
        _constantes("pareamento_siclom_sinan", "# Pesos do escore composto.",
                    "\n# Blocagem:"),
        "referencia/pareamento_siclom_sinan.py")

    p(d, "A redistribuição do peso na ausência de variável merece "
         "justificativa. Quando o nome da mãe ou a data de nascimento não "
         "constam de um dos registros, o peso correspondente é redistribuído "
         "entre as variáveis presentes, e não descontado. Descontá-lo "
         "penalizaria o par pela incompletude do cadastro, e não pela falta "
         "de evidência de identidade — distinção que importa porque a "
         "incompletude é justamente um dos problemas que o procedimento se "
         "propõe a diagnosticar.")

    n["programa"] = programa(
        d, n["programa"], "Escore composto com redistribuição de peso",
        _codigo("pareamento_siclom_sinan", "escore_composto"),
        "referencia/pareamento_siclom_sinan.py")

    p(d, "A data de nascimento recebe pontuação graduada, e não binária. A "
         "inversão entre dia e mês é o erro de transcrição mais frequente "
         "nesse campo e recebe pontuação intermediária, em lugar de ser "
         "tratada como divergência total.")

    n["programa"] = programa(
        d, n["programa"], "Pontuação da data de nascimento",
        _codigo("pareamento_siclom_sinan", "pontuar_data"),
        "referencia/pareamento_siclom_sinan.py")

    titulo(d, "Blocagem", 3)

    p(d, "A comparação de todos os cadastros com todas as notificações seria "
         "computacionalmente onerosa e, sobretudo, desnecessária: a imensa "
         "maioria dos pares não guarda qualquer semelhança. Na aplicação de "
         "outubro de 2026, o cruzamento integral exigiria 3.791.700 "
         "comparações.")

    p(d, "A blocagem restringe a avaliação aos pares plausíveis, por meio de "
         "duas portas de entrada das quais basta uma: similaridade do "
         "primeiro nome igual ou superior a 80, ou data de nascimento "
         "idêntica com similaridade de nome igual ou superior a 60. A segunda "
         "condição recupera casos em que o prenome foi registrado de forma "
         "muito distinta nos dois sistemas.")

    n["programa"] = programa(
        d, n["programa"], "Blocagem por primeiro nome ou data de nascimento",
        _codigo("pareamento_siclom_sinan", "candidatos"),
        "referencia/pareamento_siclom_sinan.py")

    titulo(d, "Pontos de corte e categorização", 3)

    p(d, "A decisão sobre cada par obedece a pontos de corte explícitos. A "
         "correspondência é aceita quando a data de nascimento coincide "
         "exatamente e a similaridade do nome é igual ou superior a 88. O "
         "encaminhamento à revisão manual ocorre quando a similaridade do "
         "nome é igual ou superior a 90, ou quando o escore composto é igual "
         "ou superior a 80 com similaridade de nome não inferior a 80, sem "
         "coincidência exata da data.")

    p(d, "O resultado é expresso em sete categorias, apresentadas no quadro "
         "seguinte. A estrutura não é hierarquia de qualidade, mas de "
         "encaminhamento: cada categoria corresponde a uma providência "
         "distinta.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Categorias do resultado do pareamento e respectivo encaminhamento",
        ["Cód.", "Categoria", "Encaminhamento"],
        [["1", "Confirmado — vínculo direto pelo número da notificação",
          "Nenhum"],
         ["2", "Número informado não localizado, mas nome e data conferem",
          "Corrigir o número no cadastro"],
         ["3", "Correspondência provável por nome e data, sem número informado",
          "Registrar o número no cadastro"],
         ["4A", "Nome localizado, data de nascimento não confere",
          "Revisão manual"],
         ["4B", "Número localizado, mas pertencente a outro paciente",
          "Revisão manual e correção"],
         ["5", "Número não localizado; nome similar, data diverge ou ausente",
          "Revisão manual"],
         ["6", "Número não localizado e sem correspondência por nome",
          "Busca ativa"],
         ["7", "Sem correspondência e sem número informado",
          "Busca ativa — possível subnotificação"]],
        "Fonte: elaboração própria.",
        larguras=[1.2, 8.3, 5.5], corpo=8)

    p(d, "A implementação da classificação reproduz a hierarquia de "
         "evidência: examina-se primeiro o vínculo declarado, depois a "
         "correspondência por nome e data, por fim a ausência de "
         "correspondência.")

    n["programa"] = programa(
        d, n["programa"], "Classificação do registro em uma das sete categorias",
        _codigo("pareamento_siclom_sinan", "classificar"),
        "referencia/pareamento_siclom_sinan.py", corpo=7)

    titulo(d, "Confirmação pelo nome da mãe", 3)

    p(d, "O nome da mãe não participa da decisão sobre o par: participa da "
         "sua qualificação. Cada correspondência estabelecida recebe uma "
         "classificação adicional — confere, quando a similaridade é igual ou "
         "superior a 85; parcial, entre 70 e 84; não confere, abaixo de 70; e "
         "sem dado, quando ausente em um dos registros.")

    p(d, "A separação entre decidir e qualificar é deliberada. O nome da mãe "
         "é campo de completude irregular nos dois sistemas; condicionar a "
         "decisão a ele reduziria a sensibilidade do procedimento. Empregá-lo "
         "como confirmação independente permite medir a confiabilidade do "
         "conjunto de pares estabelecidos — e foi o que permitiu afirmar, na "
         "aplicação de outubro de 2026, que o nome da mãe confere em 90,2% "
         "das correspondências.")
