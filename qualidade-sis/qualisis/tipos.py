"""Tipos de inconsistência, cores e atributos de qualidade.

Este módulo é a "fonte da verdade" do sistema: toda inconsistência detectada
pelo motor de regras tem um tipo, e cada tipo tem uma cor fixa (usada tanto no
Excel quanto no relatório HTML), uma gravidade e um atributo de qualidade da
informação associado.

Cores:
  * ``cor_celula``  -> preenchimento da célula no Excel (tom claro, para que o
    texto preto continue legível).
  * ``cor_marca``   -> cor saturada usada em gráficos, legendas e etiquetas.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# Tipos de inconsistência
# --------------------------------------------------------------------------- #

DUPLICIDADE = "duplicidade"
EM_BRANCO = "em_branco"
IGNORADO = "ignorado"
CODIGO_INVALIDO = "codigo_invalido"
DATA_INVALIDA = "data_invalida"
INCOERENCIA = "incoerencia"
FORMATO_INVALIDO = "formato_invalido"
FORA_DE_FAIXA = "fora_de_faixa"
FORA_DO_PRAZO = "fora_do_prazo"


@dataclass(frozen=True)
class TipoInconsistencia:
    codigo: str
    rotulo: str
    descricao: str
    cor_celula: str          # RRGGBB (preenchimento no Excel)
    cor_marca: str           # #RRGGBB (gráficos / legenda)
    gravidade: str           # alta | media | baixa
    atributos: tuple         # atributos de qualidade impactados
    peso: float = 1.0        # peso no escore de gravidade do registro


TIPOS = {
    DUPLICIDADE: TipoInconsistencia(
        codigo=DUPLICIDADE,
        rotulo="Duplicidade",
        descricao=(
            "Registro repetido segundo a chave identificadora do sistema ou "
            "segundo chave probabilística (nome + data + mãe/município)."
        ),
        cor_celula="F4B9B8",
        cor_marca="#e34948",
        gravidade="alta",
        atributos=("Singularidade", "Confiabilidade", "Precisão"),
        peso=3.0,
    ),
    EM_BRANCO: TipoInconsistencia(
        codigo=EM_BRANCO,
        rotulo="Campo em branco",
        descricao="Campo obrigatório ou essencial sem preenchimento.",
        cor_celula="FCE7A8",
        cor_marca="#eda100",
        gravidade="alta",
        atributos=("Completude", "Suficiência", "Abrangência"),
        peso=2.0,
    ),
    IGNORADO: TipoInconsistencia(
        codigo=IGNORADO,
        rotulo="Ignorado / Não informado",
        descricao=(
            "Campo preenchido com código de ignorado (9, 99, 999, "
            "'IGNORADO', 'NÃO INFORMADO'). Formalmente completo, "
            "porém sem valor informativo."
        ),
        cor_celula="FBD6C4",
        cor_marca="#eb6834",
        gravidade="media",
        atributos=("Confiabilidade", "Valor informativo", "Utilidade"),
        peso=1.5,
    ),
    CODIGO_INVALIDO: TipoInconsistencia(
        codigo=CODIGO_INVALIDO,
        rotulo="Código inválido",
        descricao=(
            "Valor fora do domínio previsto no dicionário de dados do sistema "
            "(categoria inexistente, código de município/CID/CNES inválido)."
        ),
        cor_celula="D5D0EF",
        cor_marca="#4a3aa7",
        gravidade="alta",
        atributos=("Validade", "Correção", "Precisão", "Inequivocidade"),
        peso=2.5,
    ),
    DATA_INVALIDA: TipoInconsistencia(
        codigo=DATA_INVALIDA,
        rotulo="Data inválida ou incoerente",
        descricao=(
            "Data inexistente, fora do intervalo plausível, no futuro, ou "
            "em ordem cronológica impossível (ex.: nascimento após o óbito)."
        ),
        cor_celula="C6DDF7",
        cor_marca="#2a78d6",
        gravidade="alta",
        atributos=("Validade", "Logicidade", "Coerência", "Veracidade"),
        peso=2.5,
    ),
    INCOERENCIA: TipoInconsistencia(
        codigo=INCOERENCIA,
        rotulo="Incoerência entre campos",
        descricao=(
            "Combinação logicamente impossível ou improvável entre campos "
            "(ex.: sexo masculino com óbito puerperal; idade x escolaridade)."
        ),
        cor_celula="BEE7D6",
        cor_marca="#1baf7a",
        gravidade="alta",
        atributos=("Coerência", "Logicidade", "Compatibilidade", "Veracidade"),
        peso=2.5,
    ),
    FORMATO_INVALIDO: TipoInconsistencia(
        codigo=FORMATO_INVALIDO,
        rotulo="Formato inválido",
        descricao=(
            "Conteúdo não obedece à máscara/estrutura esperada "
            "(CNS, CPF, CEP, telefone, número de DO/DN, CID-10)."
        ),
        cor_celula="F8D7E3",
        cor_marca="#e87ba4",
        gravidade="media",
        atributos=("Formato", "Legibilidade", "Interpretabilidade"),
        peso=1.5,
    ),
    FORA_DE_FAIXA: TipoInconsistencia(
        codigo=FORA_DE_FAIXA,
        rotulo="Valor fora de faixa",
        descricao=(
            "Valor numérico fora dos limites plausíveis "
            "(peso ao nascer, idade, consultas de pré-natal, Apgar)."
        ),
        cor_celula="CFE6B8",
        cor_marca="#008300",
        gravidade="media",
        atributos=("Quantidade", "Precisão", "Veracidade", "Correção"),
        peso=2.0,
    ),
    FORA_DO_PRAZO: TipoInconsistencia(
        codigo=FORA_DO_PRAZO,
        rotulo="Fora do prazo",
        descricao=(
            "Registro digitado/notificado/encerrado fora do prazo pactuado "
            "(oportunidade da notificação, da digitação e do encerramento)."
        ),
        cor_celula="DEDDD6",
        cor_marca="#898781",
        gravidade="media",
        atributos=("Tempestividade", "Atualidade", "Tempo de resposta"),
        peso=1.5,
    ),
}

ORDEM_TIPOS = [
    DUPLICIDADE,
    EM_BRANCO,
    IGNORADO,
    CODIGO_INVALIDO,
    DATA_INVALIDA,
    INCOERENCIA,
    FORMATO_INVALIDO,
    FORA_DE_FAIXA,
    FORA_DO_PRAZO,
]

GRAVIDADES = {"alta": 3.0, "media": 2.0, "baixa": 1.0}


def tipo(codigo: str) -> TipoInconsistencia:
    """Retorna o descritor do tipo; cria um genérico se for desconhecido."""
    if codigo in TIPOS:
        return TIPOS[codigo]
    return TipoInconsistencia(
        codigo=codigo,
        rotulo=codigo.replace("_", " ").capitalize(),
        descricao="Tipo definido pelo usuário.",
        cor_celula="E6E6E6",
        cor_marca="#52514e",
        gravidade="media",
        atributos=("Correção",),
        peso=1.0,
    )


# --------------------------------------------------------------------------- #
# Atributos de qualidade
# --------------------------------------------------------------------------- #
# Bloco A: atributos medidos automaticamente a partir da base (indicadores).
# Bloco B: atributos avaliados por instrumento estruturado (escala 1 a 5),
#          porque dependem de julgamento sobre o sistema, não sobre o dado.

@dataclass(frozen=True)
class Atributo:
    nome: str
    definicao: str
    bloco: str            # "automatico" | "instrumento"
    indicador: str = ""   # nome do indicador calculado (bloco automático)
    peso: float = 1.0
    evidencias: tuple = field(default=())


ATRIBUTOS_AUTOMATICOS = [
    Atributo("Completude", "Proporção de campos essenciais efetivamente preenchidos.",
             "automatico", "completude_essencial", peso=3.0),
    Atributo("Suficiência", "O conjunto preenchido basta para as análises do setor.",
             "automatico", "suficiencia_bloco", peso=2.0),
    Atributo("Confiabilidade", "Proporção de campos preenchidos com informação útil "
             "(exclui 'ignorado'/'não informado').",
             "automatico", "nao_ignorado", peso=3.0),
    Atributo("Validade", "Proporção de valores dentro do domínio do dicionário de dados.",
             "automatico", "validade_dominio", peso=3.0),
    Atributo("Correção", "Ausência de erros detectáveis por regra de crítica.",
             "automatico", "correcao", peso=3.0),
    Atributo("Precisão", "Granularidade e exatidão dos valores registrados.",
             "automatico", "precisao", peso=2.0),
    Atributo("Coerência", "Compatibilidade lógica entre campos do mesmo registro.",
             "automatico", "coerencia", peso=3.0),
    Atributo("Logicidade", "Ausência de combinações logicamente impossíveis.",
             "automatico", "logicidade", peso=2.0),
    Atributo("Singularidade", "Ausência de duplicidades (um evento, um registro).",
             "automatico", "singularidade", peso=3.0),
    Atributo("Tempestividade", "Registro dentro do prazo pactuado entre o evento e a digitação.",
             "automatico", "tempestividade", peso=3.0),
    Atributo("Atualidade", "Defasagem entre a data da extração e o evento mais recente.",
             "automatico", "atualidade", peso=2.0),
    Atributo("Abrangência", "Cobertura territorial/populacional dos registros esperados.",
             "automatico", "abrangencia", peso=2.0),
    Atributo("Quantidade", "Volume de registros compatível com o esperado para o período.",
             "automatico", "quantidade", peso=1.0),
    Atributo("Formato", "Conformidade de máscaras e estruturas de campo.",
             "automatico", "formato", peso=1.5),
    Atributo("Veracidade", "Consistência do dado com a realidade verificável.",
             "automatico", "veracidade", peso=2.0),
    Atributo("Inequivocidade", "Ausência de valores ambíguos ou multi-interpretáveis.",
             "automatico", "inequivocidade", peso=1.5),
    Atributo("Compatibilidade", "Aderência do dado às tabelas e padrões nacionais.",
             "automatico", "compatibilidade", peso=1.5),
    Atributo("Valor informativo", "Densidade de informação aproveitável por registro.",
             "automatico", "valor_informativo", peso=2.0),
    Atributo("Volume", "Massa de dados processada e sua evolução entre envios.",
             "automatico", "volume", peso=1.0),
    Atributo("Ordem", "Consistência da sequência temporal e de numeração dos registros.",
             "automatico", "ordem", peso=1.0),
    Atributo("Mensurabilidade", "Possibilidade de calcular indicadores a partir da base.",
             "automatico", "mensurabilidade", peso=1.5),
]

ATRIBUTOS_INSTRUMENTO = [
    Atributo("Clareza", "A informação é apresentada sem obscuridade ao usuário do sistema.",
             "instrumento", evidencias=("Telas e relatórios do sistema", "Rótulos dos campos")),
    Atributo("Acessibilidade", "Facilidade de obter o dado por quem tem perfil para tanto.",
             "instrumento", evidencias=("Perfis de acesso", "Tempo médio para liberação de acesso")),
    Atributo("Legibilidade", "Facilidade de leitura de telas, relatórios e exportações.",
             "instrumento", evidencias=("Exportações CSV/DBF", "Relatórios impressos")),
    Atributo("Pertinência", "O dado responde às perguntas de gestão do setor.",
             "instrumento", evidencias=("Demandas atendidas x demandas recebidas",)),
    Atributo("Utilidade", "O dado é efetivamente usado em decisões e produtos do setor.",
             "instrumento", evidencias=("Boletins, painéis e notas técnicas produzidos",)),
    Atributo("Compreensibilidade", "O usuário entende o significado do dado sem apoio externo.",
             "instrumento", evidencias=("Dicionário de dados disponível", "Treinamentos")),
    Atributo("Concisão", "Ausência de redundância entre campos e relatórios.",
             "instrumento", evidencias=("Campos redundantes identificados",)),
    Atributo("Localizabilidade", "Facilidade de encontrar um registro ou variável específica.",
             "instrumento", evidencias=("Recursos de busca e filtro do sistema",)),
    Atributo("Tempo de resposta", "Tempo do sistema para consultas, exportações e cargas.",
             "instrumento", evidencias=("Medição cronometrada de 5 operações padrão",)),
    Atributo("Segurança", "Proteção do dado (acesso, trilha de auditoria, LGPD).",
             "instrumento", evidencias=("Política de senhas", "Trilha de auditoria", "Termo de sigilo")),
    Atributo("Simplicidade", "Esforço necessário para operar o sistema.",
             "instrumento", evidencias=("Nº de passos para registrar uma notificação",)),
    Atributo("Credibilidade", "Confiança que os usuários finais depositam no dado.",
             "instrumento", evidencias=("Consulta estruturada a técnicos e gestores",)),
    Atributo("Imparcialidade", "Ausência de viés sistemático de captação/registro.",
             "instrumento", evidencias=("Comparação entre unidades notificadoras",)),
    Atributo("Importância", "Peso do sistema para a vigilância e para a gestão municipal.",
             "instrumento", evidencias=("Indicadores pactuados que dependem do sistema",)),
    Atributo("Significância", "Capacidade do dado de alterar decisões.",
             "instrumento", evidencias=("Decisões tomadas com base no sistema no período",)),
    Atributo("Conveniência", "Adequação do sistema à rotina dos serviços.",
             "instrumento", evidencias=("Relato das unidades notificadoras",)),
    Atributo("Interpretabilidade", "Existência de metadados que permitam interpretar o dado.",
             "instrumento", evidencias=("Dicionário, notas metodológicas, versões",)),
    Atributo("Relevância", "Aderência do conteúdo às prioridades de saúde do município.",
             "instrumento", evidencias=("Plano Municipal de Saúde", "Lista de agravos prioritários")),
]

ATRIBUTOS = {a.nome: a for a in ATRIBUTOS_AUTOMATICOS + ATRIBUTOS_INSTRUMENTO}


# --------------------------------------------------------------------------- #
# Classificação dos escores (adaptada de Romero & Cunha, 2006/2007)
# --------------------------------------------------------------------------- #

FAIXAS = [
    (95.0, "Excelente", "#0ca30c"),
    (90.0, "Bom", "#1baf7a"),
    (80.0, "Regular", "#fab219"),
    (50.0, "Ruim", "#ec835a"),
    (0.0, "Muito ruim", "#d03b3b"),
]


def classificar(percentual):
    """Classifica um percentual (0-100) em faixa qualitativa."""
    if percentual is None:
        return ("Não avaliado", "#898781")
    for limite, rotulo, cor in FAIXAS:
        if percentual >= limite:
            return (rotulo, cor)
    return ("Muito ruim", "#d03b3b")
