# -*- coding: utf-8 -*-
"""
Perfis dos sistemas de informação em saúde: SIM, SINAN e SINASC (ELO-SIS).

Cada perfil declara (a) o mapeamento entre os nomes de campo do sistema e as
variáveis canônicas da ferramenta, (b) os campos de preenchimento obrigatório
segundo as normativas vigentes, (c) os domínios de valores admitidos e (d) os
códigos convencionados para "ignorado".

Esse conjunto constitui a camada de harmonização semântica no sentido dado por
Schmidt et al. (2020): variáveis homônimas em sistemas distintos passam a ser
comparáveis, e variáveis heterônimas que designam o mesmo atributo passam a
ser reconhecidas como tal.

Base normativa: Portaria de Consolidação GM/MS nº 4/2017 (Anexos V e VI);
Portaria GM/MS nº 1.399/1999; Lei nº 6.015/1973; Portaria GM/MS nº 116/2009
(SIM); Portaria GM/MS nº 1.119/2008 e nº 72/2010 (SIM/SINASC — vigilância do
óbito infantil, fetal e materno); Instrução Normativa SVS nº 2/2005 (SINAN);
Portaria GM/MS nº 264/2020 (Lista Nacional de Notificação Compulsória).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Variáveis canônicas
# --------------------------------------------------------------------------- #

NOME = "NOME"
NOME_MAE = "NOME_MAE"
DATA_NASCIMENTO = "DATA_NASCIMENTO"
SEXO = "SEXO"
CPF = "CPF"
CNS = "CNS"
MUNICIPIO_RESIDENCIA = "MUNICIPIO_RESIDENCIA"
DATA_EVENTO = "DATA_EVENTO"
DATA_REGISTRO = "DATA_REGISTRO"
IDADE = "IDADE"
RACA_COR = "RACA_COR"
LOGRADOURO = "LOGRADOURO"
BAIRRO = "BAIRRO"
CEP = "CEP"
NUMERO_REGISTRO = "NUMERO_REGISTRO"
CAUSA_BASICA = "CAUSA_BASICA"
AGRAVO = "AGRAVO"
ESTABELECIMENTO = "ESTABELECIMENTO"
ESCOLARIDADE = "ESCOLARIDADE"
NOME_PAI = "NOME_PAI"
PESO_NASCIMENTO = "PESO_NASCIMENTO"
EVOLUCAO = "EVOLUCAO"
CLASSIFICACAO_FINAL = "CLASSIFICACAO_FINAL"
DATA_OBITO = "DATA_OBITO"
DATA_ENCERRAMENTO = "DATA_ENCERRAMENTO"
DATA_SINTOMAS = "DATA_SINTOMAS"

ROTULOS_CANONICOS = {
    NOME: "Nome do usuário",
    NOME_MAE: "Nome da mãe",
    NOME_PAI: "Nome do pai",
    DATA_NASCIMENTO: "Data de nascimento",
    SEXO: "Sexo",
    CPF: "CPF",
    CNS: "Cartão Nacional de Saúde",
    MUNICIPIO_RESIDENCIA: "Município de residência (IBGE)",
    DATA_EVENTO: "Data do evento (óbito, nascimento ou notificação)",
    DATA_REGISTRO: "Data de digitação/cadastro no sistema",
    IDADE: "Idade",
    RACA_COR: "Raça/cor",
    LOGRADOURO: "Logradouro",
    BAIRRO: "Bairro",
    CEP: "CEP",
    NUMERO_REGISTRO: "Número do registro no sistema",
    CAUSA_BASICA: "Causa básica (CID-10)",
    AGRAVO: "Agravo/doença notificada (CID-10)",
    ESTABELECIMENTO: "Estabelecimento (CNES)",
    ESCOLARIDADE: "Escolaridade",
    PESO_NASCIMENTO: "Peso ao nascer (g)",
    EVOLUCAO: "Evolução do caso",
    CLASSIFICACAO_FINAL: "Classificação final",
    DATA_OBITO: "Data do óbito",
    DATA_ENCERRAMENTO: "Data de encerramento",
    DATA_SINTOMAS: "Data dos primeiros sintomas",
}

# Natureza de cada variável canônica — orienta normalização e validação.
NATUREZA = {
    NOME: "nome", NOME_MAE: "nome", NOME_PAI: "nome",
    DATA_NASCIMENTO: "data", DATA_EVENTO: "data", DATA_REGISTRO: "data",
    DATA_OBITO: "data", DATA_ENCERRAMENTO: "data", DATA_SINTOMAS: "data",
    SEXO: "categoria", RACA_COR: "categoria", ESCOLARIDADE: "categoria",
    EVOLUCAO: "categoria", CLASSIFICACAO_FINAL: "categoria",
    CPF: "cpf", CNS: "cns", CEP: "cep",
    MUNICIPIO_RESIDENCIA: "ibge", ESTABELECIMENTO: "cnes",
    CAUSA_BASICA: "cid", AGRAVO: "cid",
    IDADE: "numero", PESO_NASCIMENTO: "numero",
    NUMERO_REGISTRO: "codigo", LOGRADOURO: "texto", BAIRRO: "texto",
}

# --------------------------------------------------------------------------- #
# Domínios de valores
# --------------------------------------------------------------------------- #

DOMINIO_SEXO = {
    "SIM": {"1": "Masculino", "2": "Feminino", "0": "Ignorado", "9": "Ignorado"},
    "SINASC": {"1": "Masculino", "2": "Feminino", "0": "Ignorado", "9": "Ignorado"},
    "SINAN": {"M": "Masculino", "F": "Feminino", "I": "Ignorado"},
}

DOMINIO_RACA_COR = {
    "1": "Branca", "2": "Preta", "3": "Amarela", "4": "Parda",
    "5": "Indígena", "9": "Ignorado",
}

DOMINIO_EVOLUCAO_SINAN = {
    "1": "Cura", "2": "Óbito pelo agravo notificado",
    "3": "Óbito por outra causa", "4": "Transferência",
    "9": "Ignorado",
}

DOMINIO_CLASSI_FIN_SINAN = {
    "1": "Confirmado", "2": "Descartado", "3": "Provável",
    "4": "Confirmado laboratorial", "5": "Confirmado clínico-epidemiológico",
    "8": "Inconclusivo", "9": "Ignorado",
}

DOMINIO_ESCOLARIDADE = {
    "0": "Sem escolaridade", "1": "Fundamental I incompleto",
    "2": "Fundamental I completo", "3": "Fundamental II incompleto",
    "4": "Fundamental II completo", "5": "Médio incompleto",
    "6": "Médio completo", "7": "Superior incompleto",
    "8": "Superior completo", "9": "Ignorado", "10": "Não se aplica",
}

# Códigos que os sistemas convencionam para "ignorado" ou "não informado".
CODIGOS_IGNORADO = {"9", "99", "999", "9999", "99999", "0", "00",
                    "I", "IGN", "IGNORADO", "NAO INFORMADO", "NÃO INFORMADO",
                    "N/I", "NI", "SEM INFORMACAO", "SEM INFORMAÇÃO", "-",
                    "NAO SE APLICA", "NÃO SE APLICA", "88", "888"}

# Preenchimentos inválidos frequentes em campos nominais.
NOMES_INVALIDOS = {
    "RN", "RN DE", "NATIMORTO", "IGNORADO", "IGN", "NAO INFORMADO",
    "DESCONHECIDO", "DESCONHECIDA", "NAO SABE", "SEM NOME", "XXX", "XXXX",
    "TESTE", "NN", "N N", "FULANO", "FULANA", "SEM INFORMACAO", "A IDENTIFICAR",
    "NAO IDENTIFICADO", "NAO IDENTIFICADA", "PACIENTE", "INDIGENTE",
}

CODIGO_IBGE_SALVADOR = "292740"

# --------------------------------------------------------------------------- #
# Estrutura do perfil
# --------------------------------------------------------------------------- #

@dataclass
class PerfilSistema:
    sigla: str
    nome_extenso: str
    descricao: str
    instrumento: str
    base_normativa: str
    mapeamento: dict[str, list[str]]
    obrigatorios: dict[str, str]
    recomendados: dict[str, str] = field(default_factory=dict)
    dominios: dict[str, dict[str, str]] = field(default_factory=dict)
    prazo_registro_dias: int = 60
    assinaturas: list[str] = field(default_factory=list)

    def campo_de(self, canonica: str, colunas: list[str]) -> str | None:
        """Localiza, entre as colunas da base, o campo que representa a variável."""
        disponiveis = {c.upper().strip(): c for c in colunas}
        for candidato in self.mapeamento.get(canonica, []):
            if candidato.upper() in disponiveis:
                return disponiveis[candidato.upper()]
        return None

    def mapear(self, colunas: list[str]) -> dict[str, str]:
        """Devolve {variável canônica: coluna original} para o que existir."""
        return {c: campo for c in self.mapeamento
                if (campo := self.campo_de(c, colunas))}

    def pontuar(self, colunas: list[str]) -> int:
        """Quantas assinaturas do sistema aparecem nas colunas da base."""
        conjunto = {c.upper().strip() for c in colunas}
        return sum(1 for assinatura in self.assinaturas if assinatura in conjunto)


# --------------------------------------------------------------------------- #
# SIM — Sistema de Informações sobre Mortalidade
# --------------------------------------------------------------------------- #

PERFIL_SIM = PerfilSistema(
    sigla="SIM",
    nome_extenso="Sistema de Informações sobre Mortalidade",
    descricao=(
        "Registra os óbitos ocorridos no território, tendo como instrumento de "
        "coleta a Declaração de Óbito (DO). Implantado em 1975, é a fonte "
        "oficial para o cálculo de indicadores de mortalidade."
    ),
    instrumento="Declaração de Óbito (DO)",
    base_normativa=(
        "Portaria de Consolidação GM/MS nº 4/2017, Anexo V; Portaria GM/MS "
        "nº 116/2009; Lei nº 6.015/1973, art. 77 e seguintes."
    ),
    mapeamento={
        NOME: ["NOME", "NOME_FALEC", "NM_PACIENT", "NOMEPAC", "NOME_DO",
               "NOMEFALECIDO", "NM_FALECIDO", "NOME_PACIENTE"],
        NOME_MAE: ["NOMEMAE", "NOME_MAE", "NM_MAE", "NM_MAE_PAC", "NOME_MAE_DO"],
        NOME_PAI: ["NOMEPAI", "NOME_PAI", "NM_PAI"],
        DATA_NASCIMENTO: ["DTNASC", "DT_NASC", "DATANASC", "DATA_NASC",
                          "DT_NASCIMENTO"],
        DATA_EVENTO: ["DTOBITO", "DT_OBITO", "DATAOBITO", "DATA_OBITO"],
        DATA_OBITO: ["DTOBITO", "DT_OBITO", "DATAOBITO", "DATA_OBITO"],
        DATA_REGISTRO: ["DTCADASTRO", "DT_CADASTRO", "DTRECEBIM", "DT_DIGITA",
                        "DATACADASTRO"],
        SEXO: ["SEXO", "CS_SEXO", "DS_SEXO"],
        CPF: ["CPF", "NU_CPF", "CPF_FALEC", "CPFPACIENTE"],
        CNS: ["CNS", "NUMSUS", "NU_CNS", "ID_CNS_SUS", "CARTAOSUS"],
        MUNICIPIO_RESIDENCIA: ["CODMUNRES", "COD_MUN_RES", "MUNRES",
                               "ID_MN_RESI", "CODMUNICIPIORES"],
        IDADE: ["IDADE", "NU_IDADE", "IDADE_ANOS"],
        RACA_COR: ["RACACOR", "RACA_COR", "CS_RACA", "RACA"],
        ESCOLARIDADE: ["ESC", "ESC2010", "ESCOLARIDADE", "CS_ESCOL_N"],
        LOGRADOURO: ["ENDERECO", "LOGRADOURO", "NM_LOGRADO", "END_RES"],
        BAIRRO: ["BAIRRO", "NM_BAIRRO", "BAIRRO_RES"],
        CEP: ["CEP", "NU_CEP", "CEP_RES"],
        NUMERO_REGISTRO: ["NUMERODO", "NUMERO_DO", "NU_DO", "N_DO", "NUMDO"],
        CAUSA_BASICA: ["CAUSABAS", "CAUSA_BAS", "CAUSABAS_O", "CID_CAUSABAS"],
        ESTABELECIMENTO: ["CODESTAB", "COD_ESTAB", "CNES", "CO_CNES"],
    },
    obrigatorios={
        NOME: "Bloco I da DO — identificação do falecido (campo 6).",
        DATA_NASCIMENTO: "Bloco I da DO — campo 8.",
        SEXO: "Bloco I da DO — campo 10.",
        DATA_EVENTO: "Bloco I da DO — data do óbito (campo 4).",
        MUNICIPIO_RESIDENCIA: "Bloco III da DO — residência (campo 25).",
        CAUSA_BASICA: "Bloco V da DO — condições e causas do óbito (campo 49).",
        NUMERO_REGISTRO: "Numeração sequencial da DO — chave do sistema.",
    },
    recomendados={
        NOME_MAE: "Campo 7 da DO. Essencial ao linkage e à vigilância do óbito "
                  "infantil e materno (Portaria GM/MS nº 72/2010).",
        CPF: "Identificador com maior poder discriminante para pareamento.",
        CNS: "Identificador nacional do usuário do SUS.",
        RACA_COR: "Campo 11 da DO. Obrigatório para o quesito raça/cor "
                  "(Portaria GM/MS nº 344/2017).",
        DATA_REGISTRO: "Permite aferir o atributo de oportunidade.",
    },
    dominios={SEXO: DOMINIO_SEXO["SIM"], RACA_COR: DOMINIO_RACA_COR,
              ESCOLARIDADE: DOMINIO_ESCOLARIDADE},
    prazo_registro_dias=30,
    assinaturas=["NUMERODO", "CAUSABAS", "DTOBITO", "LINHAA", "CIRCOBITO",
                 "TIPOBITO", "OBITOGRAV", "ASSISTMED"],
)

# --------------------------------------------------------------------------- #
# SINASC — Sistema de Informações sobre Nascidos Vivos
# --------------------------------------------------------------------------- #

PERFIL_SINASC = PerfilSistema(
    sigla="SINASC",
    nome_extenso="Sistema de Informações sobre Nascidos Vivos",
    descricao=(
        "Registra os nascidos vivos, tendo como instrumento a Declaração de "
        "Nascido Vivo (DN). Implantado em 1990, fornece o denominador de "
        "indicadores de saúde materno-infantil."
    ),
    instrumento="Declaração de Nascido Vivo (DN)",
    base_normativa=(
        "Portaria de Consolidação GM/MS nº 4/2017, Anexo VI; Portaria GM/MS "
        "nº 1.119/2008; Lei nº 12.662/2012."
    ),
    mapeamento={
        NOME: ["NOMERN", "NOME_RN", "NOME", "NM_RECEM", "NOMECRIANCA",
               "NM_PACIENT", "NOME_CRIANCA"],
        NOME_MAE: ["NOMEMAE", "NOME_MAE", "NM_MAE", "NM_MAE_PAC", "NOMEMAE_DN"],
        NOME_PAI: ["NOMEPAI", "NOME_PAI", "NM_PAI"],
        DATA_NASCIMENTO: ["DTNASC", "DT_NASC", "DATANASC", "DATA_NASC"],
        DATA_EVENTO: ["DTNASC", "DT_NASC", "DATANASC", "DATA_NASC"],
        DATA_REGISTRO: ["DTCADASTRO", "DT_CADASTRO", "DTRECEBIM", "DT_DIGITA"],
        SEXO: ["SEXO", "CS_SEXO"],
        CPF: ["CPF", "CPFMAE", "CPF_MAE", "NU_CPF"],
        CNS: ["CNS", "NUMSUSMAE", "NUMSUS", "ID_CNS_SUS"],
        MUNICIPIO_RESIDENCIA: ["CODMUNRES", "COD_MUN_RES", "MUNRES", "ID_MN_RESI"],
        RACA_COR: ["RACACOR", "RACACORMAE", "CS_RACA", "RACA_COR"],
        ESCOLARIDADE: ["ESCMAE", "ESCMAE2010", "ESCOLARIDADE", "CS_ESCOL_N"],
        LOGRADOURO: ["ENDERECO", "LOGRADOURO", "NM_LOGRADO"],
        BAIRRO: ["BAIRRO", "NM_BAIRRO"],
        CEP: ["CEP", "NU_CEP", "CEPMAE"],
        NUMERO_REGISTRO: ["NUMERODN", "NUMERO_DN", "NU_DN", "N_DN", "NUMDN"],
        ESTABELECIMENTO: ["CODESTAB", "COD_ESTAB", "CNES", "CO_CNES"],
        PESO_NASCIMENTO: ["PESO", "PESO_NASC", "PESONASC"],
    },
    obrigatorios={
        NOME_MAE: "Bloco II da DN — identificação da mãe (campo 9).",
        DATA_EVENTO: "Bloco IV da DN — data do nascimento (campo 24).",
        SEXO: "Bloco IV da DN — campo 27.",
        MUNICIPIO_RESIDENCIA: "Bloco II da DN — residência da mãe (campo 18).",
        NUMERO_REGISTRO: "Numeração sequencial da DN — chave do sistema.",
        PESO_NASCIMENTO: "Bloco IV da DN — peso ao nascer (campo 31).",
    },
    recomendados={
        NOME: "Nome do recém-nascido. Frequentemente ausente na DN emitida na "
              "maternidade; sua ausência compromete o pareamento com o SIM "
              "em óbitos infantis.",
        DATA_NASCIMENTO: "Coincide com a data do evento no SINASC.",
        CPF: "CPF da mãe — eleva o poder discriminante do pareamento.",
        RACA_COR: "Campo 13 da DN (Portaria GM/MS nº 344/2017).",
    },
    dominios={SEXO: DOMINIO_SEXO["SINASC"], RACA_COR: DOMINIO_RACA_COR,
              ESCOLARIDADE: DOMINIO_ESCOLARIDADE},
    prazo_registro_dias=15,
    assinaturas=["NUMERODN", "APGAR1", "APGAR5", "IDADEMAE", "CONSULTAS",
                 "GESTACAO", "LOCNASC", "QTDFILVIVO", "PARTO"],
)

# --------------------------------------------------------------------------- #
# SINAN — Sistema de Informação de Agravos de Notificação
# --------------------------------------------------------------------------- #

PERFIL_SINAN = PerfilSistema(
    sigla="SINAN",
    nome_extenso="Sistema de Informação de Agravos de Notificação",
    descricao=(
        "Registra os casos de doenças e agravos de notificação compulsória, "
        "por meio da Ficha Individual de Notificação (FIN) e da Ficha de "
        "Investigação. Sustenta a detecção de surtos e o monitoramento de "
        "agravos prioritários."
    ),
    instrumento="Ficha Individual de Notificação (FIN)",
    base_normativa=(
        "Portaria de Consolidação GM/MS nº 4/2017, Anexo V, Capítulo I; "
        "Portaria GM/MS nº 264/2020; Instrução Normativa SVS nº 2/2005."
    ),
    mapeamento={
        NOME: ["NM_PACIENT", "NOME", "NOMEPAC", "NM_PACIENTE", "NOME_PACIENTE"],
        NOME_MAE: ["NM_MAE_PAC", "NOMEMAE", "NOME_MAE", "NM_MAE"],
        DATA_NASCIMENTO: ["DT_NASC", "DTNASC", "DATANASC", "DATA_NASC"],
        DATA_EVENTO: ["DT_NOTIFIC", "DTNOTIFIC", "DATA_NOTIF", "DT_NOTIF"],
        DATA_SINTOMAS: ["DT_SIN_PRI", "DTSINPRI", "DATA_SINTOMAS"],
        DATA_REGISTRO: ["DT_DIGITA", "DTDIGITA", "DT_TRANSUS", "DATA_DIGITACAO"],
        DATA_ENCERRAMENTO: ["DT_ENCERRA", "DTENCERRA", "DATA_ENCERRAMENTO"],
        DATA_OBITO: ["DT_OBITO", "DTOBITO", "DATA_OBITO"],
        SEXO: ["CS_SEXO", "SEXO", "DS_SEXO"],
        CPF: ["NU_CPF", "CPF", "CPF_PACIENTE"],
        CNS: ["ID_CNS_SUS", "CNS", "NU_CNS", "CARTAOSUS"],
        MUNICIPIO_RESIDENCIA: ["ID_MN_RESI", "CODMUNRES", "COD_MUN_RES",
                               "ID_MUNICIP_RES"],
        IDADE: ["NU_IDADE_N", "IDADE", "NU_IDADE"],
        RACA_COR: ["CS_RACA", "RACACOR", "RACA_COR"],
        ESCOLARIDADE: ["CS_ESCOL_N", "ESCOLARIDADE", "ESC"],
        LOGRADOURO: ["NM_LOGRADO", "LOGRADOURO", "ENDERECO"],
        BAIRRO: ["NM_BAIRRO", "BAIRRO"],
        CEP: ["NU_CEP", "CEP"],
        NUMERO_REGISTRO: ["NU_NOTIFIC", "NUNOTIFIC", "NUMERO_NOTIF", "N_NOTIFIC"],
        AGRAVO: ["ID_AGRAVO", "IDAGRAVO", "AGRAVO", "CID_AGRAVO"],
        ESTABELECIMENTO: ["ID_UNIDADE", "IDUNIDADE", "CNES", "CO_CNES"],
        EVOLUCAO: ["EVOLUCAO", "EVOLUCAO_CASO", "DS_EVOLUCAO"],
        CLASSIFICACAO_FINAL: ["CLASSI_FIN", "CLASSIFIN", "CLASSIFICACAO_FINAL"],
    },
    obrigatorios={
        NOME: "Campo 10 da FIN — nome do paciente.",
        DATA_NASCIMENTO: "Campo 11 da FIN.",
        SEXO: "Campo 13 da FIN.",
        DATA_EVENTO: "Campo 3 da FIN — data da notificação.",
        DATA_SINTOMAS: "Campo 7 da FIN — data dos primeiros sintomas.",
        MUNICIPIO_RESIDENCIA: "Campo 20 da FIN — município de residência.",
        AGRAVO: "Campo 2 da FIN — agravo/doença (CID-10).",
        NUMERO_REGISTRO: "Campo 1 da FIN — número da notificação.",
    },
    recomendados={
        NOME_MAE: "Campo 18 da FIN. Chave de segunda ordem no linkage, "
                  "conforme Garcia, Miranda e Sousa (2022).",
        CPF: "Identificador de maior poder discriminante.",
        CNS: "Identificador nacional do usuário do SUS.",
        CLASSIFICACAO_FINAL: "Necessária ao encerramento oportuno da notificação.",
        EVOLUCAO: "Permite o cruzamento com o SIM para confirmação de óbitos.",
        DATA_ENCERRAMENTO: "Prazo de encerramento conforme o agravo notificado.",
    },
    dominios={SEXO: DOMINIO_SEXO["SINAN"], RACA_COR: DOMINIO_RACA_COR,
              ESCOLARIDADE: DOMINIO_ESCOLARIDADE,
              EVOLUCAO: DOMINIO_EVOLUCAO_SINAN,
              CLASSIFICACAO_FINAL: DOMINIO_CLASSI_FIN_SINAN},
    prazo_registro_dias=7,
    assinaturas=["NU_NOTIFIC", "ID_AGRAVO", "DT_NOTIFIC", "DT_SIN_PRI",
                 "NM_PACIENT", "CLASSI_FIN", "CS_SEXO", "TP_NOT", "SEM_NOT"],
)

PERFIL_GENERICO = PerfilSistema(
    sigla="OUTRA",
    nome_extenso="Base de dados não identificada",
    descricao=(
        "Base cujo conjunto de campos não corresponde às assinaturas do SIM, "
        "do SINAN ou do SINASC. A ferramenta aplica o mapeamento por "
        "aproximação de nomes e assinala o fato no relatório."
    ),
    instrumento="Não identificado",
    base_normativa="Não aplicável.",
    mapeamento={
        **{k: v for k, v in PERFIL_SINAN.mapeamento.items()},
    },
    obrigatorios={NOME: "Identificação mínima para pareamento.",
                  DATA_NASCIMENTO: "Chave de terceira ordem no linkage."},
    recomendados={NOME_MAE: "Chave de segunda ordem no linkage."},
    dominios={},
    prazo_registro_dias=60,
    assinaturas=[],
)

PERFIS = {p.sigla: p for p in (PERFIL_SIM, PERFIL_SINAN, PERFIL_SINASC)}
PERFIS["OUTRA"] = PERFIL_GENERICO


def identificar_sistema(colunas: list[str], nome_arquivo: str = "") -> PerfilSistema:
    """Identifica o sistema de origem pela assinatura de campos e pelo nome.

    A assinatura de campos prevalece sobre o nome do arquivo: nomes de arquivo
    são atribuídos por pessoas e variam; o conjunto de campos é produzido pelo
    próprio sistema exportador.
    """
    pontuacoes = {sigla: perfil.pontuar(colunas)
                  for sigla, perfil in PERFIS.items() if sigla != "OUTRA"}
    melhor = max(pontuacoes, key=pontuacoes.get) if pontuacoes else None

    if melhor and pontuacoes[melhor] >= 2:
        return PERFIS[melhor]

    texto = nome_arquivo.upper()
    for sigla, chaves in (("SINASC", ("SINASC", "DN", "NASCID", "NASC")),
                          ("SINAN", ("SINAN", "HEPA", "NOTIFIC", "AGRAVO")),
                          ("SIM", ("SIM", "DO", "OBITO", "ÓBITO", "MORTALID"))):
        if any(chave in texto for chave in chaves):
            return PERFIS[sigla]

    if melhor and pontuacoes[melhor] >= 1:
        return PERFIS[melhor]
    return PERFIL_GENERICO


# Chaves de pareamento na ordem de precedência discutida na fundamentação:
# a adição sequencial de chaves reduz drasticamente a ambiguidade
# (Garcia; Miranda; Sousa, 2022).
CHAVES_PAREAMENTO = [NOME, NOME_MAE, DATA_NASCIMENTO, SEXO, CPF, CNS]

# Pesos do escore probabilístico, conforme definido na fundamentação teórica
# do projeto: 0,4 para nome, 0,3 para nome da mãe e 0,3 para data de nascimento.
PESOS_PROBABILISTICO = {
    NOME: 0.40,
    NOME_MAE: 0.30,
    DATA_NASCIMENTO: 0.30,
}

# Variáveis auxiliares: não compõem o escore, mas corroboram ou contestam o par.
PESOS_AUXILIARES = {SEXO: 0.05, CPF: 0.10, CNS: 0.08,
                    MUNICIPIO_RESIDENCIA: 0.03}

LIMIAR_PAREAMENTO = 0.90          # corte validado na fundamentação do projeto
LIMIAR_REVISAO_MANUAL = 0.85      # análise de sensibilidade em ±0,05


# --------------------------------------------------------------------------- #
# Perspectivas de identidade
# --------------------------------------------------------------------------- #
#
# O SINASC registra dois sujeitos no mesmo documento: o recém-nascido e a mãe.
# Qual deles é "a pessoa" a ser pareada depende da pergunta epidemiológica:
#
#   - vigilância do óbito infantil  -> o sujeito é o recém-nascido
#     (SINASC x SIM: a criança nascida é a mesma que morreu);
#   - vigilância da transmissão vertical e do óbito materno -> o sujeito é a mãe
#     (SINASC x SINAN: a gestante notificada é a mesma que deu à luz).
#
# Sem essa distinção explícita, o relacionamento compara o nome do
# recém-nascido com o nome de um adulto e não encontra par algum — erro que
# não se manifesta como falha, mas como resultado vazio, e por isso é
# particularmente traiçoeiro na rotina.

PERSPECTIVA_RECEM_NASCIDO = "recem_nascido"
PERSPECTIVA_MAE = "mae"

PERSPECTIVAS = {
    PERSPECTIVA_RECEM_NASCIDO: {
        "rotulo": "Recém-nascido",
        "descricao": ("O sujeito do pareamento é a criança nascida viva. "
                      "Indicada para o relacionamento SINASC x SIM na "
                      "vigilância do óbito infantil e fetal "
                      "(Portaria GM/MS nº 72/2010)."),
        "aplica_a": ["SINASC"],
        "sobreposicao": {},
    },
    PERSPECTIVA_MAE: {
        "rotulo": "Mãe",
        "descricao": ("O sujeito do pareamento é a mãe. Indicada para o "
                      "relacionamento SINASC x SINAN (transmissão vertical, "
                      "agravos na gestação) e SINASC x SIM na vigilância do "
                      "óbito materno."),
        "aplica_a": ["SINASC"],
        # A identidade da mãe passa a ocupar os campos de identificação
        # principal; o nome do recém-nascido deixa de ser chave.
        "sobreposicao": {
            NOME: ["NOMEMAE", "NOME_MAE", "NM_MAE", "NM_MAE_PAC"],
            NOME_MAE: [],
            DATA_NASCIMENTO: ["DTNASCMAE", "DT_NASC_MAE", "DATANASCMAE"],
            CPF: ["CPFMAE", "CPF_MAE", "CPF"],
            CNS: ["NUMSUSMAE", "CNS_MAE", "CNS"],
            # O campo SEXO da DN refere-se ao recém-nascido. Mantê-lo sob a
            # perspectiva materna faria o sexo da criança ser confrontado com o
            # da paciente notificada, produzindo divergência sistemática e
            # remetendo à revisão manual pares corretos.
            SEXO: [],
        },
        # A mãe é, por definição do instrumento, a pessoa que deu à luz.
        "valores_fixos": {SEXO: "F"},
    },
}


def mapear_com_perspectiva(perfil: PerfilSistema, colunas: list[str],
                           perspectiva: str | None = None) -> dict[str, str]:
    """Mapeia as variáveis canônicas aplicando a perspectiva de identidade.

    Quando a perspectiva não se aplica ao sistema, o mapeamento padrão é
    devolvido sem alteração.
    """
    if not perspectiva or perspectiva not in PERSPECTIVAS:
        return perfil.mapear(colunas)
    definicao = PERSPECTIVAS[perspectiva]
    if perfil.sigla not in definicao["aplica_a"]:
        return perfil.mapear(colunas)

    disponiveis = {c.upper().strip(): c for c in colunas}
    mapeamento = perfil.mapear(colunas)
    for canonica, candidatos in definicao["sobreposicao"].items():
        escolhida = None
        for candidato in candidatos:
            if candidato.upper() in disponiveis:
                escolhida = disponiveis[candidato.upper()]
                break
        if escolhida:
            mapeamento[canonica] = escolhida
        else:
            mapeamento.pop(canonica, None)
    return mapeamento


def valores_fixos_da_perspectiva(perfil: PerfilSistema,
                                 perspectiva: str | None) -> dict[str, str]:
    """Valores que a perspectiva determina por definição do instrumento."""
    if not perspectiva or perspectiva not in PERSPECTIVAS:
        return {}
    definicao = PERSPECTIVAS[perspectiva]
    if perfil.sigla not in definicao["aplica_a"]:
        return {}
    return dict(definicao.get("valores_fixos", {}))


def perspectiva_sugerida(sigla_a: str, sigla_b: str) -> dict[str, str]:
    """Perspectiva recomendada para cada base, dado o par a relacionar."""
    par = {sigla_a, sigla_b}
    if par == {"SINASC", "SINAN"}:
        return {"SINASC": PERSPECTIVA_MAE}
    if par == {"SINASC", "SIM"}:
        return {"SINASC": PERSPECTIVA_RECEM_NASCIDO}
    return {}
