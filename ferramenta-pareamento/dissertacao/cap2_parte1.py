# -*- coding: utf-8 -*-
"""Capítulo sobre a rotina de pareamento SICLOM x SINAN e SIM x SINAN."""

from pathlib import Path

from gerar_capitulo import (citacao, extrair_funcao, extrair_trecho, figura,
                            lista, p, programa, tabela, titulo)

REF = Path(__file__).resolve().parent.parent / "referencia"


def _codigo(modulo: str, nome: str, **kw) -> str:
    """Extrai do diretório da implementação de referência."""
    import ast
    texto = (REF / f"{modulo}.py").read_text(encoding="utf-8")
    arvore = ast.parse(texto)
    linhas = texto.splitlines()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.ClassDef)) and no.name == nome:
            return "\n".join(linhas[no.lineno - 1:no.end_lineno]).rstrip()
    raise ValueError(nome)


def _constantes(modulo: str, inicio: str, fim: str) -> str:
    texto = (REF / f"{modulo}.py").read_text(encoding="utf-8")
    recorte = texto[texto.index(inicio):]
    return recorte[:recorte.index(fim)].rstrip()


def escrever(d, n):
    titulo(d, "Rotina de pareamento e qualificação entre sistemas de "
              "informação em saúde", 1)

    p(d, "Este capítulo descreve a rotina computacional desenvolvida para o "
         "relacionamento entre sistemas de informação em saúde e a verificação "
         "simultânea dos atributos de qualidade das bases relacionadas. "
         "Apresentam-se as premissas que a orientam, os requisitos que lhe "
         "foram impostos, a metodologia adotada em cada etapa, a linguagem e "
         "a estrutura do código, os resultados obtidos em duas aplicações e a "
         "aplicabilidade do procedimento.")

    p(d, "A exposição apoia-se em duas aplicações efetivamente realizadas no "
         "âmbito da Subcoordenadoria de Informação em Saúde (SUIS) da "
         "Secretaria Municipal da Saúde de Salvador, cujos produtos foram "
         "entregues às áreas técnicas da vigilância:")

    lista(d, [
        "o relacionamento entre o Sistema de Controle Logístico de "
        "Medicamentos (SICLOM), na Unidade Dispensadora de Medicamentos (UDM) "
        "Comércio, e o Sistema de Informação de Agravos de Notificação "
        "(SINAN), módulo HEPANET, referente a outubro de 2026, abrangendo 900 "
        "usuários cadastrados e 4.213 notificações de hepatites virais;",
        "o relacionamento entre o Sistema de Informações sobre Mortalidade "
        "(SIM) e o SINAN, referente ao período de janeiro a setembro de 2026, "
        "abrangendo 1.344 óbitos distribuídos em dezesseis agravos sob "
        "vigilância.",
    ])

    p(d, "As listagens de código reproduzidas ao longo do capítulo "
         "correspondem à implementação de referência da rotina, escrita para "
         "tornar o método reproduzível e verificável. Os parâmetros, pontos de "
         "corte e critérios nela expressos são os efetivamente empregados nas "
         "duas aplicações, registrados na aba de metodologia que acompanha "
         "cada produto entregue.")

    # ------------------------------------------------------------------ #
    titulo(d, "Premissas", 2)

    p(d, "O procedimento assenta-se em cinco premissas. Não são escolhas "
         "técnicas arbitrárias: cada uma responde a uma característica do "
         "objeto, e a sua negação conduziria a resultados incorretos ou "
         "inaplicáveis.")

    titulo(d, "O identificador declarado é padrão de referência, não verdade", 3)

    p(d, "O SICLOM dispõe de campos destinados ao registro do número da "
         "notificação do SINAN. Esse número constitui o único vínculo "
         "declarado entre os dois sistemas e é, por isso, o ponto de partida "
         "natural do relacionamento.")

    p(d, "Ele não pode, contudo, ser tomado como verdade. Trata-se de campo "
         "digitado manualmente, sujeito a erro de transcrição, e cuja "
         "correção nenhum dos dois sistemas verifica. A rotina adota, "
         "portanto, uma posição intermediária: utiliza o número declarado "
         "como chave primeira, mas só aceita o vínculo quando o nome do "
         "paciente registrado na notificação é compatível com o do cadastro.")

    p(d, "A pertinência dessa cautela foi confirmada empiricamente. Na "
         "aplicação de outubro de 2026, três usuários apresentavam número de "
         "notificação existente na base, porém pertencente a outro paciente — "
         "situação que a conferência detectou e que deu origem a uma categoria "
         "própria no resultado. Aceitar o número sem conferência teria "
         "produzido três vínculos falsos, indistinguíveis dos verdadeiros.")

    titulo(d, "Ausência de correspondência não equivale a ausência de notificação", 3)

    p(d, "A segunda premissa delimita o que o resultado negativo autoriza a "
         "concluir. Quando a rotina não encontra correspondência para um "
         "usuário, três explicações permanecem abertas: o caso não foi "
         "notificado; foi notificado com dados divergentes a ponto de escapar "
         "à similaridade; ou foi notificado em outro município, fora da base "
         "disponível.")

    p(d, "A distinção tem consequência direta sobre o encaminhamento. Por "
         "isso, os registros sem correspondência não são rotulados como "
         "subnotificação, mas encaminhados à busca ativa — e a rotina fornece, "
         "para orientar essa busca, elementos que permitem priorizá-la, como "
         "a data de cadastro anterior à janela temporal da base de notificações "
         "e a existência de dispensação recente de medicamento.")

    titulo(d, "O critério de qualidade é do sistema, não do analista", 3)

    p(d, "A terceira premissa governa a verificação dos atributos de "
         "qualidade. Não se arbitra quais campos são obrigatórios nem o que "
         "constitui preenchimento válido: adota-se a classificação do "
         "Dicionário de Dados do próprio sistema — no caso, o Dicionário de "
         "Dados do SINAN NET, versão 5.0, para hepatites virais — e as "
         "instruções de preenchimento do instrumento.")

    p(d, "A opção tem duas consequências práticas. A primeira é que o "
         "resultado é defensável perante a área técnica: a exigência não parte "
         "do setor de informação, mas da norma que rege o sistema. A segunda é "
         "que dispensa a renegociação do critério a cada rodada, o que em "
         "rotinas de qualificação costuma consumir mais tempo do que a própria "
         "análise.")

    titulo(d, "Duplicidade não é erro até que se demonstre", 3)

    p(d, "A quarta premissa reconhece que a repetição de um registro pode ser "
         "legítima. Um mesmo paciente pode ser notificado duas vezes por "
         "episódios distintos, e a exclusão indiscriminada de pares "
         "semelhantes apagaria informação verdadeira.")

    p(d, "A rotina, por isso, não classifica duplicidades apenas pela "
         "similaridade dos dados de identificação, mas também pelo intervalo "
         "entre as datas de notificação, que é o elemento capaz de distinguir "
         "o erro operacional da renotificação. Nenhum par é apresentado como "
         "exclusão recomendada: todos são apresentados como conferência.")

    titulo(d, "O produto dirige-se à ação, não ao diagnóstico", 3)

    p(d, "A quinta premissa diz respeito à finalidade. O produto não se "
         "destina a descrever o estado das bases, mas a provocar a sua "
         "correção e a investigação dos casos. Disso decorre que cada achado "
         "precisa chegar à área técnica acompanhado de quatro elementos: o que "
         "foi encontrado, por que constitui problema, o que fazer a respeito e "
         "quem deve fazê-lo.")

    p(d, "Essa premissa determinou a estrutura das planilhas entregues, "
         "descrita adiante, e explica a presença de colunas que um relatório "
         "meramente descritivo dispensaria.")

    # ------------------------------------------------------------------ #
    titulo(d, "Requisitos", 2, nova_pagina=True)

    titulo(d, "Requisitos funcionais", 3)

    lista(d, [
        "relacionar duas bases de sistemas distintos na ausência de "
        "identificador único comum de preenchimento confiável;",
        "utilizar, quando disponível, o identificador declarado por um dos "
        "sistemas, submetendo-o a conferência;",
        "classificar cada registro em categorias que distingam o vínculo "
        "confirmado, a correspondência provável, a divergência e a ausência "
        "de correspondência;",
        "verificar os atributos de qualidade de ambas as bases segundo o "
        "dicionário de dados do sistema de origem;",
        "identificar duplicidades em cada base, distinguindo o lançamento "
        "repetido da renotificação legítima;",
        "entregar, para cada achado, descrição, fundamentação, recomendação de "
        "correção, responsável sugerido e prioridade;",
        "registrar os critérios, parâmetros e limitações no próprio produto, "
        "de modo que a sua leitura não dependa de documento externo.",
    ])

    titulo(d, "Requisitos não funcionais", 3)

    p(d, "Três requisitos não funcionais condicionaram o desenho.")

    p(d, "O primeiro é a proteção dos dados. Os registros tratados são dados "
         "pessoais sensíveis, nos termos do art. 5º, II, da Lei nº 13.709, de "
         "2018, e o tratamento fundamenta-se na hipótese de execução de "
         "políticas públicas por órgão da administração pública, restrita à "
         "finalidade declarada. O processamento é integralmente local, sem "
         "transmissão a serviços externos, e os produtos entregues trazem "
         "advertência expressa quanto ao caráter restrito dos dados nominais.")

    p(d, "O segundo é a operabilidade pelas áreas técnicas. O produto final é "
         "uma planilha eletrônica, e não um sistema: o formato foi escolhido "
         "porque é o instrumento que as equipes de vigilância já dominam e "
         "porque permite que a resposta da área técnica seja registrada no "
         "próprio arquivo, em colunas reservadas para esse fim, sem "
         "necessidade de ferramenta adicional.")

    p(d, "O terceiro é a auditabilidade. Cada número apresentado no resumo "
         "executivo é calculado por fórmula a partir das abas de detalhe, e "
         "não digitado. A consequência é que qualquer indicador pode ser "
         "rastreado até os registros que o compõem, e que a correção de um "
         "registro se propaga ao resumo sem intervenção manual.")
