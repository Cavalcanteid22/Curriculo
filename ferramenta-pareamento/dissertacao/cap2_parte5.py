# -*- coding: utf-8 -*-
"""Aplicabilidade, limitações, reprodutibilidade e considerações finais."""

from gerar_capitulo import citacao, lista, p, tabela, titulo


def escrever(d, n):
    titulo(d, "Aplicabilidade", 2, nova_pagina=True)

    p(d, "A aplicabilidade do procedimento é discutida em três planos: o uso "
         "imediato pelas áreas técnicas de vigilância, a transposição para "
         "outros pares de sistemas e as condições institucionais que o uso "
         "pressupõe.")

    titulo(d, "Uso pelas áreas técnicas de vigilância", 3)

    p(d, "O produto destina-se ao trabalho cotidiano das áreas técnicas e não "
         "à produção de um indicador agregado. Essa destinação determina a "
         "forma de apresentação: a unidade de leitura é o registro, não a "
         "proporção. Cada linha corresponde a um caso sobre o qual é possível "
         "agir, e as colunas finais informam qual é a ação, a quem compete e "
         "com que urgência. A escolha decorre de uma constatação operacional: "
         "um relatório que informe que determinada proporção dos registros "
         "está incompleta não permite corrigir registro algum, porque não "
         "identifica quais registros são, em que sistema estão e o que neles "
         "falta.")

    p(d, "Do procedimento derivam quatro usos distintos, que correspondem a "
         "quatro competências institucionais diferentes.")

    p(d, "O primeiro é a busca ativa de notificação. Os usuários presentes no "
         "sistema de dispensação de medicamentos sem notificação localizada "
         "no sistema de agravos, bem como os óbitos registrados por causa de "
         "notificação compulsória sem notificação correspondente, constituem "
         "listas nominais de investigação. Não são, conforme a segunda "
         "premissa enunciada, medidas de subnotificação: são hipóteses a "
         "verificar, ordenadas por critério de prioridade, cuja apuração cabe "
         "ao serviço de vigilância do território onde o caso foi registrado.")

    p(d, "O segundo é o encerramento oportuno de casos. O cruzamento com o "
         "sistema de mortalidade identifica notificações cujo campo de "
         "evolução permanece em branco ou registra situação diversa daquela "
         "comprovada pela declaração de óbito. Trata-se de correção que "
         "incide diretamente sobre indicadores de encerramento e de "
         "letalidade, calculados a partir do campo que se encontra "
         "inconsistente.")

    p(d, "O terceiro é a correção das bases nativas. As pendências de "
         "qualidade são apresentadas com indicação do sistema de origem, do "
         "campo e da regra violada, de modo que a correção possa ser feita "
         "no sistema onde o dado foi digitado — e não apenas na cópia "
         "analisada. Essa distinção é o que diferencia a qualificação de uma "
         "base de trabalho da qualificação do registro de origem: somente a "
         "segunda produz efeito duradouro, porque toda extração posterior "
         "voltaria a reproduzir o erro não corrigido na fonte.")

    p(d, "O quarto é o subsídio à gestão. A distribuição das pendências por "
         "campo, por unidade notificante e por prioridade indica onde a "
         "capacitação e a supervisão produzem maior efeito. Um campo "
         "sistematicamente ignorado em determinada unidade sugere problema de "
         "fluxo ou de treinamento, não de digitação individual, e comporta "
         "resposta de natureza distinta.")

    titulo(d, "Transposição a outros pares de sistemas", 3)

    p(d, "A rotina foi aplicada a dois pares de sistemas, mas o método não é "
         "específico a eles. A sua estrutura separa o que é geral do que é "
         "particular: as funções de padronização, de comparação aproximada, "
         "de blocagem, de pontuação e de classificação não contêm referência "
         "a sistema algum; o que é próprio de cada sistema concentra-se na "
         "declaração dos campos, das suas obrigatoriedades e das suas regras "
         "de consistência. Transpor a rotina a um novo par de sistemas "
         "consiste, portanto, em declarar os campos do novo sistema e o "
         "mapeamento entre eles, sem alteração da lógica de pareamento.")

    p(d, "As condições para a transposição são três, e convém enunciá-las com "
         "precisão, porque delimitam o alcance real do procedimento.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Condições para aplicação do procedimento a um novo par de sistemas",
        ["Condição", "Exigência", "Consequência se ausente"],
        [["Atributos de identificação comuns",
          "Nome do indivíduo e, desejavelmente, nome da mãe e data de "
          "nascimento",
          "O pareamento probabilístico perde discriminação; sem nome, torna-se "
          "inviável"],
         ["Dicionário de dados do sistema",
          "Classificação de obrigatoriedade dos campos e regras de "
          "consistência documentadas",
          "A verificação de qualidade fica restrita à completude bruta, sem "
          "distinção entre campo não aplicável e campo omitido"],
         ["Recorte populacional e temporal definido",
          "Critério explícito de quais registros devem e quais não devem estar "
          "em cada base",
          "A ausência de correspondência deixa de ser interpretável: não se "
          "distingue registro faltante de registro fora do recorte"]],
        "Fonte: elaboração própria.", larguras=[3.6, 5.8, 5.6], corpo=8)

    p(d, "Satisfeitas essas condições, são imediatamente candidatos à "
         "aplicação os relacionamentos entre o sistema de agravos de "
         "notificação e os sistemas de internação hospitalar, de informações "
         "ambulatoriais, de nascidos vivos e de exames laboratoriais, assim "
         "como o cruzamento entre bases de programas específicos e o cadastro "
         "nacional de usuários.")

    titulo(d, "Condições institucionais de uso", 3)

    p(d, "A aplicabilidade do procedimento não é apenas técnica. Três "
         "condições institucionais a sustentam.")

    lista(d, [
        "Execução local dos dados identificados. O tratamento ocorre na "
        "estação de trabalho do serviço, sem transmissão a serviço externo, "
        "conforme o requisito não funcional de confidencialidade e em "
        "atendimento ao disposto na Lei nº 13.709, de 2018, quanto ao "
        "tratamento de dados pessoais sensíveis referentes à saúde.",
        "Competência definida para o retorno. O produto reserva colunas à "
        "resposta da área técnica; essa resposta precisa ter responsável "
        "designado, sem o que o ciclo de qualificação não se fecha e a rodada "
        "seguinte repete os mesmos achados.",
        "Periodicidade estabelecida. A qualificação só produz efeito "
        "cumulativo se for recorrente: a comparação entre rodadas é o que "
        "permite distinguir o erro corrigido do erro persistente e medir o "
        "resultado da intervenção.",
    ], numerada=True)

    p(d, "A terceira condição merece registro particular. Uma rodada isolada "
         "de pareamento descreve o estado das bases em um momento; a "
         "repetição periódica transforma a descrição em instrumento de "
         "monitoramento, no qual o próprio conjunto de pendências passa a "
         "funcionar como indicador de processo da vigilância.")

    # ------------------------------------------------------------------ #
    titulo(d, "Limitações", 2)

    p(d, "As limitações do procedimento são de quatro ordens.")

    p(d, "A primeira é inerente ao relacionamento probabilístico. Na ausência "
         "de identificador unívoco, a correspondência entre registros é "
         "inferida a partir de atributos sujeitos a variação de grafia, a "
         "mudança de nome e a homonímia. Daí resultam dois tipos de erro: o "
         "par falso, quando registros de pessoas distintas são aproximados, e "
         "o par perdido, quando registros da mesma pessoa não são "
         "reconhecidos. A estratégia adotada — faixa intermediária remetida à "
         "conferência manual, em lugar de decisão automática — reduz o "
         "primeiro tipo de erro à custa de trabalho humano, mas não elimina "
         "nenhum dos dois.")

    p(d, "A segunda decorre da blocagem. A restrição das comparações a blocos "
         "definidos por atributos de identificação torna o processamento "
         "viável, mas impede, por construção, o reconhecimento de pares cujos "
         "atributos de blocagem divirjam simultaneamente. Um registro com "
         "nome gravemente corrompido e data de nascimento divergente não "
         "entra em nenhum bloco comum e não é recuperado. O ganho "
         "computacional tem, portanto, custo em sensibilidade, e esse custo "
         "não é observável a partir do próprio resultado.")

    p(d, "A terceira refere-se à verificação de qualidade. O procedimento "
         "verifica a conformidade do registro às regras do sistema que o "
         "abriga: campo obrigatório preenchido, código pertencente ao "
         "domínio, datas em ordem cronológica compatível, regra condicional "
         "respeitada. Não verifica, nem poderia verificar a partir da base, a "
         "veracidade do dado. Um registro integralmente conforme pode conter "
         "informação falsa, e a ferramenta o classificaria sem pendência. A "
         "qualificação aqui realizada é, nesse sentido, condição necessária e "
         "não suficiente da fidedignidade da informação.")

    p(d, "A quarta é relativa à validação. A conferência manual que aferiu a "
         "classificação automática incidiu sobre registros selecionados por "
         "critério de utilidade operacional — casos de fronteira entre "
         "categorias —, e não por amostragem probabilística. Os valores de "
         "concordância obtidos descrevem, portanto, o desempenho sobre os "
         "casos verificados, e não estimativa com intervalo de confiança "
         "aplicável ao conjunto das bases. Uma validação com amostra aleatória "
         "e padrão de referência independente permanece como desenvolvimento "
         "necessário.")

    p(d, "Registre-se, por fim, que nenhuma dessas limitações é particular a "
         "este procedimento: todas são próprias da técnica de relacionamento "
         "de bases sem identificador comum, e a literatura as discute desde "
         "as formulações iniciais do método. O que cabe ao instrumento não é "
         "suprimi-las, e sim torná-las explícitas, de modo que a área técnica "
         "saiba o que o resultado afirma e o que ele não afirma.")

    # ------------------------------------------------------------------ #
    titulo(d, "Reprodutibilidade e procedência do código apresentado", 2)

    p(d, "Para que o leitor possa situar corretamente o que se apresentou, "
         "convém distinguir dois registros do mesmo método.")

    p(d, "O primeiro é o registro metodológico contido nos próprios produtos "
         "entregues às áreas técnicas. As planilhas de pareamento incorporam "
         "aba de metodologia que documenta, para cada rodada, as fontes "
         "utilizadas, o recorte temporal, as regras de padronização, os pesos "
         "atribuídos a cada atributo, os pontos de corte e a definição de cada "
         "categoria de resultado. Essa documentação embutida é o registro "
         "primário do procedimento: acompanha o produto, não se perde na "
         "circulação do arquivo e permite que a área técnica verifique, no "
         "momento do uso, sob quais parâmetros o resultado foi produzido.")

    p(d, "O segundo é o conjunto de listagens apresentado neste capítulo. "
         "Trata-se de implementação de referência, escrita e testada "
         "especificamente para esta exposição, que reproduz os parâmetros "
         "documentados no registro primário — os mesmos pesos, os mesmos "
         "pontos de corte, as mesmas categorias e as mesmas regras de "
         "aplicabilidade de campo. A sua finalidade é expositiva e "
         "verificatória: permite que o método seja lido, criticado e "
         "reexecutado de forma independente, com casos de prova que fixam o "
         "comportamento esperado em cada categoria de classificação. Não se "
         "apresenta, portanto, como transcrição dos arquivos de execução das "
         "rodadas descritas, e sim como formalização verificável do método "
         "que as orientou.")

    p(d, "A distinção tem consequência prática para quem pretenda reproduzir "
         "o procedimento. Os parâmetros são explícitos e estão reunidos em "
         "constantes nomeadas no início de cada módulo, de modo que a sua "
         "alteração não exige leitura do restante do código; as funções de "
         "decisão são puras, isto é, dependem apenas dos seus argumentos, o "
         "que as torna testáveis isoladamente; e os casos de prova "
         "acompanham o código, podendo ser executados sem acesso a dado real "
         "algum. Essas três propriedades, e não a posse dos arquivos "
         "originais, são o que efetivamente sustenta a reprodutibilidade.")

    citacao(d, "A escassez de estudos metodológicos que apresentem os "
               "procedimentos necessários à execução da técnica de "
               "relacionamento de bases de dados impõe a necessidade de "
               "produção e disseminação de modelos de análise passíveis de "
               "adaptação a diferentes realidades e áreas do conhecimento em "
               "saúde.",
            "Garcia, Miranda e Sousa (2022)")

    # ------------------------------------------------------------------ #
    titulo(d, "Considerações sobre o capítulo", 2)

    p(d, "O procedimento descrito responde a um problema que não é de "
         "processamento, mas de arquitetura da informação em saúde: sistemas "
         "concebidos em momentos distintos, com finalidades distintas e sem "
         "identificação unívoca do usuário, registram eventos da mesma pessoa "
         "sem que haja meio direto de reconhecê-los como tais. O "
         "relacionamento probabilístico é, nesse contexto, solução "
         "compensatória — e a sua própria necessidade é evidência do problema "
         "que compensa.")

    p(d, "Duas contribuições cabe destacar. A primeira é a integração, em "
         "procedimento único, de duas atividades habitualmente separadas: o "
         "relacionamento entre bases e a verificação dos atributos de "
         "qualidade. A separação tem custo analítico, porque a qualidade dos "
         "atributos de identificação é precisamente o que determina o "
         "desempenho do relacionamento; medi-la na mesma rotina permite "
         "interpretar o resultado do pareamento à luz da base que o produziu, "
         "em lugar de atribuir a ausência de par a subnotificação quando ela "
         "pode decorrer de incompletude do campo de identificação.")

    p(d, "A segunda é a orientação do produto à ação. A classificação por "
         "prioridade, a indicação do sistema de origem de cada pendência, a "
         "formulação de recomendação específica por tipo de achado e a reserva "
         "de campos para o retorno da área técnica convertem o resultado "
         "analítico em instrumento de trabalho. É a diferença entre informar "
         "que as bases apresentam problemas e indicar, registro por registro, "
         "qual é o problema, onde corrigi-lo e a quem compete fazê-lo.")

    p(d, "Permanece, contudo, o ponto de ordem conceitual. A ferramenta não "
         "substitui uma agenda de interoperabilidade entre os sistemas de "
         "informação em saúde: torna-a mensurável. Cada par não recuperado por "
         "ausência de identificador comum e cada pendência de preenchimento "
         "documentam uma consequência concreta da fragmentação. Nesse "
         "sentido, o produto serve a dois propósitos simultâneos — qualificar "
         "as bases hoje disponíveis e reunir evidência empírica para "
         "sustentar, junto às instâncias competentes, a necessidade de "
         "padronização e de identificação unívoca do usuário no Sistema Único "
         "de Saúde.")
