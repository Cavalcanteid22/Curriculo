# -*- coding: utf-8 -*-
"""Seções 4 a 7: produtos, avaliação, achados e limitações."""

from pathlib import Path

from gerar_capitulo import (citacao, extrair_atribuicao, extrair_funcao,
                            extrair_trecho, figura, lista, p, programa,
                            tabela, titulo)

GRAFICOS = Path("/tmp/claude-0/-home-user-Curriculo/"
                "9798b6f8-ca13-5a35-949c-dc3fbfc4df1e/scratchpad/"
                "exemplos/graficos")
CAPTURAS = Path("/tmp/claude-0/-home-user-Curriculo/"
                "9798b6f8-ca13-5a35-949c-dc3fbfc4df1e/scratchpad")


def escrever(d, n):
    # ------------------------------------------------------------------ #
    titulo(d, "Indicadores e análises", 3, nova_pagina=True)

    p(d, "Concluído o relacionamento, a ferramenta calcula os indicadores "
         "previstos no quadro de avaliação do produto técnico deste projeto, "
         "acrescidos das análises estatísticas e epidemiológicas que compõem "
         "o relatório.")

    p(d, "Os indicadores de desempenho do pareamento — sensibilidade, valor "
         "preditivo positivo e proporção de falsos-positivos — são aferidos "
         "contra amostra de referência. A implementação adota precaução "
         "relevante: quando há duplicatas, exige-se da rotina a recuperação "
         "de um par por pessoa, e não de todas as combinações possíveis, que "
         "seriam artefato da duplicidade e inflariam artificialmente o "
         "denominador.")

    n["programa"] = programa(
        d, n["programa"],
        "Indicadores de desempenho do pareamento",
        extrair_funcao("indicadores", "ValidacaoPareamento", ate_linha=32),
        "elosis/indicadores.py")

    p(d, "As projeções empregam regressão linear pelo método dos mínimos "
         "quadrados, acompanhadas do intervalo de predição de 95%, que "
         "incorpora tanto a incerteza da estimativa dos parâmetros quanto a "
         "dispersão residual observada. O método é deliberadamente simples e "
         "auditável: modelos mais elaborados exigiriam séries históricas mais "
         "longas do que as disponíveis no recorte anual, e sua complexidade "
         "dificultaria a leitura por equipes que não são especialistas em "
         "estatística — público a que o produto se destina.")

    p(d, "A ferramenta reporta o coeficiente de determinação e, quando este "
         "é baixo, adverte explicitamente que a projeção deve ser lida como "
         "cenário de referência, e não como previsão. Essa advertência "
         "automática responde a um risco concreto: a projeção apresentada sem "
         "qualificação tende a ser tomada como previsão, ainda que o ajuste do "
         "modelo não a autorize.")

    n["programa"] = programa(
        d, n["programa"],
        "Projeção por regressão linear com intervalo de predição",
        extrair_funcao("indicadores", "projetar_serie"),
        "elosis/indicadores.py", corpo=7)

    p(d, "Os intervalos de confiança das proporções empregam o método de "
         "Wilson, preferido ao intervalo de Wald por manter cobertura "
         "adequada quando a proporção se aproxima dos extremos e quando o "
         "denominador é pequeno — situação frequente em recortes por bairro "
         "ou por faixa etária, como os que a vigilância municipal realiza.")

    # ------------------------------------------------------------------ #
    titulo(d, "Produtos gerados pela ferramenta", 2, nova_pagina=True)

    p(d, "A ferramenta entrega três arquivos a cada execução.")

    titulo(d, "Planilha de resultados", 3)

    p(d, "A planilha é o instrumento de trabalho da equipe. Contém vinte e "
         "oito abas, organizadas em blocos: as bases nativas registro a "
         "registro, a qualificação por dimensão, as duplicidades, a "
         "harmonização, os dois estágios de pareamento, os registros sem par, "
         "os indicadores, as recomendações consolidadas e a trilha de "
         "auditoria.")

    p(d, "Nas abas das bases, cada registro recebe a cor correspondente à sua "
         "classificação e treze colunas analíticas acrescentadas ao final, "
         "que informam a descrição das inconsistências encontradas, os campos "
         "afetados, as dimensões de qualidade comprometidas, a justificativa "
         "técnico-normativa, a recomendação de correção na base nativa, a "
         "sugestão de encaminhamento à área técnica, a prioridade e a "
         "situação do registro quanto ao pareamento.")

    p(d, "As colunas nativas são preservadas sem qualquer alteração. Essa "
         "decisão, já mencionada a propósito da harmonização, tem aqui sua "
         "razão prática mais evidente: a área técnica precisa confrontar o "
         "valor registrado no sistema com o valor que a ferramenta apurou, "
         "sem o que não pode verificar a recomendação nem corrigi-la quando "
         "improcedente.")

    n["figura"] = figura(
        d, n["figura"],
        "Classificação dos registros por base, na execução de avaliação",
        GRAFICOS / "classificacao.png",
        "Fonte: elaboração própria, gerado pela ferramenta a partir das bases "
        "fictícias de avaliação.")

    titulo(d, "Relatório analítico-descritivo", 3)

    p(d, "O relatório é gerado em formato de documento de texto, segundo as "
         "normas da ABNT, e destina-se a dois públicos simultâneos: a "
         "coordenação do setor, que precisa de síntese e de fundamentação, e "
         "a equipe técnica, que precisa de orientação operacional. Contém "
         "dezoito tabelas e onze gráficos, e está organizado de modo que cada "
         "seção de resultado seja seguida de sua interpretação em linguagem "
         "corrente.")

    p(d, "Compõem o relatório a metodologia empregada, com indicação do "
         "referencial que a fundamenta; os resultados da qualificação por "
         "dimensão; os resultados do pareamento, incluindo a reprodução, "
         "sobre as bases em uso, do experimento de adição sequencial de "
         "chaves; as análises estatísticas e epidemiológicas, com os "
         "coeficientes calculados e respectivos intervalos de confiança; as "
         "projeções; as análises comparativas entre as bases; as orientações "
         "dirigidas às áreas técnicas; e as limitações reconhecidas.")

    n["figura"] = figura(
        d, n["figura"],
        "Exemplo de gráfico de projeção produzido pelo relatório",
        GRAFICOS / "projecao_1.png",
        "Fonte: elaboração própria, gerado pela ferramenta. A série observada "
        "aparece em linha contínua; a projeção, em tracejado, acompanhada da "
        "banda de predição de 95%.")

    titulo(d, "Trilha de auditoria", 3)

    p(d, "A trilha registra, em formato estruturado, o ambiente de execução, "
         "os parâmetros adotados, o resumo criptográfico SHA-256 de cada "
         "arquivo de entrada e de saída, os eventos do processamento e as "
         "tentativas de saída de rede bloqueadas. Sua função é permitir a "
         "reconstituição posterior do que foi processado, com que parâmetros "
         "e sobre qual versão de cada base, sem que seja necessário armazenar "
         "cópia dos dados pessoais.")

    # ------------------------------------------------------------------ #
    titulo(d, "Interface com o usuário", 2, nova_pagina=True)

    p(d, "O requisito de operabilidade por profissionais sem formação em "
         "informática orientou o desenho da interface gráfica. Adotaram-se "
         "três decisões.")

    p(d, "A primeira é a redução do caminho principal a três passos visíveis: "
         "escolher as bases, escolher onde salvar e executar. Todos os demais "
         "parâmetros — limiares, ano de referência, população, horizonte de "
         "projeção, perspectiva de identidade — permanecem recolhidos em "
         "seção de opções avançadas, com valores padrão adequados ao uso "
         "corrente. O usuário que não deseje ajustá-los não precisa sequer "
         "saber que existem.")

    p(d, "A segunda é que o programa nunca fica sem resposta. O processamento "
         "corre em linha de execução própria, e a barra de progresso informa a "
         "etapa em curso. Um programa que permanece imóvel durante minutos "
         "induz o usuário a encerrá-lo, perdendo o trabalho já realizado.")

    p(d, "A terceira é que as mensagens dizem o que houve e o que fazer, em "
         "lugar de reproduzir o erro técnico. Quando nenhuma base pode ser "
         "lida, por exemplo, a mensagem enumera o motivo de cada arquivo, "
         "distinguindo formato inválido, arquivo vazio e ausência de "
         "permissão de leitura.")

    p(d, "Acrescentou-se à interface um recurso destinado à apropriação da "
         "ferramenta pela equipe: o botão que gera bases fictícias de exemplo. "
         "Aragão e Almeida Filho (2026) desenvolvem o conceito de apropriação "
         "sociotécnica, que envolve a atribuição de sentido ao objeto técnico, "
         "a aquisição de cultura técnica e o desenvolvimento de habilidades e "
         "competências. O recurso responde a essa perspectiva: permite que a "
         "equipe conheça o comportamento da ferramenta, e verifique o seu "
         "desempenho contra um resultado conhecido, antes de empregá-la sobre "
         "bases reais.")

    n["figura"] = figura(
        d, n["figura"],
        "Interface gráfica da ferramenta, com as opções avançadas abertas",
        CAPTURAS / "gui.png",
        "Fonte: elaboração própria. Captura de tela da versão final.",
        largura=14.5)

    p(d, "A ferramenta dispõe ainda de interface de linha de comando, "
         "destinada à execução em lote e ao agendamento periódico, situação "
         "em que a interface gráfica seria inadequada.")

    # ------------------------------------------------------------------ #
    titulo(d, "Avaliação do produto", 2, nova_pagina=True)

    titulo(d, "Estratégia de avaliação", 3)

    p(d, "A avaliação foi conduzida sobre bases fictícias, conforme previsto "
         "na metodologia deste projeto, que estabelece a utilização exclusiva "
         "de bases de caráter ilustrativo, semelhantes às produzidas pelos "
         "sistemas, sem coleta de dados junto a participantes.")

    p(d, "Desenvolveu-se, para esse fim, um gerador de bases fictícias que "
         "produz os três sistemas com estrutura de campos equivalente à real "
         "e que, deliberadamente, insere nelas os defeitos observados na "
         "rotina da SUIS: duplicidades dos três tipos, campos obrigatórios em "
         "branco, códigos fora de domínio, datas impossíveis, pesos "
         "implausíveis e erros de digitação em campos nominais.")

    p(d, "O gerador produz, simultaneamente, um gabarito que registra qual "
         "pessoa corresponde a qual registro em cada base. É esse gabarito "
         "que permite aferir a sensibilidade e o valor preditivo positivo do "
         "pareamento contra um resultado conhecido — procedimento análogo ao "
         "previsto no quadro de indicadores deste projeto, que estabelece a "
         "revisão de amostra aleatória por dois avaliadores independentes.")

    p(d, "Três cuidados foram necessários na construção do gerador, e cada um "
         "deles corrigiu um viés que teria invalidado a avaliação.")

    lista(d, [
        "As populações precisam ser disjuntas. Na primeira versão, as pessoas "
        "que existiam apenas no SINAN e apenas no SIM eram sorteadas do mesmo "
        "conjunto, o que produzia sobreposição acidental não registrada no "
        "gabarito: pares verdadeiros eram contabilizados como "
        "falsos-positivos, e o valor preditivo positivo apurado foi de 39,5%, "
        "quando o real era 100%.",
        "As duplicatas precisam constar do gabarito. Registros duplicados "
        "inseridos após a montagem do gabarito seriam contabilizados como "
        "falsos-positivos ao parearem corretamente.",
        "A criança que morre precisa ter, no SIM, a mesma mãe declarada no "
        "SINASC. A primeira versão atribuía mães distintas nos dois sistemas, "
        "o que reduzia artificialmente a similaridade dos pares verdadeiros.",
    ])

    p(d, "O registro desses vieses não é digressão. Eles ilustram que a "
         "construção de uma base de avaliação é, ela própria, objeto de "
         "decisão metodológica: uma base mal construída produz medidas de "
         "desempenho que parecem rigorosas e não o são.")

    titulo(d, "Desempenho do pareamento", 3)

    p(d, "A avaliação foi conduzida sobre 135.162 registros distribuídos em "
         "três bases: 61.200 no SINAN, 26.242 no SIM e 47.720 no SINASC. Os "
         "resultados constam da tabela seguinte.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Desempenho do pareamento contra o gabarito",
        ["Relacionamento", "Pares determinísticos", "Pares probabilísticos",
         "Revisão manual", "Sensibilidade", "VPP"],
        [["SINAN × SIM", "4.569", "1.237", "5.742", "75,9%", "91,6%"],
         ["SINAN × SINASC", "2.501", "1.614", "12.258", "41,0%", "69,8%"],
         ["SIM × SINASC", "567", "315", "1.670", "73,1%", "66,3%"]],
        "Fonte: elaboração própria. VPP: valor preditivo positivo.",
        larguras=[3.2, 2.6, 2.6, 2.2, 2.2, 2.2], corpo=8)

    p(d, "A leitura conjunta dos dois indicadores é o que permite julgar o "
         "procedimento. O valor preditivo positivo mede a confiabilidade "
         "daquilo que a rotina afirma; a sensibilidade mede o quanto ela deixa "
         "de encontrar. O comportamento observado — valor preditivo positivo "
         "alto com sensibilidade moderada — é o desejável em vigilância: um "
         "procedimento conservador, que erra por omissão e não por afirmação. "
         "O falso-positivo propaga-se silenciosamente aos indicadores; o par "
         "não recuperado permanece visível na aba de registros sem par.")

    p(d, "Cabe qualificar a sensibilidade observada. As bases fictícias foram "
         "deliberadamente degradadas em grau superior ao esperado em bases "
         "reais: entre 18% e 22% dos nomes receberam erro de digitação e "
         "entre 12% e 24% dos nomes de mãe foram suprimidos. A sensibilidade "
         "apurada corresponde, portanto, a cenário adverso, e não ao cenário "
         "esperado em produção.")

    p(d, "Observou-se ainda que os pares verdadeiros não recuperados "
         "concentram-se na faixa de revisão manual. No relacionamento entre "
         "SINAN e SINASC, por exemplo, 47 dos 55 pares não recuperados "
         "automaticamente encontravam-se nessa faixa. O achado é "
         "operacionalmente relevante: indica que a conferência manual dessa "
         "faixa tem rendimento alto e justifica a alocação de equipe, ao "
         "contrário do que ocorreria se os pares perdidos estivessem "
         "dispersos abaixo do limiar.")

    n["figura"] = figura(
        d, n["figura"],
        "Sensibilidade e valor preditivo positivo por relacionamento",
        GRAFICOS / "desempenho.png",
        "Fonte: elaboração própria, gerado pela ferramenta.")

    titulo(d, "Desempenho computacional", 3)

    p(d, "O tempo de execução foi aferido sobre o mesmo conjunto de 135.162 "
         "registros, em máquina de configuração modesta.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Tempo de execução por etapa",
        ["Etapa", "Tempo"],
        [["Leitura e qualificação das três bases", "50 segundos"],
         ["Pareamento (três relacionamentos)", "2 minutos e 30 segundos"],
         ["Geração da planilha e do relatório", "3 minutos e 20 segundos"],
         ["Total", "7 minutos"]],
        "Fonte: elaboração própria. Consumo máximo de memória: 1,2 GB.",
        larguras=[10.0, 5.0])

    p(d, "O tempo de execução deve ser confrontado com o do procedimento "
         "manual mapeado na etapa de diagnóstico situacional. É essa "
         "comparação, e não o valor absoluto, que permite aferir o ganho de "
         "eficiência previsto entre os indicadores de avaliação do produto.")
