# -*- coding: utf-8 -*-
"""
Gerador de bases fictícias do SIM, SINAN e SINASC (ELO-SIS).

O projeto de intervenção prevê que o piloto seja executado exclusivamente
sobre bases fictícias, de caráter ilustrativo, semelhantes às produzidas pelos
sistemas, sem coleta de dados junto a participantes. Este módulo produz essas
bases e, deliberadamente, nelas insere os defeitos observados na rotina da
SUIS — duplicidades, incompletude, códigos fora de domínio, datas impossíveis,
erros de digitação em nomes — de modo que a capacidade de detecção da
ferramenta possa ser aferida contra um gabarito conhecido.

Nenhum dado real é utilizado. Os nomes são combinações aleatórias de
prenomes e sobrenomes de uso corrente, sem correspondência com pessoas.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .perfis import CODIGO_IBGE_SALVADOR

PRENOMES_F = ["MARIA", "ANA", "FRANCISCA", "ANTONIA", "ADRIANA", "JULIANA",
              "MARCIA", "FERNANDA", "PATRICIA", "ALINE", "SANDRA", "CAMILA",
              "AMANDA", "BRUNA", "JESSICA", "LETICIA", "LUCIANA", "VANESSA",
              "MARIANA", "GABRIELA", "VALERIA", "CLAUDIA", "DENISE", "ELAINE",
              "RITA", "SIMONE", "TATIANE", "VIVIANE", "CARLA", "DANIELA"]
PRENOMES_M = ["JOSE", "JOAO", "ANTONIO", "FRANCISCO", "CARLOS", "PAULO",
              "PEDRO", "LUCAS", "LUIZ", "MARCOS", "LUIS", "GABRIEL", "RAFAEL",
              "DANIEL", "MARCELO", "BRUNO", "EDUARDO", "FELIPE", "RODRIGO",
              "MANOEL", "MATEUS", "SERGIO", "ANDRE", "FERNANDO", "RICARDO",
              "TIAGO", "VINICIUS", "WESLEY", "ROBERTO", "GUSTAVO"]
NOMES_MEIO = ["DE", "DA", "DOS", "DAS", ""]
SOBRENOMES = ["SILVA", "SANTOS", "OLIVEIRA", "SOUZA", "RODRIGUES", "FERREIRA",
              "ALVES", "PEREIRA", "LIMA", "GOMES", "COSTA", "RIBEIRO",
              "MARTINS", "CARVALHO", "ALMEIDA", "LOPES", "SOARES", "FERNANDES",
              "VIEIRA", "BARBOSA", "ROCHA", "DIAS", "NASCIMENTO", "MOREIRA",
              "NUNES", "MARQUES", "MACHADO", "MENDES", "FREITAS", "CARDOSO",
              "CONCEICAO", "JESUS", "SANT ANNA", "CERQUEIRA", "BISPO"]

BAIRROS_SALVADOR = ["LIBERDADE", "CAJAZEIRAS", "ITAPUA", "PERNAMBUES",
                    "BROTAS", "FEDERACAO", "NORDESTE DE AMARALINA", "CABULA",
                    "SAO CRISTOVAO", "PARIPE", "PLATAFORMA", "BOCA DO RIO",
                    "PITUBA", "BARRA", "RIO VERMELHO", "CANABRAVA",
                    "SUSSUARANA", "VALERIA", "FAZENDA GRANDE", "CASTELO BRANCO"]

CNES_SALVADOR = ["0003859", "2465892", "2802034", "0004030", "2708283",
                 "5586275", "0002968", "2673584", "7896542", "0005266"]

# Hepatites virais — agravo adotado como amostragem no piloto (SINAN HEPANET).
CID_HEPATITES = ["B15", "B150", "B159", "B16", "B162", "B169", "B17", "B171",
                 "B172", "B179", "B18", "B180", "B181", "B182", "B189", "B19",
                 "B190", "B199"]

CID_OBITO = ["B199", "B171", "C22", "C220", "K703", "K746", "I64", "J189",
             "E149", "I219", "A419", "R99", "K729", "B182"]

# Códigos de município vizinhos, usados para simular registros de não residentes.
MUNICIPIOS_VIZINHOS = ["292920", "291080", "290570", "291005", "293135"]


def _sobrenome() -> str:
    partes = [random.choice(SOBRENOMES)]
    if random.random() < 0.65:
        ligacao = random.choice(NOMES_MEIO)
        partes.append(f"{ligacao} {random.choice(SOBRENOMES)}".strip())
    return " ".join(partes)


def _nome(sexo: str) -> str:
    prenome = random.choice(PRENOMES_F if sexo == "F" else PRENOMES_M)
    if random.random() < 0.45:
        prenome += " " + random.choice(PRENOMES_F if sexo == "F" else PRENOMES_M)
    return f"{prenome} {_sobrenome()}"


def _cpf_valido() -> str:
    base = [random.randint(0, 9) for _ in range(9)]
    for _ in range(2):
        soma = sum(d * (len(base) + 1 - i) for i, d in enumerate(base))
        digito = (soma * 10) % 11
        base.append(0 if digito == 10 else digito)
    return "".join(map(str, base))


def _cns_valido() -> str:
    while True:
        base = [random.choice([7, 8, 9])] + [random.randint(0, 9) for _ in range(14)]
        if sum(d * (15 - i) for i, d in enumerate(base)) % 11 == 0:
            return "".join(map(str, base))


def _data(inicio: date, fim: date) -> date:
    return inicio + timedelta(days=random.randint(0, (fim - inicio).days))


def _corromper_nome(nome: str) -> str:
    """Introduz os erros de digitação característicos dos sistemas."""
    tipo = random.choice(["troca", "omissao", "duplicacao", "fonetico",
                          "abreviacao", "inversao"])
    tokens = nome.split()
    if tipo == "fonetico":
        for origem, destino in (("SOUZA", "SOUSA"), ("LUIZ", "LUIS"),
                                ("CONCEICAO", "CONCEIÇÃO"), ("JESUS", "JESUZ"),
                                ("NASCIMENTO", "NACIMENTO"), ("SILVA", "SILVIA")):
            if origem in nome:
                return nome.replace(origem, destino, 1)
        tipo = "troca"
    if tipo == "abreviacao" and len(tokens) > 2:
        tokens[1] = tokens[1][0]
        return " ".join(tokens)
    if tipo == "inversao" and len(tokens) > 2:
        tokens[-2], tokens[-1] = tokens[-1], tokens[-2]
        return " ".join(tokens)
    if tipo == "omissao" and len(tokens) > 2:
        del tokens[random.randrange(1, len(tokens) - 1)]
        return " ".join(tokens)
    posicao = random.randrange(len(nome))
    if nome[posicao] == " ":
        posicao = max(0, posicao - 1)
    if tipo == "duplicacao":
        return nome[:posicao] + nome[posicao] + nome[posicao:]
    letra = random.choice("ABCDEFGHIJLMNOPQRSTUVXZ")
    return nome[:posicao] + letra + nome[posicao + 1:]


def _corromper_data(iso: str) -> str:
    partes = iso.split("-")
    if len(partes) != 3:
        return iso
    ano, mes, dia = partes
    escolha = random.random()
    if escolha < 0.4:                       # inversão dia/mês
        return f"{ano}-{dia}-{mes}" if int(dia) <= 12 else f"{ano}-{mes}-{dia}"
    if escolha < 0.7:                       # erro de um dígito no ano
        return f"{ano[:3]}{random.randint(0, 9)}-{mes}-{dia}"
    return f"{ano}-{mes}-{int(dia) % 28 + 1:02d}"


def gerar_bases(n_sinan: int = 3000, n_sim: int = 1200, n_sinasc: int = 2000,
                ano: int = 2024, semente: int = 20260919,
                proporcao_pareavel: float = 0.28) -> dict[str, pd.DataFrame]:
    """Gera as três bases fictícias com sobreposição conhecida entre elas.

    A proporção de registros efetivamente pareáveis é controlada, o que
    permite aferir a sensibilidade e o valor preditivo positivo da rotina
    contra um gabarito — exatamente o procedimento de avaliação previsto no
    Quadro 4 do projeto.
    """
    random.seed(semente)
    inicio = date(ano, 1, 1)
    fim = date(ano, 12, 31)

    def nova_pessoa(identificador: int) -> dict:
        sexo = random.choice(["M", "F"])
        nascimento = _data(date(ano - 95, 1, 1), date(ano, 12, 31))
        return {
            "id": f"P{identificador:07d}",
            "nome": _nome(sexo),
            "mae": _nome("F"),
            "nascimento": nascimento.isoformat(),
            "sexo": sexo,
            "cpf": _cpf_valido(),
            "cns": _cns_valido(),
            "bairro": random.choice(BAIRROS_SALVADOR),
            "cep": "4" + "".join(str(random.randint(0, 9)) for _ in range(7)),
        }

    # As populações precisam ser disjuntas: pessoas que só existem no SINAN não
    # podem reaparecer no SIM por acaso, sob pena de o gabarito registrar como
    # falso-positivo um par que é, de fato, verdadeiro.
    n_compartilhadas = int(min(n_sim, n_sinan) * proporcao_pareavel)
    sequencia = iter(range(1, 10_000_000))
    compartilhadas = [nova_pessoa(next(sequencia)) for _ in range(n_compartilhadas)]
    so_sinan = [nova_pessoa(next(sequencia))
                for _ in range(max(0, n_sinan - n_compartilhadas))]
    so_sim = [nova_pessoa(next(sequencia))
              for _ in range(max(0, n_sim - n_compartilhadas))]
    so_sinasc = [nova_pessoa(next(sequencia)) for _ in range(n_sinasc)]

    # Parte dos recém-nascidos do SINASC morre no mesmo ano e reaparece no SIM:
    # é a sobreposição que sustenta a vigilância do óbito infantil.
    n_obitos_infantis = max(1, int(n_sinasc * 0.02))
    recem_nascidos_falecidos = [nova_pessoa(next(sequencia))
                                for _ in range(n_obitos_infantis)]

    # Parte das mães do SINASC também é notificada no SINAN (gestantes com o
    # agravo sob vigilância) — sobreposição que sustenta a investigação da
    # transmissão vertical.
    maes_do_sinasc = compartilhadas[:max(1, n_sinasc // 5)] + so_sinasc

    gabarito: list[dict] = []
    sinan = _gerar_sinan(compartilhadas + so_sinan, inicio, fim, gabarito)
    # O SINASC é gerado antes do SIM: é na Declaração de Nascido Vivo que a
    # criança recebe a sua mãe, e o SIM precisa registrar a mesma mãe na
    # Declaração de Óbito para que o relacionamento seja possível.
    sinasc = _gerar_sinasc(maes_do_sinasc, inicio, fim, gabarito,
                           recem_nascidos_falecidos)
    sim = _gerar_sim(compartilhadas + so_sim, inicio, fim, gabarito,
                     recem_nascidos_falecidos)

    return {"SINAN": sinan, "SIM": sim, "SINASC": sinasc,
            "GABARITO": pd.DataFrame(gabarito)}



def _indice_gabarito(gabarito: list[dict], sistema: str) -> dict[str, str]:
    return {linha["REGISTRO"]: linha["ID_PESSOA"] for linha in gabarito
            if linha["SISTEMA"] == sistema}


def _papel_do_registro(gabarito: list[dict], sistema: str,
                       registro: str) -> str:
    for linha in gabarito:
        if linha["SISTEMA"] == sistema and linha["REGISTRO"] == registro:
            return linha.get("PAPEL", "")
    return ""


def _registrar_duplicata(gabarito: list[dict], sistema: str, campo: str,
                         original: dict, copia: dict, tipo: str) -> None:
    """Anota no gabarito que a cópia se refere à mesma pessoa do original.

    Sem esse registro, uma duplicata seria contabilizada como falso-positivo
    na aferição de sensibilidade e de valor preditivo positivo, distorcendo a
    avaliação da rotina.
    """
    indice = _indice_gabarito(gabarito, sistema)
    identificador = indice.get(original[campo])
    if identificador:
        gabarito.append({"SISTEMA": sistema, "ID_PESSOA": identificador,
                         "REGISTRO": copia[campo],
                         "PAPEL": _papel_do_registro(gabarito, sistema,
                                                     original[campo]),
                         "ORIGEM": tipo})


def _gerar_sinan(populacao, inicio, fim, gabarito) -> pd.DataFrame:
    registros = []
    for i, pessoa in enumerate(populacao):
        sintomas = _data(inicio, fim - timedelta(days=20))
        notificacao = sintomas + timedelta(days=random.randint(0, 25))
        digitacao = notificacao + timedelta(days=random.randint(0, 20))
        obito_relacionado = random.random() < 0.06

        nome = pessoa["nome"]
        mae = pessoa["mae"]
        nascimento = pessoa["nascimento"]
        if random.random() < 0.18:
            nome = _corromper_nome(nome)
        if random.random() < 0.12:
            mae = _corromper_nome(mae)
        if random.random() < 0.05:
            nascimento = _corromper_data(nascimento)

        registro = {
            "NU_NOTIFIC": f"{2024000000 + i}",
            "TP_NOT": "2",
            "ID_AGRAVO": random.choice(CID_HEPATITES),
            "DT_NOTIFIC": notificacao.isoformat(),
            "SEM_NOT": f"2024{notificacao.isocalendar()[1]:02d}",
            "NU_ANO": "2024",
            "SG_UF_NOT": "29",
            "ID_MUNICIP": CODIGO_IBGE_SALVADOR,
            "ID_UNIDADE": random.choice(CNES_SALVADOR),
            "DT_SIN_PRI": sintomas.isoformat(),
            "NM_PACIENT": nome,
            "NM_MAE_PAC": mae if random.random() > 0.14 else "",
            "DT_NASC": nascimento,
            "CS_SEXO": pessoa["sexo"],
            "CS_RACA": random.choice(["1", "2", "3", "4", "5", "9"]),
            "CS_ESCOL_N": random.choice(["0", "1", "2", "3", "4", "5", "6",
                                         "7", "8", "9", "10"]),
            "NU_CPF": pessoa["cpf"] if random.random() < 0.42 else "",
            "ID_CNS_SUS": pessoa["cns"] if random.random() < 0.38 else "",
            "ID_MN_RESI": (CODIGO_IBGE_SALVADOR if random.random() > 0.05
                           else random.choice(MUNICIPIOS_VIZINHOS)),
            "NM_BAIRRO": pessoa["bairro"],
            "NU_CEP": pessoa["cep"],
            "DT_DIGITA": digitacao.isoformat(),
            "CLASSI_FIN": random.choice(["1", "1", "1", "2", "5", "8", ""]),
            "CRITERIO": random.choice(["1", "2", "3"]),
            "EVOLUCAO": "2" if obito_relacionado else random.choice(["1", "1", "4", "9", ""]),
            "DT_OBITO": "",
            "DT_ENCERRA": (digitacao + timedelta(days=random.randint(5, 120))).isoformat()
            if random.random() < 0.7 else "",
        }
        if obito_relacionado:
            registro["DT_OBITO"] = (notificacao
                                    + timedelta(days=random.randint(1, 180))).isoformat()
        registros.append(registro)
        gabarito.append({"SISTEMA": "SINAN", "ID_PESSOA": pessoa["id"],
                         "REGISTRO": registro["NU_NOTIFIC"], "PAPEL": "PACIENTE",
                         "ORIGEM": "Registro original"})

    _injetar_defeitos_sinan(registros, gabarito)
    return pd.DataFrame(registros)


def _injetar_defeitos_sinan(registros: list[dict], gabarito: list[dict]) -> None:
    total = len(registros)
    if total < 20:
        return
    indices = random.sample(range(total), min(total, int(total * 0.13)))
    for posicao, indice in enumerate(indices):
        registro = registros[indice]
        defeito = posicao % 8
        if defeito == 0:
            registro["NM_PACIENT"] = ""
        elif defeito == 1:
            registro["DT_NASC"] = ""
        elif defeito == 2:
            registro["CS_SEXO"] = random.choice(["X", "3", "0"])
        elif defeito == 3:
            registro["DT_SIN_PRI"] = (date.fromisoformat(registro["DT_NOTIFIC"])
                                      + timedelta(days=random.randint(1, 30))).isoformat()
        elif defeito == 4:
            registro["ID_AGRAVO"] = random.choice(["ZZZ", "999", "B1"])
        elif defeito == 5:
            registro["NM_PACIENT"] = random.choice(["IGNORADO", "AAAA", "TESTE",
                                                    "NAO INFORMADO", "RN"])
        elif defeito == 6:
            registro["DT_NASC"] = "31/02/1985"
        else:
            registro["NU_CPF"] = random.choice(["11111111111", "000.000.000-00",
                                                "12345678901"])
    # Duplicidades técnicas, de conteúdo e prováveis
    for _ in range(max(2, total // 120)):
        original = random.choice(registros[:total])
        registros.append(dict(original))              # duplicata técnica
    for _ in range(max(2, total // 150)):
        original = random.choice(registros[:total])
        copia = dict(original)
        copia["NU_NOTIFIC"] = f"9{original['NU_NOTIFIC'][1:]}"
        _registrar_duplicata(gabarito, "SINAN", "NU_NOTIFIC", original, copia,
                             "Duplicata de conteúdo")
        registros.append(copia)
    for _ in range(max(2, total // 200)):
        original = random.choice(registros[:total])
        copia = dict(original)
        copia["NU_NOTIFIC"] = f"8{original['NU_NOTIFIC'][1:]}"
        copia["NM_PACIENT"] = _corromper_nome(original["NM_PACIENT"] or "ANA SILVA")
        _registrar_duplicata(gabarito, "SINAN", "NU_NOTIFIC", original, copia,
                             "Duplicata provável")
        registros.append(copia)


def _gerar_sim(populacao, inicio, fim, gabarito,
               recem_nascidos_falecidos=None) -> pd.DataFrame:
    registros = []
    for i, pessoa in enumerate(populacao):
        obito = _data(inicio, fim)
        cadastro = obito + timedelta(days=random.randint(1, 75))

        nome = pessoa["nome"]
        mae = pessoa["mae"]
        nascimento = pessoa["nascimento"]
        if random.random() < 0.22:
            nome = _corromper_nome(nome)
        if random.random() < 0.16:
            mae = _corromper_nome(mae)
        if random.random() < 0.06:
            nascimento = _corromper_data(nascimento)

        gabarito.append({"SISTEMA": "SIM", "ID_PESSOA": pessoa["id"],
                         "REGISTRO": f"{29000000 + i}", "PAPEL": "FALECIDO",
                         "ORIGEM": "Registro original"})
        registros.append({
            "NUMERODO": f"{29000000 + i}",
            "TIPOBITO": "2",
            "DTOBITO": obito.isoformat(),
            "DTNASC": nascimento,
            "NOME": nome,
            "NOMEMAE": mae if random.random() > 0.24 else "",
            "NOMEPAI": _nome("M") if random.random() > 0.45 else "",
            "SEXO": "1" if pessoa["sexo"] == "M" else "2",
            "RACACOR": random.choice(["1", "2", "3", "4", "5", "9"]),
            "ESC": random.choice(["0", "1", "2", "3", "4", "5", "9"]),
            "CODMUNRES": (CODIGO_IBGE_SALVADOR if random.random() > 0.04
                          else random.choice(MUNICIPIOS_VIZINHOS)),
            "CODMUNOCOR": CODIGO_IBGE_SALVADOR,
            "CODESTAB": random.choice(CNES_SALVADOR),
            "LOCOCOR": random.choice(["1", "2", "3", "4", "5"]),
            "CAUSABAS": random.choice(CID_OBITO),
            "CPF": pessoa["cpf"] if random.random() < 0.30 else "",
            "CNS": pessoa["cns"] if random.random() < 0.26 else "",
            "BAIRRO": pessoa["bairro"],
            "CEP": pessoa["cep"],
            "ASSISTMED": random.choice(["1", "2", "9"]),
            "NECROPSIA": random.choice(["1", "2", "9"]),
            "DTCADASTRO": cadastro.isoformat(),
            "DTATESTADO": obito.isoformat(),
        })

    # Óbitos infantis: o falecido é o próprio recém-nascido registrado no
    # SINASC, com menos de um ano de idade na data do óbito.
    deslocamento = len(registros)
    for j, crianca in enumerate(recem_nascidos_falecidos or []):
        nascimento = date.fromisoformat(crianca["nascimento"])
        obito = nascimento + timedelta(days=random.randint(0, 360))
        if obito > fim:
            obito = fim
        numero = f"{29000000 + deslocamento + j}"
        gabarito.append({"SISTEMA": "SIM", "ID_PESSOA": crianca["id"],
                         "REGISTRO": numero, "PAPEL": "RECEM_NASCIDO",
                         "ORIGEM": "Óbito infantil"})
        nome = crianca["nome"] if random.random() > 0.20 else _corromper_nome(crianca["nome"])
        registros.append({
            "NUMERODO": numero,
            "TIPOBITO": "2",
            "DTOBITO": obito.isoformat(),
            "DTNASC": crianca["nascimento"],
            "NOME": nome,
            "NOMEMAE": crianca["mae"] if random.random() > 0.15 else "",
            "NOMEPAI": "",
            "SEXO": "1" if crianca["sexo"] == "M" else "2",
            "RACACOR": random.choice(["1", "2", "3", "4", "5", "9"]),
            "ESC": "9",
            "CODMUNRES": CODIGO_IBGE_SALVADOR,
            "CODMUNOCOR": CODIGO_IBGE_SALVADOR,
            "CODESTAB": random.choice(CNES_SALVADOR),
            "LOCOCOR": "1",
            "CAUSABAS": random.choice(["P219", "P073", "Q249", "P369", "A419",
                                       "P220", "J189", "P285"]),
            "CPF": "",
            "CNS": crianca["cns"] if random.random() < 0.20 else "",
            "BAIRRO": crianca["bairro"],
            "CEP": crianca["cep"],
            "ASSISTMED": random.choice(["1", "2"]),
            "NECROPSIA": random.choice(["1", "2", "9"]),
            "DTCADASTRO": (obito + timedelta(days=random.randint(1, 60))).isoformat(),
            "DTATESTADO": obito.isoformat(),
        })

    _injetar_defeitos_sim(registros, gabarito)
    return pd.DataFrame(registros)


def _injetar_defeitos_sim(registros: list[dict], gabarito: list[dict]) -> None:
    total = len(registros)
    if total < 20:
        return
    indices = random.sample(range(total), min(total, int(total * 0.12)))
    for posicao, indice in enumerate(indices):
        registro = registros[indice]
        defeito = posicao % 7
        if defeito == 0:
            registro["CAUSABAS"] = ""
        elif defeito == 1:
            registro["NOME"] = ""
        elif defeito == 2:
            registro["SEXO"] = random.choice(["0", "3", "M"])
        elif defeito == 3:
            registro["DTNASC"] = (date.fromisoformat(registro["DTOBITO"])
                                  + timedelta(days=random.randint(1, 400))).isoformat()
        elif defeito == 4:
            registro["DTNASC"] = "1890-05-12"
        elif defeito == 5:
            registro["CAUSABAS"] = random.choice(["ZZ99", "0000", "X"])
        else:
            registro["DTCADASTRO"] = ""
    for _ in range(max(2, total // 100)):
        registros.append(dict(random.choice(registros[:total])))
    for _ in range(max(2, total // 140)):
        original = random.choice(registros[:total])
        copia = dict(original)
        copia["NUMERODO"] = f"79{original['NUMERODO'][2:]}"
        _registrar_duplicata(gabarito, "SIM", "NUMERODO", original, copia,
                             "Duplicata de conteúdo")
        registros.append(copia)


def _gerar_sinasc(populacao, inicio, fim, gabarito,
                  recem_nascidos_falecidos=None) -> pd.DataFrame:
    registros = []
    falecidos = list(recem_nascidos_falecidos or [])
    for i, pessoa in enumerate(populacao):
        nascimento = _data(inicio, fim)
        cadastro = nascimento + timedelta(days=random.randint(1, 40))
        sexo = random.choice(["M", "F"])
        nome_rn = (f"{random.choice(PRENOMES_F if sexo == 'F' else PRENOMES_M)} "
                   f"{pessoa['nome'].split()[-1]}")
        nascimento_rn = nascimento.isoformat()

        numero_dn = f"{31000000 + i}"
        # A mãe é a identidade pareável na perspectiva materna.
        gabarito.append({"SISTEMA": "SINASC", "ID_PESSOA": pessoa["id"],
                         "REGISTRO": numero_dn, "PAPEL": "MAE",
                         "ORIGEM": "Registro original"})
        # Parte dos recém-nascidos corresponde a crianças que morrerão no ano;
        # nesses casos, o recém-nascido é a identidade pareável com o SIM.
        crianca = falecidos.pop() if falecidos and random.random() < 0.85 else None
        if crianca:
            nome_rn = crianca["nome"]
            nascimento_rn = crianca["nascimento"]
            sexo = crianca["sexo"]
            # A criança e o registro precisam compartilhar a mesma mãe: é ela
            # que o SIM registrará no campo NOMEMAE da Declaração de Óbito.
            crianca["mae"] = pessoa["nome"]
            gabarito.append({"SISTEMA": "SINASC", "ID_PESSOA": crianca["id"],
                             "REGISTRO": numero_dn, "PAPEL": "RECEM_NASCIDO",
                             "ORIGEM": "Nascido vivo que evoluiu a óbito"})
        if crianca:
            nascimento = date.fromisoformat(nascimento_rn)
            cadastro = nascimento + timedelta(days=random.randint(1, 40))
        registros.append({
            "NUMERODN": numero_dn,
            "LOCNASC": random.choice(["1", "1", "1", "2", "3"]),
            "CODESTAB": random.choice(CNES_SALVADOR),
            "CODMUNNASC": CODIGO_IBGE_SALVADOR,
            "NOMERN": nome_rn if (crianca or random.random() > 0.30) else "",
            "NOMEMAE": pessoa["nome"],
            "DTNASCMAE": pessoa["nascimento"],
            "IDADEMAE": str(max(12, min(55, 2024 - int(pessoa["nascimento"][:4])))),
            "ESTCIVMAE": random.choice(["1", "2", "3", "5", "9"]),
            "ESCMAE": random.choice(["1", "2", "3", "4", "5", "9"]),
            "QTDFILVIVO": str(random.randint(0, 6)),
            "QTDFILMORT": str(random.randint(0, 2)),
            "CODMUNRES": (CODIGO_IBGE_SALVADOR if random.random() > 0.05
                          else random.choice(MUNICIPIOS_VIZINHOS)),
            "GESTACAO": random.choice(["1", "2", "3", "4", "5", "6", "9"]),
            "GRAVIDEZ": random.choice(["1", "1", "1", "2", "3"]),
            "PARTO": random.choice(["1", "2", "9"]),
            "CONSULTAS": random.choice(["1", "2", "3", "4", "9"]),
            "DTNASC": nascimento.isoformat(),
            "HORANASC": f"{random.randint(0, 23):02d}{random.randint(0, 59):02d}",
            "SEXO": "1" if sexo == "M" else "2",
            "APGAR1": str(random.randint(4, 10)),
            "APGAR5": str(random.randint(6, 10)),
            "RACACOR": random.choice(["1", "2", "3", "4", "5", "9"]),
            "PESO": str(random.randint(1800, 4400)),
            "IDANOMAL": random.choice(["1", "2", "9"]),
            "CPFMAE": pessoa["cpf"] if random.random() < 0.46 else "",
            "NUMSUSMAE": pessoa["cns"] if random.random() < 0.33 else "",
            "BAIRRO": pessoa["bairro"],
            "CEP": pessoa["cep"],
            "DTCADASTRO": cadastro.isoformat(),
        })

    _injetar_defeitos_sinasc(registros, gabarito)
    return pd.DataFrame(registros)


def _injetar_defeitos_sinasc(registros: list[dict], gabarito: list[dict]) -> None:
    total = len(registros)
    if total < 20:
        return
    indices = random.sample(range(total), min(total, int(total * 0.11)))
    for posicao, indice in enumerate(indices):
        registro = registros[indice]
        defeito = posicao % 7
        if defeito == 0:
            registro["PESO"] = random.choice(["0", "35", "12000", "3"])
        elif defeito == 1:
            registro["NOMEMAE"] = ""
        elif defeito == 2:
            registro["SEXO"] = random.choice(["0", "3", "9"])
        elif defeito == 3:
            registro["PESO"] = ""
        elif defeito == 4:
            registro["DTNASCMAE"] = ""
        elif defeito == 5:
            registro["NOMEMAE"] = random.choice(["IGNORADO", "NAO INFORMADO", "XXX"])
        else:
            registro["CODMUNRES"] = ""
    for _ in range(max(2, total // 110)):
        registros.append(dict(random.choice(registros[:total])))
    for _ in range(max(2, total // 160)):
        original = random.choice(registros[:total])
        copia = dict(original)
        copia["NUMERODN"] = f"72{original['NUMERODN'][2:]}"
        copia["NOMEMAE"] = _corromper_nome(original["NOMEMAE"] or "MARIA SILVA")
        _registrar_duplicata(gabarito, "SINASC", "NUMERODN", original, copia,
                             "Duplicata provável")
        registros.append(copia)


def salvar_bases(destino: Path | str, formato: str = "csv", **parametros) -> dict[str, Path]:
    """Gera e grava as bases fictícias no formato solicitado."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    bases = gerar_bases(**parametros)
    caminhos = {}
    for sigla, quadro in bases.items():
        if sigla == "GABARITO":
            caminho = destino / "gabarito_pareamento.csv"
            quadro.to_csv(caminho, sep=";", index=False, encoding="utf-8-sig")
            caminhos[sigla] = caminho
            continue
        if formato == "dbf":
            from .dbf import escrever_dbf
            caminho = destino / f"{sigla.lower()}_2024_ficticia.dbf"
            escrever_dbf(caminho, list(quadro.columns),
                         quadro.to_dict("records"))
        elif formato in ("xlsx", "excel"):
            caminho = destino / f"{sigla.lower()}_2024_ficticia.xlsx"
            quadro.to_excel(caminho, index=False)
        else:
            caminho = destino / f"{sigla.lower()}_2024_ficticia.csv"
            quadro.to_csv(caminho, sep=";", index=False, encoding="utf-8-sig")
        caminhos[sigla] = caminho
    return caminhos
