#!/usr/bin/env python3
"""Gera bases CSV fictícias para testar e demonstrar o QualiSIS.

Cria dois "envios" de cada sistema, imitando a base acumulativa real:

    <sigla>_envio1.csv  -> base acumulada até o mês anterior
    <sigla>_envio2.csv  -> mesma base com parte dos erros corrigidos + registros novos

Rodando a análise nos dois, na ordem, o relatório do segundo já traz a
comparação de resolutividade. Nenhum dado é real — nomes, números de DO/DN e
notificações são gerados aleatoriamente.

Uso:
    python exemplos/gerar_exemplos.py            (gera tudo em exemplos/bases)
    python exemplos/gerar_exemplos.py --registros 20000
"""

from __future__ import annotations

import argparse
import csv
import os
import random
from datetime import date, timedelta

PRENOMES = ["MARIA", "JOSE", "ANA", "JOAO", "ANTONIO", "FRANCISCA", "CARLOS", "PAULO",
            "ADRIANA", "LUCAS", "JULIANA", "MARCOS", "PATRICIA", "RAFAEL", "CAMILA",
            "BRUNO", "LARISSA", "GABRIEL", "VITORIA", "RODRIGO"]
SOBRENOMES = ["SILVA", "SANTOS", "OLIVEIRA", "SOUZA", "PEREIRA", "COSTA", "RODRIGUES",
              "ALMEIDA", "NASCIMENTO", "LIMA", "ARAUJO", "FERREIRA", "CARVALHO", "GOMES"]
CNES = ["2748080", "0003859", "2400123", "6432198", "9999999", "2748081", "12345"]
BAIRROS = ["LIBERDADE", "CAJAZEIRAS", "PERIPERI", "ITAPUA", "BROTAS", "PAU DA LIMA",
           "SAO CAETANO", "BARRA", "CABULA", "SUBURBIO FERROVIARIO"]
CID_OBITO = ["I219", "J189", "C349", "E149", "I64", "A419", "R99", "W878", "X959", "V892"]
CID_AGRAVO = ["A90", "A150", "A300", "B19", "A509", "W64", "Y09", "A379"]


def nome(rnd):
    return f"{rnd.choice(PRENOMES)} {rnd.choice(SOBRENOMES)} {rnd.choice(SOBRENOMES)}"


def data_br(d):
    return d.strftime("%d/%m/%Y")


def talvez(rnd, prob, valor, alternativa=""):
    return valor if rnd.random() > prob else alternativa


# --------------------------------------------------------------------------- #
def registros_sim(rnd, n, inicio, corrigir=0.0, janela=330):
    linhas = []
    for i in range(n):
        dt_obito = inicio + timedelta(days=rnd.randint(0, janela))
        idade_anos = rnd.randint(0, 95)
        dt_nasc = dt_obito - timedelta(days=idade_anos * 365 + rnd.randint(0, 364))
        sexo = rnd.choice(["1", "2"])
        atraso = rnd.choice([3, 7, 12, 20, 28, 35, 60, 95, 140])
        corrige = rnd.random() < corrigir
        p = 0.0 if corrige else 1.0  # quando "corrigido", os erros deixam de ser injetados

        linha = {
            "NUMERODO": f"{9000000 + i}",
            "TIPOBITO": rnd.choices(["2", "1"], weights=[92, 8])[0],
            "DTOBITO": data_br(dt_obito),
            "HORAOBITO": talvez(rnd, 0.12 * p, f"{rnd.randint(0, 23):02d}{rnd.randint(0, 59):02d}", "9999"),
            "DTNASC": data_br(dt_nasc),
            "IDADE": f"4{min(idade_anos, 99):02d}",
            "SEXO": sexo,
            "RACACOR": talvez(rnd, 0.22 * p, rnd.choice(["1", "2", "3", "4", "5"]), "9"),
            "ESTCIV": talvez(rnd, 0.18 * p, rnd.choice(["1", "2", "3", "4", "5"]), ""),
            "ESC": talvez(rnd, 0.30 * p, rnd.choice(["1", "2", "3", "4", "5"]), "9"),
            "OCUP": talvez(rnd, 0.25 * p, f"{rnd.randint(1000, 999999)}", ""),
            "CODMUNRES": talvez(rnd, 0.03 * p, "292740", "29274"),
            "LOCOCOR": talvez(rnd, 0.06 * p, rnd.choice(["1", "2", "3", "4", "5"]), "9"),
            "CODESTAB": talvez(rnd, 0.15 * p, rnd.choice(CNES), ""),
            "CODMUNOCOR": "292740",
            "IDADEMAE": "", "ESCMAE": "", "QTDFILVIVO": "", "QTDFILMORT": "",
            "GRAVIDEZ": "", "GESTACAO": "", "PARTO": "", "OBITOPARTO": "", "PESO": "",
            "OBITOGRAV": "", "OBITOPUERP": "",
            "ASSISTMED": talvez(rnd, 0.10 * p, rnd.choice(["1", "2"]), "9"),
            "EXAME": rnd.choice(["1", "2", "9"]),
            "CIRURGIA": rnd.choice(["1", "2", "9"]),
            "NECROPSIA": rnd.choice(["1", "2", "9"]),
            "LINHAA": rnd.choice(CID_OBITO),
            "LINHAB": talvez(rnd, 0.4, rnd.choice(CID_OBITO)),
            "LINHAC": "", "LINHAD": "",
            "CAUSABAS": talvez(rnd, 0.04 * p, rnd.choice(CID_OBITO), "XX99"),
            "CIRCOBITO": "", "ACIDTRAB": "", "FONTE": "",
            "ATESTANTE": talvez(rnd, 0.12 * p, rnd.choice(["1", "2", "3", "4", "5"]), ""),
            "TPPOS": rnd.choice(["S", "N", "N", "N"]),
            "DTINVESTIG": "", "DTCONINV": "", "FONTEINV": "",
            "DTCADASTRO": data_br(dt_obito + timedelta(days=atraso if not corrige else min(atraso, 25))),
            "NOME": nome(rnd),
            "NOMEMAE": talvez(rnd, 0.10 * p, nome(rnd), ""),
        }
        if linha["TIPOBITO"] == "1":  # óbito fetal
            linha.update({
                "GESTACAO": talvez(rnd, 0.25 * p, rnd.choice(["3", "4", "5"]), ""),
                "PESO": talvez(rnd, 0.2 * p, str(rnd.randint(500, 4200)), "99999"),
                "OBITOPARTO": talvez(rnd, 0.3 * p, rnd.choice(["1", "2", "3"]), ""),
                "PARTO": rnd.choice(["1", "2", "9"]),
                "IDADEMAE": str(rnd.randint(15, 44)),
                "GRAVIDEZ": rnd.choice(["1", "1", "2"]),
            })
        if sexo == "2" and 10 <= idade_anos <= 49:
            linha["OBITOGRAV"] = rnd.choice(["1", "2", "2", "9"])
            linha["OBITOPUERP"] = rnd.choice(["1", "2", "3", "9"])
        if not corrige and rnd.random() < 0.01:      # incoerência proposital
            linha["OBITOGRAV"] = "1"
            linha["SEXO"] = "1"
        if not corrige and rnd.random() < 0.008:     # data impossível
            linha["DTNASC"] = data_br(dt_obito + timedelta(days=rnd.randint(1, 400)))
        if linha["CAUSABAS"].startswith(("V", "W", "X", "Y")):
            linha["CIRCOBITO"] = talvez(rnd, 0.3 * p, rnd.choice(["1", "2", "3", "4"]), "9")
            linha["FONTE"] = talvez(rnd, 0.45 * p, rnd.choice(["1", "2", "3", "4"]), "")
            linha["ACIDTRAB"] = rnd.choice(["1", "2", "9"])
        if linha["TPPOS"] == "S":
            linha["DTINVESTIG"] = data_br(dt_obito + timedelta(days=rnd.randint(10, 200)))
            linha["DTCONINV"] = talvez(rnd, 0.35 * p,
                                       data_br(dt_obito + timedelta(days=rnd.randint(20, 260))), "")
            linha["FONTEINV"] = talvez(rnd, 0.3 * p, rnd.choice(["1", "2", "3", "4", "5", "6"]), "")
        linhas.append(linha)
    return linhas


def registros_sinasc(rnd, n, inicio, corrigir=0.0, janela=330):
    linhas = []
    for i in range(n):
        dt_nasc = inicio + timedelta(days=rnd.randint(0, janela))
        corrige = rnd.random() < corrigir
        p = 0.0 if corrige else 1.0
        gest = rnd.choices(["5", "4", "6", "3", "2", "1"], weights=[70, 15, 6, 5, 3, 1])[0]
        peso_base = {"1": 500, "2": 900, "3": 1600, "4": 2400, "5": 3200, "6": 3500}[gest]
        peso = max(300, int(rnd.gauss(peso_base, 420)))
        atraso = rnd.choice([2, 5, 10, 18, 25, 33, 48, 80])
        linhas.append({
            "NUMERODN": f"{31000000 + i}",
            "LOCNASC": talvez(rnd, 0.04 * p, rnd.choice(["1", "1", "1", "2", "3"]), "9"),
            "CODESTAB": talvez(rnd, 0.08 * p, rnd.choice(CNES), ""),
            "CODMUNNASC": "292740",
            "DTNASC": data_br(dt_nasc),
            "HORANASC": talvez(rnd, 0.1 * p, f"{rnd.randint(0, 23):02d}{rnd.randint(0, 59):02d}", "9999"),
            "SEXO": rnd.choice(["1", "2"]),
            "PESO": talvez(rnd, 0.03 * p, str(peso), "0"),
            "APGAR1": talvez(rnd, 0.12 * p, str(rnd.randint(5, 9)), "99"),
            "APGAR5": talvez(rnd, 0.12 * p, str(rnd.randint(7, 10)), "99"),
            "RACACOR": talvez(rnd, 0.2 * p, rnd.choice(["1", "2", "3", "4", "5"]), "9"),
            "IDANOMAL": talvez(rnd, 0.08 * p, rnd.choices(["2", "1"], weights=[97, 3])[0], "9"),
            "CODANOMAL": "",
            "IDADEMAE": str(rnd.randint(13, 45)),
            "ESTCIVMAE": talvez(rnd, 0.2 * p, rnd.choice(["1", "2", "5"]), "9"),
            "ESCMAE": talvez(rnd, 0.25 * p, rnd.choice(["2", "3", "4", "5"]), "9"),
            "RACACORMAE": talvez(rnd, 0.3 * p, rnd.choice(["1", "2", "4"]), ""),
            "CODOCUPMAE": talvez(rnd, 0.35 * p, f"{rnd.randint(1000, 999999)}", ""),
            "CODMUNRES": talvez(rnd, 0.02 * p, "292740", "2927408"),
            "QTDFILVIVO": talvez(rnd, 0.15 * p, str(rnd.randint(0, 5)), "99"),
            "QTDFILMORT": talvez(rnd, 0.2 * p, str(rnd.randint(0, 2)), "99"),
            "QTDGESTANT": str(rnd.randint(0, 4)),
            "QTDPARTNOR": str(rnd.randint(0, 3)),
            "QTDPARTCES": str(rnd.randint(0, 3)),
            "GESTACAO": gest,
            "SEMAGESTAC": talvez(rnd, 0.25 * p, str(rnd.randint(28, 42)), "99"),
            "GRAVIDEZ": rnd.choices(["1", "2"], weights=[97, 3])[0],
            "PARTO": talvez(rnd, 0.03 * p, rnd.choice(["1", "2"]), "9"),
            "CONSULTAS": talvez(rnd, 0.06 * p, rnd.choices(["4", "3", "2", "1"],
                                                           weights=[65, 22, 9, 4])[0], "9"),
            "CONSPRENAT": talvez(rnd, 0.2 * p, str(rnd.randint(0, 12)), "99"),
            "MESPRENAT": talvez(rnd, 0.25 * p, str(rnd.randint(1, 6)), ""),
            "DTULTMENST": talvez(rnd, 0.4 * p, data_br(dt_nasc - timedelta(days=rnd.randint(250, 290))), ""),
            "TPMETESTIM": rnd.choice(["1", "2", "9"]),
            "TPAPRESENT": rnd.choice(["1", "1", "2", "9"]),
            "STTRABPART": rnd.choice(["1", "2", "3", "9"]),
            "STCESPARTO": rnd.choice(["1", "2", "3", "9"]),
            "TPNASCASSI": talvez(rnd, 0.1 * p, rnd.choice(["1", "2", "3"]), "9"),
            "TPFUNCRESP": rnd.choice(["1", "2", "9"]),
            "DTDECLARAC": data_br(dt_nasc + timedelta(days=rnd.randint(0, 12))),
            "DTCADASTRO": data_br(dt_nasc + timedelta(days=atraso if not corrige else min(atraso, 22))),
            "NOMEMAE": talvez(rnd, 0.04 * p, nome(rnd), ""),
            "NOMERN": talvez(rnd, 0.5, "RN DE " + nome(rnd), ""),
        })
        if linhas[-1]["IDANOMAL"] == "1":
            linhas[-1]["CODANOMAL"] = talvez(rnd, 0.4 * p, f"Q{rnd.randint(10, 99)}", "")
        if not corrige and rnd.random() < 0.012:  # Apgar trocado
            linhas[-1]["APGAR1"], linhas[-1]["APGAR5"] = "9", "5"
        if not corrige and rnd.random() < 0.01:   # peso incoerente com a gestação
            linhas[-1]["GESTACAO"], linhas[-1]["PESO"] = "5", "800"
    return linhas


def registros_sinan(rnd, n, inicio, corrigir=0.0, janela=320):
    linhas = []
    for i in range(n):
        dt_sintoma = inicio + timedelta(days=rnd.randint(0, janela))
        corrige = rnd.random() < corrigir
        p = 0.0 if corrige else 1.0
        atraso_not = rnd.choice([0, 1, 2, 4, 6, 9, 15, 28, 45])
        dt_notif = dt_sintoma + timedelta(days=atraso_not if not corrige else min(atraso_not, 6))
        dt_digita = dt_notif + timedelta(days=rnd.choice([0, 1, 2, 3, 5, 9, 14]))
        sexo = rnd.choice(["M", "F"])
        classi = talvez(rnd, 0.2 * p, rnd.choice(["1", "2", "4", "5"]), "")
        linha = {
            "TP_NOT": "2",
            "ID_AGRAVO": talvez(rnd, 0.02 * p, rnd.choice(CID_AGRAVO), "ZZZ"),
            "NU_NOTIFIC": f"{5000000 + i}",
            "DT_NOTIFIC": data_br(dt_notif),
            "SEM_NOT": f"{dt_notif.year}{dt_notif.isocalendar()[1]:02d}",
            "NU_ANO": str(dt_notif.year),
            "SG_UF_NOT": "29",
            "ID_MUNICIP": "292740",
            "ID_REGIONA": "",
            "ID_UNIDADE": talvez(rnd, 0.05 * p, rnd.choice(CNES), ""),
            "DT_SIN_PRI": data_br(dt_sintoma),
            "SEM_PRI": f"{dt_sintoma.year}{dt_sintoma.isocalendar()[1]:02d}",
            "NM_PACIENT": nome(rnd),
            "DT_NASC": data_br(dt_sintoma - timedelta(days=rnd.randint(365, 32000))),
            "NU_IDADE_N": f"4{rnd.randint(1, 89):03d}",
            "CS_SEXO": sexo,
            "CS_GESTANT": "6" if sexo == "M" else talvez(rnd, 0.3 * p,
                                                         rnd.choice(["1", "2", "3", "5"]), "9"),
            "CS_RACA": talvez(rnd, 0.28 * p, rnd.choice(["1", "2", "4"]), "9"),
            "CS_ESCOL_N": talvez(rnd, 0.45 * p, rnd.choice(["1", "3", "6", "8"]), "9"),
            "NU_CNS": talvez(rnd, 0.35 * p, "7" + "".join(str(rnd.randint(0, 9)) for _ in range(14)), ""),
            "NM_MAE_PAC": talvez(rnd, 0.15 * p, nome(rnd), ""),
            "SG_UF": "29",
            "ID_MN_RESI": talvez(rnd, 0.02 * p, "292740", "29274"),
            "ID_BAIRRO": talvez(rnd, 0.25 * p, rnd.choice(BAIRROS), ""),
            "NM_BAIRRO": "",
            "NU_CEP": talvez(rnd, 0.3 * p, f"4{rnd.randint(1000000, 1999999)}", ""),
            "CS_ZONA": talvez(rnd, 0.2 * p, rnd.choice(["1", "2"]), "9"),
            "ID_PAIS": "1",
            "DT_INVEST": talvez(rnd, 0.4 * p, data_br(dt_notif + timedelta(days=rnd.randint(0, 20))), ""),
            "ID_OCUPA_N": talvez(rnd, 0.5 * p, f"{rnd.randint(1000, 999999)}", ""),
            "CLASSI_FIN": classi,
            "CRITERIO": "",
            "EVOLUCAO": "",
            "DT_OBITO": "",
            "DT_ENCERRA": "",
            "DT_DIGITA": data_br(dt_digita),
            "DT_TRANSUS": data_br(dt_digita + timedelta(days=rnd.randint(0, 5))),
            "CS_FLXRET": "0",
            "NDUPLIC_N": rnd.choices(["0", "1"], weights=[99, 1])[0],
        }
        if classi:
            linha["EVOLUCAO"] = talvez(rnd, 0.25 * p, rnd.choice(["1", "1", "2", "3"]), "")
            linha["DT_ENCERRA"] = talvez(
                rnd, 0.2 * p, data_br(dt_notif + timedelta(days=rnd.choice([20, 40, 55, 75, 120]))), "")
            if classi in ("1", "4", "5"):
                linha["CRITERIO"] = talvez(rnd, 0.3 * p, rnd.choice(["1", "2", "3"]), "")
            if linha["EVOLUCAO"] in ("2", "3"):
                linha["DT_OBITO"] = talvez(
                    rnd, 0.35 * p, data_br(dt_sintoma + timedelta(days=rnd.randint(1, 60))), "")
        if not corrige and rnd.random() < 0.01:   # homem gestante
            linha["CS_SEXO"], linha["CS_GESTANT"] = "M", "2"
        linhas.append(linha)
    return linhas


GERADORES = {
    "SIM": registros_sim,
    "SINASC": registros_sinasc,
    "SINAN": registros_sinan,
}


def escrever(caminho, linhas):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    cabecalho = list(linhas[0].keys())
    with open(caminho, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cabecalho, delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    return caminho


def gerar(pasta="exemplos/bases", registros=3000, semente=20260807):
    inicio = date.today() - timedelta(days=400)
    saidas = []
    for sigla, gerador in GERADORES.items():
        rnd = random.Random(semente)
        envio1 = gerador(rnd, registros, inicio)
        # duplicidades propositais no envio 1
        for _ in range(max(3, registros // 200)):
            envio1.append(dict(rnd.choice(envio1)))
        saidas.append(escrever(os.path.join(pasta, f"{sigla}_envio1.csv"), envio1))

        # envio 2: base acumulada — mesmos registros com parte dos erros corrigidos
        rnd2 = random.Random(semente)
        envio2 = gerador(rnd2, registros, inicio, corrigir=0.45)
        rnd3 = random.Random(semente + 999)
        novos = gerador(rnd3, max(200, registros // 5), date.today() - timedelta(days=75), janela=45)
        for j, linha in enumerate(novos):  # chaves novas, sem colidir com as antigas
            chave = "NUMERODO" if sigla == "SIM" else ("NUMERODN" if sigla == "SINASC"
                                                       else "NU_NOTIFIC")
            linha[chave] = str(int(linha[chave]) + 500000 + j)
        envio2.extend(novos)
        for _ in range(max(2, registros // 400)):
            envio2.append(dict(rnd2.choice(envio2)))
        saidas.append(escrever(os.path.join(pasta, f"{sigla}_envio2.csv"), envio2))
    return saidas


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Gera bases fictícias para teste do QualiSIS")
    ap.add_argument("--pasta", default="exemplos/bases")
    ap.add_argument("--registros", type=int, default=3000)
    ap.add_argument("--semente", type=int, default=20260807)
    args = ap.parse_args()
    for caminho in gerar(args.pasta, args.registros, args.semente):
        print(f"gerado: {caminho}")
