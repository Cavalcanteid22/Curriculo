# -*- coding: utf-8 -*-
"""Seções 6 a 8: achados metodológicos, limitações e considerações."""

from gerar_capitulo import (citacao, extrair_funcao, extrair_trecho, lista, p,
                            programa, tabela, titulo)


def escrever(d, n):
    # ------------------------------------------------------------------ #
    titulo(d, "Achados metodológicos emergentes da implementação", 2,
           nova_pagina=True)

    p(d, "Esta seção reúne três achados que não constavam do desenho do "
         "produto e que emergiram da sua construção. Registram-se por "
         "constituírem contribuição do percurso de implementação, e não "
         "apenas do seu resultado.")

    titulo(d, "A perspectiva de identidade como parâmetro explícito", 3)

    p(d, "O primeiro achado foi descrito em seção própria e apenas se retoma "
         "aqui a sua formulação geral. Documentos que registram mais de um "
         "sujeito — a Declaração de Nascido Vivo é o caso evidente, mas não o "
         "único — exigem que a identidade a ser pareada seja declarada "
         "explicitamente, em função da pergunta epidemiológica. A omissão "
         "desse parâmetro não produz erro detectável, mas resultado vazio, "
         "que na rotina de serviço tende a ser interpretado como ausência de "
         "sobreposição entre as populações.")

    p(d, "A generalização possível é que rotinas de relacionamento devem "
         "tratar a identidade do sujeito como parâmetro de entrada, e não "
         "como propriedade implícita do arquivo.")

    titulo(d, "A completude aparente como categoria de análise", 3)

    p(d, "O segundo achado diz respeito à mensuração da completude. Conforme "
         "exposto, o preenchimento com código de ignorado produz completude "
         "aparente: o campo consta preenchido nas estatísticas usuais sem que "
         "a informação exista.")

    p(d, "Ghalavand et al. (2024) registram que persiste falta de "
         "uniformidade nas dimensões de qualidade empregadas e nos métodos de "
         "avaliação. A distinção entre completude bruta e completude útil é "
         "uma contribuição possível a essa uniformização, e é de implementação "
         "trivial: basta que o instrumento de medida conheça os códigos "
         "convencionados de ignorado de cada sistema.")

    p(d, "A relevância prática é imediata. Uma base cuja completude bruta "
         "aparenta ser satisfatória pode apresentar completude útil "
         "sensivelmente inferior, e a diferença entre as duas medidas indica "
         "precisamente onde a orientação às equipes notificadoras deve "
         "concentrar-se: não no preenchimento do campo, que já ocorre, mas na "
         "recuperação da informação antes de recorrer ao código de ignorado.")

    titulo(d, "O custo computacional como decisão de projeto", 3)

    p(d, "O terceiro achado é de natureza distinta e refere-se à "
         "sustentabilidade do produto em escala real.")

    p(d, "Na primeira aferição sobre base anual completa, a ferramenta "
         "consumiu duas horas e trinta e dois minutos, dos quais apenas "
         "duzentos e onze segundos correspondiam à análise propriamente dita. "
         "O restante era geração da planilha. Um produto com esse "
         "comportamento é inviável no serviço, ainda que correto em seus "
         "resultados.")

    p(d, "A investigação revelou que a causa não era o volume de dados, mas "
         "uma propriedade da biblioteca de geração de planilhas: a expressão "
         "de indexação de linha recalcula a largura da planilha a cada "
         "chamada, percorrendo todas as células já escritas. O custo cresce "
         "com o quadrado do número de linhas.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Medição do custo de indexação, com quarenta colunas",
        ["Linhas", "Indexação por linha", "Acesso por célula", "Razão"],
        [["2.000", "5,5 s", "0,5 s", "10×"],
         ["4.000", "20,9 s", "1,0 s", "20×"]],
        "Fonte: elaboração própria. O tempo quadruplica quando o número de "
        "linhas dobra, o que caracteriza custo quadrático; o acesso por "
        "célula cresce linearmente.",
        larguras=[3.0, 4.5, 4.0, 3.5])

    p(d, "A substituição da indexação por linha pelo acesso por célula, de "
         "custo constante, reduziu o tempo total de nove mil cento e trinta e "
         "cinco segundos para quatrocentos e vinte e quatro — fator de 21,5 "
         "—, com resultados idênticos em escores, pares, sensibilidade e "
         "valor preditivo positivo. O perfilamento do programa confirmou a "
         "natureza da correção: as onze bilhões e duzentas e trinta e três "
         "milhões de chamadas concentradas naquele ponto foram reduzidas a "
         "zero.")

    p(d, "O achado tem alcance que excede este produto. Rotinas de "
         "qualificação de bases em saúde frequentemente são desenvolvidas e "
         "testadas sobre amostras reduzidas, nas quais defeitos dessa "
         "natureza permanecem invisíveis: com dois mil registros, o custo "
         "adicional era de cinco segundos. A aferição em escala real não é, "
         "portanto, mera verificação de desempenho, mas condição para "
         "identificar defeitos que a escala reduzida oculta.")

    # ------------------------------------------------------------------ #
    titulo(d, "Limitações do produto", 2, nova_pagina=True)

    p(d, "Reconhecem-se as seguintes limitações.")

    lista(d, [
        "O pareamento não constitui solução de interoperabilidade. Opera "
        "sobre dados já produzidos, sem alterar os sistemas nem os padrões "
        "que os regem, e amplia a capacidade analítica sem resolver a "
        "fragmentação que o torna necessário.",
        "A eficácia e a precisão do relacionamento dependem da qualidade das "
        "bases originais. Registros com chaves ausentes ou com múltiplos "
        "erros simultâneos de digitação permanecem não pareados, qualquer que "
        "seja o limiar adotado.",
        "O emprego de bases secundárias comporta a possibilidade de erros "
        "sistemáticos não detectáveis pelo procedimento: um campo "
        "consistentemente mal preenchido em toda a rede notificadora "
        "atravessa todas as verificações de domínio e de coerência.",
        "A verificação manual de falsos-positivos é trabalhosa e, em bases "
        "extensas, só pode ser feita por amostragem. A ferramenta mitiga a "
        "dificuldade ao registrar, para cada par, o escore por campo e as "
        "divergências observadas, mas não a elimina.",
        "Os limiares adotados foram definidos com base na literatura e "
        "verificados contra o gabarito das bases fictícias. Sua adequação a "
        "outros agravos, períodos ou recortes territoriais requer nova "
        "aferição contra amostra revisada por avaliadores independentes.",
        "As projeções supõem a continuidade das condições observadas no "
        "período. Mudanças no processo de notificação, campanhas, surtos ou "
        "alterações normativas rompem essa suposição.",
        "A extração de dados a partir de arquivos em formato PDF é "
        "aproximada, por tratar-se de formato de apresentação e não de "
        "intercâmbio. A ferramenta sinaliza as bases assim obtidas.",
        "A avaliação foi conduzida sobre bases fictícias. Embora construídas "
        "com estrutura equivalente à real e com defeitos deliberadamente "
        "inseridos, não reproduzem necessariamente a distribuição dos "
        "problemas nas bases municipais, cuja aferição depende da etapa de "
        "validação institucional prevista no projeto.",
    ])

    # ------------------------------------------------------------------ #
    titulo(d, "Considerações sobre o produto", 2)

    p(d, "O produto descrito neste capítulo responde à pergunta norteadora do "
         "projeto de intervenção quanto à possibilidade de realizar o "
         "pareamento dos dados do SIM, do SINAN e do SINASC de forma "
         "automatizada e segura. Os resultados da avaliação sustentam a "
         "hipótese de que a automatização reduz o tempo de execução e a "
         "margem de erro, com uma ressalva que convém explicitar.")

    p(d, "A redução da margem de erro não decorre da eliminação do trabalho "
         "humano, mas do seu deslocamento. O esforço da equipe deixa de ser "
         "aplicado à comparação registro a registro — operação em que o erro "
         "humano é frequente e não detectável — e passa a concentrar-se no "
         "conjunto, menor e explicitamente delimitado, dos pares que o "
         "procedimento não pôde decidir. É nesse conjunto que o juízo técnico "
         "tem maior rendimento, e é para ele que a ferramenta foi desenhada "
         "para dirigir a atenção.")

    p(d, "Cabe insistir, por fim, em um ponto de ordem conceitual já "
         "enunciado. O produto não substitui uma agenda de interoperabilidade; "
         "torna-a mais visível. Cada inconsistência que a ferramenta relata, "
         "cada par não recuperado por ausência de identificador comum, "
         "documenta uma consequência concreta da fragmentação entre sistemas "
         "concebidos em momentos distintos e sob concepções distintas quanto "
         "à própria finalidade da informação em saúde. Nesse sentido, o "
         "produto serve a dois propósitos: qualificar as bases hoje "
         "disponíveis e reunir evidência empírica para sustentar, junto às "
         "instâncias competentes, a necessidade de padronização e de "
         "identificação unívoca do usuário no Sistema Único de Saúde.")

    # ------------------------------------------------------------------ #
    titulo(d, "Disponibilidade do código-fonte", 2)

    p(d, "O código-fonte integral da ferramenta, com 10.107 linhas "
         "distribuídas em dezoito módulos, encontra-se disponível no "
         "repositório indicado no apêndice, sob os termos ali especificados. "
         "A documentação de instalação e de uso acompanha o código, assim "
         "como o gerador de bases fictícias, que permite a qualquer "
         "interessado reproduzir a avaliação aqui descrita sem acesso a dados "
         "reais.")

    p(d, "A disponibilização responde à observação de Garcia, Miranda e Sousa "
         "(2022) quanto à escassez de estudos metodológicos que apresentem os "
         "procedimentos necessários à execução da técnica de relacionamento, "
         "e à consequente necessidade de produção e disseminação de modelos "
         "de análise passíveis de adaptação a diferentes realidades e áreas "
         "do conhecimento em saúde.")
