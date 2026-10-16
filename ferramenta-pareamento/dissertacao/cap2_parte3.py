# -*- coding: utf-8 -*-
"""Metodologia: qualidade, duplicidades e validação."""

from cap2_parte1 import _codigo, _constantes
from gerar_capitulo import citacao, lista, p, programa, tabela, titulo


def escrever(d, n):
    titulo(d, "Verificação dos atributos de qualidade", 3, nova_pagina=True)

    p(d, "A verificação de qualidade não é acessório do pareamento: é "
         "condição da sua eficácia e, ao mesmo tempo, produto autônomo. "
         "Condição, porque a similaridade depende da qualidade dos campos "
         "comparados; produto autônomo, porque as pendências identificadas "
         "têm valor para a área técnica independentemente de o registro ter "
         "ou não encontrado par.")

    titulo(d, "Classificação dos campos pelo dicionário de dados", 4)

    p(d, "Conforme a terceira premissa, os campos são classificados segundo o "
         "Dicionário de Dados do sistema de origem. Para o SINAN, adotou-se o "
         "Dicionário de Dados do SINAN NET, versão 5.0, referente às "
         "hepatites virais, que distingue:")

    lista(d, [
        "campo obrigatório — aquele cuja ausência impossibilita a inclusão da "
        "notificação ou da investigação no sistema;",
        "campo essencial — aquele necessário à investigação do caso ou ao "
        "cálculo de indicadores, ainda que o sistema admita a sua ausência;",
        "regras de consistência — relações entre campos que o instrumento "
        "determina, como a precedência da data dos primeiros sintomas sobre a "
        "data de notificação.",
    ])

    p(d, "Para o SICLOM, inexistindo dicionário público, adotou-se critério "
         "operacional explicitado no produto: consideram-se de alta "
         "prioridade o CPF, o nome da mãe, a data de nascimento, o telefone, "
         "o número da notificação e as divergências entre sistemas; os demais "
         "campos recebem prioridade média. A explicitação do critério, nesse "
         "caso, é o que preserva a defensabilidade do resultado, uma vez que "
         "ele não deriva de norma.")

    titulo(d, "Medição da incompletude", 4)

    p(d, "A incompletude é calculada como a razão entre a soma dos registros "
         "em branco e dos preenchidos com código de ignorado e a população "
         "aplicável ao campo.")

    p(d, "A soma do branco com o ignorado é decisão metodológica relevante. "
         "Ambos representam ausência de informação, mas apenas o primeiro é "
         "contabilizado pelas medidas usuais de completude. Um campo "
         "preenchido com o código de ignorado consta como preenchido nas "
         "estatísticas do sistema, e a base aparenta completude satisfatória, "
         "sem que a informação exista. Na aplicação de outubro de 2026, o "
         "campo de antecedentes epidemiológicos apresentou 93,99% de "
         "incompletude, quase integralmente por código de ignorado — valor "
         "que uma contagem restrita ao campo em branco não teria revelado.")

    n["programa"] = programa(
        d, n["programa"], "Medição da incompletude",
        _codigo("qualidade_sinan", "medir_incompletude"),
        "referencia/qualidade_sinan.py")

    titulo(d, "A população aplicável", 4)

    p(d, "Vários campos do instrumento só são habilitados sob condição. A "
         "classificação etiológica, por exemplo, aplica-se apenas aos casos "
         "confirmados; a forma clínica, apenas a determinadas etiologias. "
         "Medir a incompletude desses campos sobre a base inteira produziria "
         "número sem significado, por computar como ausência o campo que "
         "sequer deveria estar preenchido.")

    p(d, "A rotina calcula, por isso, a população aplicável a cada campo, "
         "declarando no produto a regra empregada. O efeito não é "
         "desprezível: em verificação controlada, a medição sobre a base "
         "inteira superestimou a incompletude de um campo condicional em 16,7 "
         "pontos percentuais.")

    titulo(d, "Classificação da incompletude", 4)

    p(d, "A incompletude apurada é classificada segundo a escala de Romero e "
         "Cunha (2006), consagrada na avaliação de bases do Sistema Único de "
         "Saúde. Registre-se que a escala classifica a incompletude, e não a "
         "completude: valores baixos são favoráveis. A inversão é fonte "
         "frequente de erro de leitura em relatórios de qualidade, razão pela "
         "qual o produto explicita o sentido da medida em cada aba.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Escala de classificação da incompletude",
        ["Incompletude", "Classificação"],
        [["Menor que 5%", "Excelente"], ["De 5% a menos de 10%", "Bom"],
         ["De 10% a menos de 20%", "Regular"], ["De 20% a menos de 50%", "Ruim"],
         ["50% ou mais", "Muito ruim"]],
        "Fonte: Romero e Cunha (2006).", larguras=[7.5, 7.5])

    titulo(d, "Regras de consistência", 4)

    p(d, "As relações entre campos previstas no dicionário são verificadas "
         "registro a registro. Tratam-se de regras do próprio instrumento, e "
         "não de critérios arbitrados: a precedência cronológica entre "
         "sintomas, notificação, investigação e encerramento, e as condições "
         "de habilitação de campos específicos, como a escolaridade aplicável "
         "apenas a menores de sete anos ou a classificação restrita à "
         "hepatite A.")

    n["programa"] = programa(
        d, n["programa"], "Verificação das regras de consistência",
        _codigo("qualidade_sinan", "verificar_regras"),
        "referencia/qualidade_sinan.py")

    titulo(d, "Atribuição de prioridade", 4)

    p(d, "Cada pendência recebe prioridade derivada da classe do campo no "
         "dicionário e do tipo de falta, e não de juízo caso a caso. A regra "
         "é a seguinte: campo obrigatório em branco e violação de regra "
         "recebem prioridade alta, por comprometerem, respectivamente, a "
         "validade do registro e a sua coerência interna; campo obrigatório "
         "preenchido como ignorado e campo essencial recebem prioridade "
         "média; os demais, baixa.")

    n["programa"] = programa(
        d, n["programa"], "Derivação da prioridade a partir do dicionário",
        _codigo("qualidade_sinan", "prioridade_da_pendencia"),
        "referencia/qualidade_sinan.py")

    titulo(d, "Duplicidades", 3)

    p(d, "A detecção distingue o par exato — nome, nome da mãe e data de "
         "nascimento idênticos — do par provável, em que a similaridade do "
         "nome é igual ou superior a 88 com data de nascimento coincidente, "
         "ou igual ou superior a 92 com nome da mãe acima de 90 e data "
         "parcial ou ausente.")

    p(d, "Conforme a quarta premissa, a similaridade não basta para "
         "caracterizar erro. Cada par é adicionalmente classificado pelo "
         "intervalo entre as datas de notificação, que é o elemento capaz de "
         "distinguir o lançamento repetido da renotificação legítima.")

    n["programa"] = programa(
        d, n["programa"], "Classificação do par pelo intervalo entre notificações",
        _codigo("qualidade_sinan", "classificar_intervalo"),
        "referencia/qualidade_sinan.py")

    p(d, "Na aplicação de outubro de 2026, foram identificados 392 pares na "
         "base de notificações, dos quais 177 exatos e 215 prováveis. A "
         "classificação pelo intervalo revelou que 99 correspondiam a "
         "provável duplicidade de lançamento, 141 exigiam verificação e 137 "
         "configuravam provável renotificação. Apenas o primeiro grupo "
         "comporta tratamento como erro; tratar os 392 pares como "
         "duplicidades a excluir teria apagado informação legítima em mais de "
         "um terço dos casos.")

    # ------------------------------------------------------------------ #
    titulo(d, "Validação interna do método", 2, nova_pagina=True)

    p(d, "O procedimento dispõe de uma propriedade que permite validá-lo sem "
         "recurso a amostra externa: o subconjunto de registros cujo vínculo "
         "é declarado pelo número da notificação funciona como padrão de "
         "referência para o pareamento probabilístico.")

    p(d, "O raciocínio é o seguinte. Para os 190 usuários da categoria 1 — "
         "aqueles cujo número de notificação foi localizado e confirmado —, "
         "conhece-se o par verdadeiro por via independente. Pode-se então "
         "perguntar: quantos deles o pareamento probabilístico também teria "
         "encontrado, caso o número não existisse? A resposta mede a "
         "sensibilidade do algoritmo contra um padrão que não deriva dele.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Validação do pareamento probabilístico contra o vínculo declarado",
        ["Indicador", "N", "%"],
        [["Usuários com vínculo direto confirmado (categoria 1)", "190", "—"],
         ["também localizados por nome e data de nascimento", "178", "93,7"],
         ["Nome da mãe confere nas categorias 1 a 3", "331", "90,2"],
         ["Data de nascimento exata nas categorias 1 a 3", "358", "97,5"]],
        "Fonte: elaboração própria, a partir do produto de outubro de 2026.",
        larguras=[9.5, 2.5, 3.0])

    p(d, "A sensibilidade de 93,7% significa que, entre os pares cuja "
         "veracidade é conhecida, o algoritmo recuperaria quase todos sem o "
         "auxílio do identificador. O resultado sustenta o emprego do "
         "procedimento sobre os 511 cadastros em que o número não estava "
         "preenchido — que é, afinal, a razão de ser do pareamento "
         "probabilístico.")

    p(d, "As duas linhas seguintes da tabela medem coisa distinta: não a "
         "sensibilidade, mas a confiabilidade do conjunto de pares "
         "estabelecidos. O nome da mãe, variável que não participou da "
         "decisão, confere em 90,2% dos casos; a data de nascimento coincide "
         "exatamente em 97,5%. Tratam-se de verificações independentes, e a "
         "sua convergência reforça a validade do resultado.")

    p(d, "Esse desenho de validação tem uma limitação que convém explicitar: "
         "o subconjunto de referência não é aleatório. Usuários cujo número "
         "de notificação foi corretamente registrado podem ter, em média, "
         "cadastro de melhor qualidade que os demais, o que tenderia a "
         "superestimar a sensibilidade. A medida deve ser lida, portanto, "
         "como limite superior.")
