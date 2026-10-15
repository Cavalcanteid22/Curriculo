# -*- coding: utf-8 -*-
"""Seção 3 do capítulo: percurso de construção, etapa a etapa."""

from pathlib import Path

from gerar_capitulo import (citacao, extrair_atribuicao, extrair_funcao,
                            extrair_trecho, figura, lista, p, programa,
                            tabela, titulo)


def escrever(d, n):
    titulo(d, "Percurso de construção", 2, nova_pagina=True)

    p(d, "As seções seguintes descrevem a implementação de cada etapa do "
         "fluxo, na ordem em que são executadas. Para cada uma, apresenta-se "
         "o problema enfrentado, a decisão adotada, a justificativa e o "
         "trecho de código correspondente. A Figura 1 sintetiza o encadeamento "
         "das seis etapas e os três produtos que delas resultam.")

    n["figura"] = figura(
        d, n["figura"],
        "Fluxo de processamento da ferramenta",
        Path(__file__).resolve().parent / "figuras" / "fluxo.png",
        "Fonte: elaboração própria. A moldura tracejada indica que todo o "
        "processamento ocorre em ambiente local, sob bloqueio ativo de "
        "conexões externas.",
        largura=12.5)

    # ------------------------------------------------------------------ #
    titulo(d, "Leitura e identificação das bases", 3)

    p(d, "A primeira etapa lê as bases nos formatos em que os sistemas as "
         "exportam. Duas decisões orientaram a implementação.")

    p(d, "A primeira foi carregar todos os campos como texto, sem conversão "
         "automática de tipos. A conversão automática destrói silenciosamente "
         "os zeros à esquerda de códigos como CEP, CNES e código de município "
         "do IBGE, transformando o código 0004030 no número 4030. Mais grave, "
         "descarta ou converte em valor nulo justamente os preenchimentos "
         "inválidos — uma data como 31/02/2024, por exemplo — que constituem "
         "o objeto da etapa seguinte. Preservar o dado como texto é, "
         "portanto, condição para que a inconsistência possa ser detectada.")

    p(d, "A segunda decisão foi identificar o sistema de origem pela "
         "assinatura de campos, e não pelo nome do arquivo. Nomes de arquivo "
         "são atribuídos por pessoas e variam entre competências, unidades e "
         "operadores; o conjunto de campos é produzido pelo próprio sistema "
         "exportador e é estável. O nome do arquivo permanece como critério "
         "secundário, aplicado apenas quando a assinatura de campos é "
         "inconclusiva.")

    n["programa"] = programa(
        d, n["programa"],
        "Identificação do sistema de origem pela assinatura de campos",
        extrair_funcao("perfis", "identificar_sistema"),
        "elosis/perfis.py")

    p(d, "O leitor de arquivos DBF foi implementado em Python puro. A decisão "
         "decorre do requisito de execução em estações sem permissão de "
         "instalação: o DBF é o formato em que o DATASUS distribui as bases, e "
         "uma ferramenta que dependesse de biblioteca externa para lê-lo "
         "seria inutilizável precisamente onde mais se necessita dela. O "
         "leitor opera por fluxo, devolvendo um registro por vez, de modo que "
         "arquivos de centenas de megabytes sejam processados sem que a base "
         "inteira precise residir em memória.")

    p(d, "A validação do cabeçalho do arquivo foi acrescentada após "
         "verificação com entradas malformadas. Sem ela, um arquivo que não é "
         "DBF era interpretado como se fosse: os bytes iniciais convertiam-se "
         "em campos aparentemente plausíveis e o erro só se manifestava "
         "adiante, sob a forma de base vazia — mensagem que levava o usuário "
         "a procurar o problema no lugar errado.")

    n["programa"] = programa(
        d, n["programa"],
        "Validação do cabeçalho do arquivo DBF",
        extrair_trecho("dbf",
                       "        # Validação do cabeçalho.",
                       "        self._id_pagina"),
        "elosis/dbf.py")

    p(d, "A leitura de arquivos PDF recebeu tratamento defensivo específico. "
         "O PDF é formato de apresentação, e não de intercâmbio de dados: "
         "células sobrepostas e quebras de linha produzem valores embaralhados "
         "que nenhuma verificação posterior recupera. A ferramenta executa a "
         "extração porque relatórios de sistemas legados por vezes só estão "
         "disponíveis nesse formato, mas sinaliza a base assim obtida no "
         "relatório e recomenda a exportação em formato adequado na origem.")

    p(d, "Além disso, a captura de exceções nessa rotina é deliberadamente "
         "ampla. Bibliotecas de leitura de PDF dependem de extensões "
         "compiladas que, em instalações institucionais, podem estar ausentes "
         "ou quebradas — e falham de modos que não se reduzem ao erro de "
         "importação. Nenhuma dessas falhas deve impedir a leitura pela via "
         "alternativa, nem interromper a análise das demais bases.")

    # ------------------------------------------------------------------ #
    titulo(d, "Avaliação dos atributos de qualidade", 3, nova_pagina=True)

    p(d, "A qualificação das bases segue as dimensões identificadas por "
         "Ghalavand et al. (2024) em revisão sistemática que partiu de 760 "
         "artigos e submeteu 58 à apreciação crítica, da qual resultaram "
         "catorze dimensões de qualidade. Conforme definido na metodologia "
         "deste projeto, foram adotadas como prioritárias a acurácia, a "
         "completude e a consistência — rotineiramente avaliadas na SUIS —, "
         "acrescidas da oportunidade, apontada pelos autores entre as três "
         "mais empregadas na literatura.")

    titulo(d, "Completude bruta e completude útil", 4)

    p(d, "A implementação da completude revelou uma distinção que a literatura "
         "consultada não explicita e que se mostrou consequente. Um campo "
         "pode encontrar-se em três situações: em branco; preenchido com "
         "código convencionado de ignorado; ou preenchido com valor útil. "
         "Apenas a terceira constitui completude efetiva.")

    p(d, "A medida usual de completude — proporção de registros com o campo "
         "preenchido — não distingue a segunda da terceira situação. Do ponto "
         "de vista do sistema, o campo consta preenchido e a base aparenta "
         "completude satisfatória; do ponto de vista analítico, a informação "
         "inexiste. A ferramenta reporta, por isso, duas medidas em separado: "
         "a completude bruta, que corresponde à medida usual, e a completude "
         "útil, que desconta os códigos de ignorado. A diferença entre ambas "
         "é a dimensão do problema.")

    n["programa"] = programa(
        d, n["programa"],
        "Cálculo da completude, com distinção entre bruta e útil",
        extrair_funcao("qualidade", "calcular_completude"),
        "elosis/qualidade.py")

    titulo(d, "Acurácia: validação de domínio e de regras de formação", 4)

    p(d, "A acurácia é aferida pela conformidade do valor ao domínio e às "
         "regras de formação da variável. Foram implementadas verificações "
         "para os dígitos verificadores do CPF e do Cartão Nacional de Saúde, "
         "para a estrutura dos códigos da Classificação Internacional de "
         "Doenças, para a existência das datas no calendário e para a "
         "pertinência dos códigos aos domínios de cada sistema.")

    p(d, "O Programa a seguir apresenta a validação do CPF pelo algoritmo de "
         "módulo 11. Note-se que a função devolve, além do juízo de validade, "
         "o motivo da recusa: essa informação chega à planilha e ao relatório, "
         "de modo que a área técnica saiba o que conferir no documento-fonte.")

    n["programa"] = programa(
        d, n["programa"],
        "Validação do CPF pelos dígitos verificadores",
        extrair_funcao("normalizacao", "cpf_e_valido"),
        "elosis/normalizacao.py")

    titulo(d, "Consistência: coerência lógica entre variáveis", 4)

    p(d, "A verificação de consistência confronta variáveis do mesmo registro "
         "em busca de relações logicamente impossíveis ou implausíveis. Foram "
         "implementadas dez regras, que abrangem a ordem cronológica dos "
         "eventos, a plausibilidade biológica dos valores e a compatibilidade "
         "entre campos correlatos. O Programa seguinte reproduz uma delas, "
         "escolhida por ilustrar a estrutura adotada: cada achado carrega "
         "descrição, justificativa e recomendação.")

    n["programa"] = programa(
        d, n["programa"],
        "Regra de consistência: evento anterior ao nascimento",
        extrair_trecho("qualidade",
                       "        # 1. Evento anterior ao nascimento",
                       "        # 2. Idade implausível"),
        "elosis/qualidade.py")

    p(d, "A estrutura merece comentário. Cada achado não se limita a assinalar "
         "o problema: explicita por que ele constitui problema e o que fazer a "
         "respeito. Essa decisão responde a uma característica do público a "
         "que o produto se destina. Uma mensagem como “data inválida” exige "
         "que o usuário saiba interpretar a regra violada; uma mensagem que "
         "informa que nenhum evento de saúde pode preceder o nascimento do "
         "indivíduo, e que a causa mais frequente é inversão entre dia e mês, "
         "dispensa esse conhecimento prévio e indica a conferência a fazer.")

    titulo(d, "Classificação dos registros por cor", 4)

    p(d, "Cada registro recebe classificação em três níveis, materializada na "
         "planilha pela cor da linha: verde para registros sem inconsistência "
         "detectada, amarelo para os que apresentam provável inconsistência e "
         "exigem verificação manual, vermelho para os que apresentam "
         "inconsistência real.")

    p(d, "A distinção entre o real e o provável não é de grau, mas de "
         "natureza. Uma data inexistente no calendário é erro objetivo, "
         "verificável sem juízo. Uma similaridade elevada entre dois nomes é "
         "indício que demanda confirmação humana. Tratar as duas situações "
         "com o mesmo peso produziria, na prática, um de dois efeitos "
         "indesejáveis: ou a equipe passaria a conferir manualmente casos que "
         "dispensam conferência, ou passaria a corrigir automaticamente casos "
         "que exigem juízo.")

    p(d, "A atribuição segue a regra da gravidade máxima, apresentada a "
         "seguir.")

    n["programa"] = programa(
        d, n["programa"],
        "Classificação dos registros pela regra da gravidade máxima",
        extrair_funcao("qualidade", "classificar_linhas"),
        "elosis/qualidade.py")

    # ------------------------------------------------------------------ #
    titulo(d, "Detecção de duplicidades", 3, nova_pagina=True)

    p(d, "Garcia, Miranda e Sousa (2022) advertem quanto ao efeito das "
         "duplicidades sobre o relacionamento:")

    citacao(d, "Deve-se atentar para bases que contenham registros duplicados "
               "ou registros distintos referentes à mesma pessoa, uma vez que "
               "as funções de junção resultam em diferentes possibilidades de "
               "análise combinatória na presença de registros idênticos.",
            "GARCIA; MIRANDA; SOUSA, 2022")

    p(d, "A consequência prática é que a duplicidade não tratada antes do "
         "pareamento multiplica pares espúrios. A depuração, por isso, "
         "precede o relacionamento no fluxo da ferramenta.")

    p(d, "A implementação distingue três fenômenos que a rotina manual "
         "costuma tratar como um só:")

    lista(d, [
        "duplicata técnica — o mesmo número de identificação do sistema "
        "aparece em mais de um registro, o que em regra indica reimportação "
        "do mesmo lote;",
        "duplicata de conteúdo — registros de numeração distinta apresentam "
        "identificação nominal integralmente coincidente, o que indica "
        "digitação repetida do mesmo evento;",
        "duplicata provável — a similaridade entre os registros é elevada sem "
        "haver identidade exata, situação que pode corresponder tanto a "
        "duplicidade com erro de digitação quanto a pessoas distintas com "
        "nomes semelhantes, e que por isso é sempre encaminhada à "
        "verificação manual.",
    ])

    p(d, "A distinção tem consequência operacional direta. A duplicata "
         "técnica admite tratamento automatizável; a de conteúdo exige "
         "conferência, mas com alta probabilidade de confirmação; a provável "
         "exige juízo. Recomenda-se, em todos os casos, que a exclusão seja "
         "precedida da consolidação dos campos: registros duplicados "
         "frequentemente diferem quanto ao preenchimento, e a eliminação sem "
         "conferência descarta informação existente.")

    n["programa"] = programa(
        d, n["programa"],
        "Escore de similaridade para duplicidade intrabase",
        extrair_funcao("duplicidades", "_escore_duplicidade"),
        "elosis/duplicidades.py")

    # ------------------------------------------------------------------ #
    titulo(d, "Pré-processamento e harmonização", 3, nova_pagina=True)

    p(d, "O pré-processamento segue os procedimentos padronizados descritos "
         "por Garcia, Miranda e Sousa (2022). Para as variáveis nominais, "
         "adotam-se a conversão de todas as letras para maiúsculas, a remoção "
         "de acentos, de caracteres especiais e de espaços duplos e a "
         "supressão das preposições que ligam sobrenomes. Para as variáveis "
         "numéricas que frequentemente apresentam inconsistências de "
         "preenchimento, como o CPF, adotam-se a remoção completa de pontos e "
         "traços e o preenchimento com dígitos zero à esquerda até que o campo "
         "alcance os onze dígitos padronizados.")

    n["programa"] = programa(
        d, n["programa"],
        "Normalização de campos nominais",
        extrair_atribuicao("normalizacao", "PREPOSICOES") + "\n\n"
        + extrair_funcao("normalizacao", "_normalizar_nome_cache"),
        "elosis/normalizacao.py")

    p(d, "Acrescentou-se à lista canônica de preposições a supressão de "
         "iniciais isoladas. Registros que grafam o nome do meio como inicial "
         "— “MARIA J SILVA” em lugar de “MARIA JOSE SILVA” — são frequentes "
         "nas bases de vigilância, e a inicial isolada não discrimina, ao "
         "passo que distorce as métricas de similaridade por acrescentar um "
         "componente de comparação de baixo valor informativo.")

    p(d, "A harmonização, no sentido dado por Schmidt et al. (2020), "
         "constitui etapa distinta e posterior. Enquanto a normalização "
         "padroniza a forma do valor, a harmonização torna comparáveis "
         "variáveis que os sistemas registram sob nomes e codificações "
         "distintas. O caso mais evidente é o do sexo, codificado como 1 e 2 "
         "no SIM e no SINASC e como M e F no SINAN.")

    p(d, "Os autores identificaram seis termos correntes empregados como "
         "sinônimos de harmonização — record linkage, data linkage, data "
         "warehousing, data sharing, data interoperability e health "
         "information exchange —, o que recomenda precisão terminológica. "
         "Nesta ferramenta, harmonização designa a etapa que torna as "
         "variáveis comparáveis, e pareamento, a etapa que identifica "
         "registros referentes à mesma pessoa.")

    p(d, "Todas as variáveis harmonizadas são gravadas em colunas novas, "
         "identificadas pelo prefixo H_, e as colunas nativas permanecem "
         "inalteradas. A preservação é deliberada: a área técnica precisa ver "
         "lado a lado o valor registrado no sistema e o valor tratado, sem o "
         "que a recomendação de correção não é verificável.")

    p(d, "A correspondência entre os campos de cada sistema e as variáveis "
         "canônicas da ferramenta é declarada em estruturas denominadas "
         "perfis. Cada perfil reúne, além do mapeamento, os campos de "
         "preenchimento obrigatório segundo as normativas vigentes, os "
         "domínios de valores admitidos e o prazo normativo de registro. O "
         "Programa seguinte reproduz parcialmente o perfil do SIM.")

    n["programa"] = programa(
        d, n["programa"],
        "Perfil do Sistema de Informações sobre Mortalidade (excerto)",
        extrair_trecho("perfis", "PERFIL_SIM = PerfilSistema(",
                       "    mapeamento={", maximo=None).rstrip()
        + '\n    mapeamento={\n        # (...)\n    },\n'
        + extrair_trecho("perfis", "    obrigatorios={\n        NOME:",
                         "    recomendados={"),
        "elosis/perfis.py")
