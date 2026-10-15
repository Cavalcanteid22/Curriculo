# -*- coding: utf-8 -*-
"""Seção 3 (continuação): perspectiva de identidade e pareamento."""

from gerar_capitulo import (citacao, extrair_atribuicao, extrair_funcao,
                            extrair_trecho, figura, lista, p, programa,
                            tabela, titulo)


def escrever(d, n):
    # ------------------------------------------------------------------ #
    titulo(d, "A perspectiva de identidade no SINASC", 3, nova_pagina=True)

    p(d, "Esta seção descreve um achado que não constava do desenho inicial e "
         "que emergiu da implementação. Registra-se em seção própria por "
         "constituir, no entendimento desta pesquisa, contribuição "
         "metodológica ao relacionamento de bases envolvendo o SINASC.")

    p(d, "A Declaração de Nascido Vivo registra duas pessoas no mesmo "
         "documento: o recém-nascido e a mãe. Qual delas constitui o sujeito "
         "do pareamento não é propriedade do documento, mas da pergunta "
         "epidemiológica que se formula.")

    lista(d, [
        "Na vigilância do óbito infantil, o sujeito é o recém-nascido: o "
        "relacionamento entre SINASC e SIM busca a criança que nasceu e "
        "morreu, e as chaves pertinentes são o nome do recém-nascido e a sua "
        "data de nascimento.",
        "Na investigação da transmissão vertical e na vigilância do óbito "
        "materno, o sujeito é a mãe: o relacionamento entre SINASC e SINAN "
        "busca a gestante notificada, e as chaves pertinentes são o nome da "
        "mãe, a sua data de nascimento e o seu CPF.",
    ])

    p(d, "A consequência de ignorar essa distinção é severa e, o que agrava, "
         "silenciosa. Sob a perspectiva do recém-nascido, o relacionamento "
         "entre SINASC e SINAN compara o nome de uma criança com o nome de um "
         "adulto e não encontra par algum. O procedimento não falha: conclui "
         "normalmente, informa zero pares e não emite advertência. O erro "
         "manifesta-se como resultado vazio, e não como erro — razão pela qual "
         "é particularmente traiçoeiro na rotina de serviço, onde o resultado "
         "vazio tende a ser interpretado como ausência de sobreposição entre "
         "as populações.")

    p(d, "A magnitude do efeito foi mensurada durante a avaliação do produto. "
         "Sob a perspectiva incorreta, o relacionamento entre SINAN e SINASC "
         "recuperou 1 par verdadeiro de 112; sob a perspectiva correta, "
         "recuperou 57, além de encaminhar outros 47 à revisão manual. A "
         "diferença não decorre de ajuste de limiar ou de melhoria do "
         "algoritmo, mas da definição de quem é a pessoa procurada.")

    p(d, "A ferramenta implementa a perspectiva como parâmetro explícito, com "
         "seleção automática conforme o par de bases em relacionamento e "
         "possibilidade de fixação manual pelo usuário.")

    n["programa"] = programa(
        d, n["programa"],
        "Declaração das perspectivas de identidade",
        extrair_atribuicao("perfis", "PERSPECTIVAS"),
        "elosis/perfis.py", corpo=7)

    p(d, "Um detalhe da implementação merece registro por ter sido descoberto "
         "apenas em verificação. Sob a perspectiva materna, o campo de sexo "
         "da Declaração de Nascido Vivo refere-se ao recém-nascido, e não à "
         "mãe. Mantê-lo no mapeamento fazia o sexo da criança ser confrontado "
         "com o da paciente notificada no SINAN, produzindo divergência "
         "sistemática que remetia à revisão manual pares corretos. A "
         "perspectiva materna, por isso, suprime esse campo do mapeamento e "
         "fixa o valor que o próprio instrumento determina.")

    n["programa"] = programa(
        d, n["programa"],
        "Aplicação da perspectiva ao mapeamento de variáveis",
        extrair_funcao("perfis", "mapear_com_perspectiva"),
        "elosis/perfis.py")

    # ------------------------------------------------------------------ #
    titulo(d, "Pareamento determinístico", 3, nova_pagina=True)

    p(d, "O primeiro estágio do relacionamento aplica chaves compostas em "
         "ordem decrescente de especificidade. A ordem reproduz o efeito "
         "demonstrado por Garcia, Miranda e Sousa (2022), que verificaram, em "
         "bases simuladas, que o uso isolado da variável nome resultou em "
         "40.108 pares; o acréscimo da chave nome da mãe reduziu o resultado "
         "a 112 pares; e a inclusão da data de nascimento isolou apenas dois "
         "pares.")

    p(d, "Foram definidos cinco conjuntos de chaves, apresentados a seguir "
         "com a respectiva justificativa.")

    n["programa"] = programa(
        d, n["programa"],
        "Conjuntos de chaves do estágio determinístico",
        extrair_atribuicao("pareamento", "CONJUNTOS_DETERMINISTICOS"),
        "elosis/pareamento.py", corpo=7)

    p(d, "O quinto conjunto — nome da mãe, data de nascimento e sexo — merece "
         "explicação. Destina-se a registros de recém-nascidos ainda não "
         "nominados, situação frequente no SINASC e determinante para a "
         "vigilância do óbito infantil. Nesses casos, o nome da criança está "
         "ausente ou preenchido com convenção genérica, e a identificação "
         "disponível é a da mãe associada à data de nascimento.")

    p(d, "Duas decisões de implementação condicionam o comportamento do "
         "estágio.")

    p(d, "A primeira é que cada registro é pareado uma única vez: estabelecido "
         "o par por uma regra mais específica, o registro é retirado das "
         "rodadas seguintes. É essa exclusão progressiva que evita a explosão "
         "combinatória advertida pelos autores na presença de registros "
         "repetidos.")

    p(d, "A segunda é o tratamento da chave ambígua. Quando mais de um "
         "registro da base de destino compartilha a mesma chave, o par não é "
         "descartado nem aceito automaticamente: é encaminhado à revisão "
         "manual, com registro explícito do motivo. Descartá-lo perderia "
         "informação; aceitá-lo introduziria arbitrariedade, uma vez que a "
         "escolha entre candidatos equivalentes não tem fundamento nos dados.")

    n["programa"] = programa(
        d, n["programa"],
        "Estágio determinístico com exclusão progressiva",
        extrair_funcao("pareamento", "parear_deterministico"),
        "elosis/pareamento.py", corpo=7)

    p(d, "Note-se ainda a verificação de divergências em variáveis auxiliares. "
         "Um par estabelecido por coincidência de CPF, por exemplo, tem escore "
         "máximo; se, contudo, as datas de nascimento dos dois registros "
         "divergirem, há contradição que o escore não capta. A ferramenta "
         "encaminha esses casos à revisão manual e informa, na planilha, qual "
         "foi a divergência observada — informação sem a qual o técnico não "
         "saberia o que conferir.")

    # ------------------------------------------------------------------ #
    titulo(d, "Pareamento probabilístico", 3, nova_pagina=True)

    p(d, "O segundo estágio submete à abordagem probabilística os registros "
         "não pareados no primeiro. Adota-se a métrica de similitude "
         "Jaro-Winkler ponderada por campo, conforme definido na "
         "fundamentação teórica deste projeto.")

    p(d, "A escolha da métrica justifica-se por ser a mais robusta para "
         "cadeias nominais com erros de digitação comuns em vigilância em "
         "saúde (COHEN; RAVIKUMAR; FIENBERG, 2003) e superior à distância de "
         "Levenshtein para nomes com variação de grafia (GARCIA; MIRANDA; "
         "SOUSA, 2022). A métrica foi implementada em Python puro, sem "
         "recurso a biblioteca externa, e verificada contra os valores de "
         "referência da literatura.")

    n["programa"] = programa(
        d, n["programa"],
        "Implementação da similaridade de Jaro-Winkler",
        extrair_funcao("similaridade", "jaro_winkler"),
        "elosis/similaridade.py")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Verificação da implementação contra valores de referência",
        ["Par de cadeias", "Valor de referência", "Valor obtido"],
        [["MARTHA / MARHTA", "0,9611", "0,9611"],
         ["DIXON / DICKSONX", "0,8133", "0,8133"],
         ["MARIA / MARIA", "1,0000", "1,0000"]],
        "Fonte: elaboração própria. Valores de referência conforme Winkler "
        "(1990).",
        larguras=[6.0, 4.5, 4.5])

    p(d, "A ponderação por campo — 0,4 para o nome, 0,3 para o nome da mãe e "
         "0,3 para a data de nascimento — reflete a confiabilidade esperada de "
         "cada variável em contexto de vigilância municipal. Um par é "
         "considerado pareado quando o escore ponderado é igual ou superior a "
         "0,90; pares com escore entre 0,85 e 0,90 — intervalo correspondente "
         "à análise de sensibilidade de ±0,05 em torno do limiar — são "
         "encaminhados à verificação manual.")

    titulo(d, "A redistribuição de peso na ausência de variável", 4)

    p(d, "Uma decisão de implementação exigiu deliberação e merece registro. "
         "Quando uma variável principal falta em um dos registros, seu peso é "
         "redistribuído entre as variáveis presentes, e não simplesmente "
         "descontado.")

    p(d, "A alternativa — descontar o peso — penalizaria o registro pela "
         "incompletude da base, e não pela ausência de evidência de "
         "identidade. A distinção importa porque a incompletude é justamente "
         "um dos problemas que o relacionamento se propõe a mitigar: um "
         "registro sem nome da mãe, mas com nome e data de nascimento "
         "coincidentes, apresenta evidência de identidade tão forte quanto "
         "outro em que as três variáveis coincidem — o que o distingue é a "
         "quantidade de evidência disponível, não a sua qualidade.")

    p(d, "Estabeleceu-se, porém, um piso: exige-se peso total mínimo de 0,40 "
         "para que o escore seja calculado. Abaixo desse valor, a informação "
         "disponível é insuficiente para afirmar identidade, e o par é "
         "descartado em lugar de receber escore artificialmente elevado pela "
         "redistribuição.")

    n["programa"] = programa(
        d, n["programa"],
        "Cálculo do escore ponderado com redistribuição de peso",
        extrair_funcao("pareamento", "calcular_escore"),
        "elosis/pareamento.py", corpo=7)

    p(d, "As variáveis auxiliares — sexo, CPF, CNS e município de residência "
         "— não compõem o escore principal, mas o ajustam. A concordância "
         "bonifica; a divergência penaliza. A penalização por divergência de "
         "sexo é deliberadamente severa, correspondendo ao triplo do peso de "
         "bonificação, por tratar-se de variável de alta confiabilidade cuja "
         "divergência raramente decorre de erro de digitação.")

    # ------------------------------------------------------------------ #
    titulo(d, "Blocagem", 3, nova_pagina=True)

    p(d, "A comparação de todos os registros de uma base com todos os da "
         "outra é computacionalmente inviável em bases municipais. Duas bases "
         "de cem mil registros exigiriam dez bilhões de comparações — número "
         "que, à taxa observada nesta implementação, corresponderia a mais de "
         "trezentas horas de processamento.")

    p(d, "Garcia, Miranda e Sousa (2022) registram as limitações de memória do "
         "software entre as restrições da técnica. A blocagem é a resposta "
         "corrente a essa restrição: restringe as comparações a subconjuntos "
         "plausíveis, definidos por chaves que dois registros da mesma pessoa "
         "provavelmente compartilham.")

    p(d, "Adotaram-se cinco chaves de blocagem simultâneas, bastando a "
         "coincidência em uma delas para que dois registros sejam comparados. "
         "A multiplicidade é deliberada: uma chave isolada que contenha erro "
         "de digitação excluiria o par verdadeiro da comparação, ao passo que "
         "a coincidência em qualquer uma das cinco o preserva.")

    n["programa"] = programa(
        d, n["programa"],
        "Construção das chaves de blocagem",
        extrair_funcao("pareamento", "_construir_blocos"),
        "elosis/pareamento.py")

    p(d, "Duas das chaves empregam código fonético. Sua adoção segue "
         "sugestão expressa de Garcia, Miranda e Sousa (2022), que indicam o "
         "emprego de códigos fonéticos combinados a outras variáveis como "
         "possibilidade de aumento da sensibilidade do método. O código "
         "fonético foi adaptado ao português brasileiro, de modo a reconhecer "
         "como equivalentes grafias como SOUZA e SOUSA, LUIZ e LUIS, "
         "GONCALVES e GONSALVES.")

    n["programa"] = programa(
        d, n["programa"],
        "Código fonético adaptado ao português brasileiro",
        extrair_funcao("similaridade", "codigo_fonetico"),
        "elosis/similaridade.py")

    p(d, "Implementou-se ainda uma guarda contra blocos degenerados. Quando "
         "uma chave perde poder de seleção — o que ocorre, por exemplo, "
         "quando milhares de registros compartilham uma data de nascimento "
         "convencional — o bloco correspondente cresce a ponto de anular o "
         "ganho da blocagem. Blocos que excedam duzentas e cinquenta mil "
         "comparações são, por isso, ignorados; os pares neles contidos "
         "permanecem elegíveis pelas demais chaves, que são mais seletivas.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Efeito da blocagem no relacionamento entre SINAN e SINASC",
        ["Medida", "Valor"],
        [["Registros remanescentes na base A", "57.388"],
         ["Registros remanescentes na base B", "43.908"],
         ["Comparações sem blocagem", "2.519.729.904"],
         ["Blocos comuns formados", "39.418"],
         ["Comparações efetivamente realizadas", "841.307"],
         ["Redução", "99,97%"]],
        "Fonte: elaboração própria, a partir da execução sobre as bases "
        "fictícias de avaliação.",
        larguras=[9.0, 6.0])
