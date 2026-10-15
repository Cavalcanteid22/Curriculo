# -*- coding: utf-8 -*-
"""Seções 1 a 3 do capítulo: caracterização, arquitetura e percurso (início)."""

from gerar_capitulo import (citacao, extrair_atribuicao, extrair_funcao,
                            extrair_trecho, figura, lista, p, programa,
                            tabela, titulo)


def escrever(d, n):
    """n é um dicionário com os contadores de programa, tabela e figura."""

    # ------------------------------------------------------------------ #
    titulo(d, "Produto técnico: a ferramenta ELO-SIS", 1)

    p(d, "Este capítulo descreve a construção do produto técnico previsto no "
         "projeto de intervenção: uma rotina computacional destinada ao "
         "relacionamento das bases do Sistema de Informações sobre Mortalidade "
         "(SIM), do Sistema de Informação de Agravos de Notificação (SINAN) e "
         "do Sistema de Informações sobre Nascidos Vivos (SINASC), no âmbito "
         "da Subcoordenadoria de Informação em Saúde (SUIS) da Secretaria "
         "Municipal da Saúde de Salvador. A ferramenta recebeu a denominação "
         "ELO-SIS.")

    p(d, "A exposição segue a ordem da construção. Descrevem-se, "
         "sucessivamente, a caracterização do produto e os requisitos dele "
         "derivados; as decisões de arquitetura, com a justificativa da "
         "linguagem de programação e do modelo de execução adotados; o "
         "percurso de implementação de cada etapa do fluxo, acompanhado dos "
         "trechos de código correspondentes; os produtos que a ferramenta "
         "entrega; a estratégia de avaliação; e os achados metodológicos que "
         "emergiram da própria implementação. Encerra-se com as limitações "
         "reconhecidas.")

    p(d, "As listagens de código reproduzidas ao longo do capítulo são "
         "extraídas diretamente dos arquivos-fonte do programa, e não "
         "transcritas manualmente. Essa decisão elimina a possibilidade de "
         "divergência entre o que o texto afirma e o que o produto executa — "
         "divergência que, em trabalhos que documentam artefatos de software, "
         "é frequente e compromete a verificabilidade.")

    # ------------------------------------------------------------------ #
    titulo(d, "Caracterização do produto", 2)

    p(d, "O ELO-SIS é um programa de computador de uso local, destinado a "
         "equipes de vigilância em saúde. Recebe as bases exportadas pelos "
         "sistemas, avalia a qualidade de cada uma, identifica e sinaliza "
         "inconsistências, harmoniza as variáveis, executa o relacionamento "
         "entre as bases e entrega dois produtos: uma planilha de trabalho e "
         "um relatório analítico-descritivo.")

    p(d, "A concepção do produto partiu de uma distinção que orienta todo o "
         "projeto e que convém reafirmar aqui. Conforme a Organização "
         "Panamericana da Saúde (2016), a interoperabilidade depende do êxito "
         "simultâneo dos níveis técnico, sintático e semântico, envolvendo "
         "decisões de política, padronização e regulação que extrapolam a "
         "competência da gestão setorial municipal. O relacionamento de bases, "
         "por sua vez, opera a posteriori, sobre dados já produzidos, sem "
         "alterar os sistemas nem os padrões que os regem. O produto aqui "
         "descrito situa-se nesta segunda ordem: amplia a capacidade "
         "analítica sem resolver a fragmentação que o torna necessário.")

    titulo(d, "Requisitos", 3)

    p(d, "Os requisitos do produto decorrem do problema descrito na "
         "introdução e das condições concretas de trabalho da SUIS. Foram "
         "estabelecidos sete, a saber:")

    lista(d, [
        "não permitir que dados identificáveis deixem a estação de trabalho "
        "institucional, em qualquer circunstância;",
        "ser operável por profissionais de vigilância sem formação em "
        "informática;",
        "aceitar bases nos formatos efetivamente produzidos pelos sistemas — "
        "DBF, CSV, planilhas eletrônicas e, quando for o caso, PDF;",
        "processar bases anuais completas, da ordem de dezenas de milhares de "
        "registros por sistema, em estações de trabalho comuns;",
        "avaliar a qualidade das bases segundo atributos reconhecidos na "
        "literatura, e não segundo critérios ad hoc;",
        "executar o relacionamento em dois estágios, determinístico e "
        "probabilístico, conforme a metodologia definida no projeto;",
        "entregar produtos que sirvam simultaneamente à correção das bases "
        "nativas e à investigação dos casos pelas áreas técnicas.",
    ], numerada=True)

    p(d, "O primeiro requisito merece destaque por sua natureza. Não se trata "
         "de preferência de projeto, mas de condição legal: os dados tratados "
         "são pessoais sensíveis, nos termos do art. 5º, II, da Lei nº 13.709, "
         "de 2018, e seu tratamento fundamenta-se na hipótese de execução de "
         "políticas públicas por órgão da administração pública, restrita à "
         "finalidade declarada. Qualquer transmissão para serviço externo "
         "extrapolaria essa finalidade.")

    # ------------------------------------------------------------------ #
    titulo(d, "Decisões de arquitetura", 2, nova_pagina=True)

    titulo(d, "Linguagem de programação e ambiente de execução", 3)

    p(d, "Adotou-se a linguagem Python, na versão 3.9 ou superior. A escolha "
         "considerou quatro fatores.")

    p(d, "O primeiro é a adequação ao domínio. Python dispõe de bibliotecas "
         "maduras para manipulação de dados tabulares e produção de "
         "documentos, e é a linguagem em que se encontra a maior parte do "
         "instrumental de análise de dados em saúde pública. Garcia, Miranda e "
         "Sousa (2022), referência metodológica central deste trabalho, "
         "empregam o software R; a opção por Python não decorre de juízo sobre "
         "a linguagem, mas do segundo fator.")

    p(d, "O segundo fator é a condição de instalação em estações "
         "institucionais. A ferramenta precisa executar em computadores da "
         "rede municipal, frequentemente sem permissão para instalação de "
         "componentes adicionais e sem acesso irrestrito à internet. Python "
         "acompanha a instalação padrão de sistemas operacionais correntes e, "
         "sobretudo, traz em sua biblioteca padrão a interface gráfica "
         "(tkinter) empregada no produto, o que dispensa componentes externos "
         "para a parte do programa com que o usuário interage.")

    p(d, "O terceiro fator é a legibilidade do código. Um produto técnico de "
         "mestrado profissional destina-se a ser mantido pela própria equipe "
         "do serviço após a conclusão do trabalho. Código legível é, nesse "
         "contexto, requisito de sustentabilidade do produto, e não virtude "
         "estética. Por essa razão, todo o programa foi escrito com "
         "identificadores em português e comentários que explicitam as "
         "decisões, e não apenas descrevem as operações.")

    p(d, "O quarto fator é a possibilidade de reduzir dependências externas. "
         "Componentes críticos do produto — o leitor de arquivos DBF e as "
         "métricas de similaridade — foram implementados em Python puro, sem "
         "recurso a bibliotecas de terceiros, precisamente para que a "
         "ferramenta execute onde a instalação de pacotes não é possível.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Bibliotecas empregadas e respectiva finalidade",
        ["Biblioteca", "Finalidade", "Caráter"],
        [["pandas", "Manipulação de dados tabulares", "Necessária"],
         ["numpy", "Cálculo numérico e regressão", "Necessária"],
         ["openpyxl", "Geração da planilha de resultados", "Necessária"],
         ["python-docx", "Geração do relatório analítico", "Necessária"],
         ["matplotlib", "Produção dos gráficos", "Necessária"],
         ["tkinter", "Interface gráfica", "Biblioteca padrão"],
         ["pdfplumber", "Extração de tabelas de PDF", "Opcional"],
         ["xlrd", "Leitura de planilhas no formato .xls", "Opcional"]],
        "Fonte: elaboração própria.",
        larguras=[3.5, 8.0, 3.5])

    p(d, "As bibliotecas assinaladas como opcionais ampliam a capacidade da "
         "ferramenta sem serem condição de funcionamento: sua ausência reduz "
         "o alcance da leitura de determinados formatos, mas não impede a "
         "execução. Essa distinção foi implementada de modo defensivo, "
         "conforme se descreve na seção sobre leitura de arquivos.")

    titulo(d, "O processamento local como requisito de projeto", 3)

    p(d, "O requisito de não permitir a saída de dados foi implementado de "
         "forma ativa, e não meramente declaratória. A ferramenta opera no que "
         "se denominou modo cofre: ao iniciar, substitui em tempo de execução "
         "as primitivas de conexão do interpretador Python, de modo que "
         "qualquer tentativa de conexão externa — partida de qualquer "
         "componente do programa, inclusive de bibliotecas de terceiros — "
         "falhe imediatamente e fique registrada na trilha de auditoria.")

    p(d, "A distinção entre garantia declaratória e garantia técnica é "
         "relevante. Afirmar em documentação que um programa não transmite "
         "dados é uma promessa cuja verificação exige auditoria do código "
         "inteiro, inclusive das dependências. Impedir tecnicamente a "
         "transmissão é uma propriedade verificável por teste: basta tentar "
         "uma conexão e observar a falha. O Programa 1 apresenta o mecanismo.")

    n["programa"] = programa(
        d, n["programa"],
        "Implementação do modo cofre",
        extrair_funcao("seguranca", "ativar_modo_cofre"),
        "elosis/seguranca.py")

    p(d, "O bloqueio alcança também a resolução de nomes. Essa extensão não "
         "era evidente no desenho inicial e foi incorporada após verificação: "
         "uma consulta ao serviço de nomes de domínio constitui, por si só, um "
         "canal de saída, uma vez que o nome consultado deixa a estação e pode "
         "carregar dados codificados no subdomínio. O tráfego de retorno "
         "(loopback) permanece liberado, por ser interno à máquina.")

    p(d, "A verificação do mecanismo foi conduzida por tentativa direta de "
         "conexão, com registro do resultado, conforme a Tabela seguinte.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Verificação do modo cofre",
        ["Primitiva testada", "Resultado"],
        [["socket.create_connection", "Bloqueada"],
         ["urllib.request.urlopen", "Bloqueada"],
         ["socket.getaddrinfo", "Bloqueada"],
         ["socket.gethostbyname", "Bloqueada"],
         ["socket.gethostbyname_ex", "Bloqueada"],
         ["socket.gethostbyaddr", "Bloqueada"],
         ["Resolução de endereço local (127.0.0.1)", "Permitida"]],
        "Fonte: elaboração própria. Cada tentativa é registrada na trilha de "
        "auditoria da execução.",
        larguras=[8.0, 7.0])

    p(d, "Compõem ainda a camada de proteção a pseudonimização opcional dos "
         "identificadores diretos, por função de resumo criptográfico com "
         "chave local de permissão restrita, e a identificação de cada arquivo "
         "processado pelo seu resumo SHA-256. Este último recurso permite "
         "demonstrar, em auditoria posterior, exatamente qual versão de cada "
         "base originou cada produto, sem que seja necessário guardar cópia "
         "dos dados — atendendo simultaneamente à rastreabilidade exigida pela "
         "governança da informação em saúde (GHAFFARI HESHAJIN et al., 2024) e "
         "ao princípio da minimização previsto na legislação.")

    titulo(d, "Organização em módulos", 3)

    p(d, "O programa foi organizado em dezoito módulos, cada um responsável "
         "por uma etapa do fluxo ou por um serviço transversal. A separação "
         "obedece a um critério: cada módulo deve poder ser lido, testado e "
         "modificado isoladamente, sem que seja necessário compreender os "
         "demais. Essa propriedade foi decisiva na fase de avaliação, quando "
         "defeitos puderam ser localizados por eliminação.")

    n["tabela"] = tabela(
        d, n["tabela"],
        "Módulos do programa e respectivas responsabilidades",
        ["Módulo", "Responsabilidade", "Linhas"],
        [["seguranca.py", "Modo cofre, pseudonimização e trilha de auditoria", "286"],
         ["dbf.py", "Leitor de arquivos DBF em Python puro", "340"],
         ["leitura.py", "Leitura unificada de CSV, DBF, Excel e PDF", "322"],
         ["normalizacao.py", "Pré-processamento das variáveis", "406"],
         ["similaridade.py", "Métricas de similaridade e código fonético", "283"],
         ["perfis.py", "Perfis do SIM, SINAN e SINASC", "564"],
         ["qualidade.py", "Atributos de qualidade e classificação", "714"],
         ["duplicidades.py", "Detecção de duplicidades intrabase", "326"],
         ["harmonizacao.py", "Harmonização das variáveis", "270"],
         ["pareamento.py", "Relacionamento determinístico e probabilístico", "555"],
         ["indicadores.py", "Desempenho, estatística e epidemiologia", "629"],
         ["graficos.py", "Produção dos gráficos", "559"],
         ["planilha.py", "Geração da planilha de resultados", "1.238"],
         ["relatorio.py", "Geração do relatório analítico", "1.707"],
         ["pipeline.py", "Orquestração do fluxo", "425"],
         ["dados_ficticios.py", "Gerador de bases fictícias e gabarito", "606"],
         ["gui.py", "Interface gráfica", "649"],
         ["cli.py", "Interface de linha de comando", "259"]],
        "Fonte: elaboração própria. Total de 10.107 linhas, incluídos "
        "comentários e documentação interna.",
        larguras=[4.0, 8.5, 2.5], corpo=8)
