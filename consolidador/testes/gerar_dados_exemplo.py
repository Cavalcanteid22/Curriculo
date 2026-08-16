"""Gera arquivos de exemplo dos dois sistemas, com problemas propositais.

Serve para testar a rotina inteira sem depender de dados reais:

    python testes/gerar_dados_exemplo.py exemplos/entradas
"""

from __future__ import annotations

import csv
import datetime as _dt
import os
import random
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nucleo.xlsx_writer import Estilo, Planilha  # noqa: E402

NOMES = [
    "Ana Paula Souza", "Bruno Carvalho Lima", "Carla Mendes Rocha", "Diego Alves Pinto",
    "Elaine Ferreira Dias", "Fabio Nogueira Cruz", "Gabriela Santos Melo", "Hugo Barros Teixeira",
    "Isabela Ramos Freitas", "Joao Vitor Moreira", "Karina Lopes Batista", "Lucas Andrade Farias",
    "Mariana Coelho Duarte", "Nelson Ribeiro Gomes", "Olivia Martins Braga", "Paulo Cesar Aguiar",
    "Queila Vasconcelos Sa", "Rafael Monteiro Prado", "Simone Cardoso Neves", "Tiago Fonseca Vieira",
    "Ursula Campos Tavares", "Vinicius Peixoto Reis", "Wanda Siqueira Amaral", "Xavier Nunes Padilha",
    "Yara Bastos Correia", "Zeca Pagodinho Silva", "Amanda Rezende Cunha", "Bernardo Leal Pires",
    "Cristiane Aparecida Luz", "Daniel Estevao Rangel", "Erica Bonfim Sales", "Felipe Torres Guedes",
]
CARGOS = ["Assistente Administrativo", "Analista de Compras", "Auxiliar Financeiro",
          "Coordenador de Contratos", "Tecnico de Suporte", "Assessor de Planejamento"]
SITUACOES = ["ATIVO", "SUSPENSO", "ENCERRADO"]
LOTACOES = ["Diretoria Administrativa", "Gerencia de Contratos", "Nucleo Financeiro",
            "Coordenacao de Compras"]


def digitos_cpf(base: str) -> str:
    numeros = [int(c) for c in base]
    for tamanho in (9, 10):
        soma = sum(numeros[i] * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11
        numeros.append(0 if digito == 10 else digito)
    return "".join(str(n) for n in numeros)


def formatar_cpf(numeros: str) -> str:
    return f"{numeros[:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:]}"


def montar_base(quantidade: int = 32):
    aleatorio = random.Random(20260816)
    registros = []
    for indice in range(quantidade):
        cpf = digitos_cpf(f"{aleatorio.randint(100000000, 999999999)}")
        registros.append({
            "cpf": cpf,
            "matricula": f"{40000 + indice}",
            "nome": NOMES[indice % len(NOMES)],
            "cargo": aleatorio.choice(CARGOS),
            "lotacao": aleatorio.choice(LOTACOES),
            "admissao": _dt.date(2019, 1, 1) + _dt.timedelta(days=aleatorio.randint(0, 2200)),
            "valor": round(aleatorio.uniform(1800, 9800), 2),
            "situacao": aleatorio.choice(SITUACOES),
            "email": f"usuario{indice}@orgao.gov.br",
        })
    return registros


def gerar(pasta: str) -> None:
    os.makedirs(pasta, exist_ok=True)
    base = montar_base()

    # ---- Sistema SIGA: dois CSV e uma planilha ---------------------------
    siga = [dict(r) for r in base[:26]]
    siga[3]["cpf"] = ""                                   # chave em branco
    siga[5]["cpf"] = "111.111.111-11"                     # CPF invalido
    siga[7]["nome"] = "  Gabriela   Santos  Melo "        # espacos extras
    siga[9]["valor"] = 987654.32                          # outlier
    siga[11]["admissao"] = _dt.date(1899, 5, 4)           # data implausivel
    siga[13]["email"] = "sem-arroba.gov.br"               # e-mail invalido
    siga.append(dict(siga[2]))                            # registro duplicado
    siga.append({**base[26], "matricula": base[1]["matricula"]})  # matricula repetida

    _escrever_csv(os.path.join(pasta, "SIGA_servidores_2026-07.csv"), siga[:14])
    _escrever_csv(os.path.join(pasta, "SIGA_servidores_2026-08.csv"), siga[14:], delimitador=";")
    _escrever_xlsx(os.path.join(pasta, "SIGA_complemento.xlsx"), base[26:30])

    # ---- Sistema RHNET: um HTML e um DBF ---------------------------------
    rhnet = [dict(r) for r in base[:24]] + [dict(r) for r in base[30:]]
    rhnet[1]["cargo"] = "Analista de Compras Junior"       # divergencia de conteudo
    rhnet[4]["valor"] = round(base[4]["valor"] + 350.0, 2)  # divergencia de valor
    rhnet[6]["situacao"] = "ativo"                          # divergencia de grafia
    rhnet[8]["nome"] = "Isabela Ramos de Freitas"           # nome levemente diferente
    rhnet[8]["cpf"] = ""                                    # sem chave: forca o pareamento
    rhnet[8]["matricula"] = ""                              # aproximado por similaridade
    rhnet[8]["email"] = ""
    rhnet[12]["admissao"] = base[12]["admissao"] + _dt.timedelta(days=1)

    _escrever_html(os.path.join(pasta, "RHNET_relatorio_pessoal.html"), rhnet[:18])
    _escrever_dbf(os.path.join(pasta, "RHNET_cadastro.dbf"), rhnet[18:])
    print(f"Arquivos de exemplo gerados em: {os.path.abspath(pasta)}")


# --------------------------------------------------------------------------
# Gravadores por formato
# --------------------------------------------------------------------------


def _escrever_csv(caminho: str, registros, delimitador: str = ",") -> None:
    with open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=delimitador)
        escritor.writerow(["CPF", "MATRICULA", "NOME DO SERVIDOR", "CARGO", "LOTACAO",
                           "DT_ADMISSAO", "VALOR_BRUTO", "SITUACAO", "EMAIL"])
        for registro in registros:
            escritor.writerow([
                formatar_cpf(registro["cpf"]) if registro["cpf"] else "",
                registro["matricula"], registro["nome"], registro["cargo"], registro["lotacao"],
                registro["admissao"].strftime("%d/%m/%Y"),
                f"{registro['valor']:.2f}".replace(".", ","),
                registro["situacao"], registro["email"],
            ])


def _escrever_xlsx(caminho: str, registros) -> None:
    planilha = Planilha()
    aba = planilha.aba("Servidores")
    cabecalho = Estilo(negrito=True, fundo="D9E1F2", borda=True)
    aba.escrever_linha(["Relatorio complementar SIGA"], estilo=Estilo(negrito=True, tamanho=12))
    aba.escrever_linha([f"Emitido em {_dt.date.today():%d/%m/%Y}"])
    aba.pular_linha()
    aba.escrever_linha(["CPF", "MATRICULA", "NOME DO SERVIDOR", "CARGO", "LOTACAO",
                        "DT_ADMISSAO", "VALOR_BRUTO", "SITUACAO", "EMAIL"], estilo=cabecalho)
    for registro in registros:
        aba.escrever_linha([
            formatar_cpf(registro["cpf"]), registro["matricula"], registro["nome"],
            registro["cargo"], registro["lotacao"],
            registro["admissao"].strftime("%d/%m/%Y"), registro["valor"],
            registro["situacao"], registro["email"],
        ])
    aba.larguras_automaticas()
    planilha.salvar(caminho)


def _escrever_html(caminho: str, registros) -> None:
    linhas = "".join(
        "<tr>"
        f"<td>{formatar_cpf(r['cpf']) if r['cpf'] else ''}</td>"
        f"<td>{r['matricula']}</td><td>{r['nome']}</td><td>{r['cargo']}</td>"
        f"<td>{r['lotacao']}</td><td>{r['admissao']:%d/%m/%Y}</td>"
        f"<td>R$ {r['valor']:,.2f}</td><td>{r['situacao']}</td><td>{r['email']}</td>"
        "</tr>"
        for r in registros
    )
    conteudo = f"""<!DOCTYPE html>
<html lang="pt-br"><head><meta charset="utf-8"><title>RHNET - Relatorio de pessoal</title></head>
<body>
<h1>RHNET - Relatorio de pessoal</h1>
<p>Emitido em {_dt.date.today():%d/%m/%Y}</p>
<table border="1">
<thead><tr><th>Nr. CPF</th><th>Cod. Matricula</th><th>Nome completo</th><th>Funcao</th>
<th>Unidade</th><th>Data de admissao</th><th>Remuneracao</th><th>Status</th><th>E-mail</th></tr></thead>
<tbody>{linhas}</tbody>
</table>
</body></html>"""
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)


def _escrever_dbf(caminho: str, registros) -> None:
    campos = [
        ("NRCPF", "C", 14, 0), ("CODMATRIC", "C", 10, 0), ("NOMECOMPL", "C", 40, 0),
        ("FUNCAO", "C", 30, 0), ("UNIDADE", "C", 30, 0), ("DTADMISSA", "D", 8, 0),
        ("REMUNERAC", "N", 12, 2), ("STATUS", "C", 10, 0), ("EMAIL", "C", 40, 0),
    ]
    tamanho_registro = 1 + sum(c[2] for c in campos)
    hoje = _dt.date.today()
    cabecalho = struct.pack(
        "<BBBBLHH20x", 0x03, hoje.year - 1900, hoje.month, hoje.day,
        len(registros), 32 + 32 * len(campos) + 1, tamanho_registro,
    )
    with open(caminho, "wb") as arquivo:
        arquivo.write(cabecalho)
        for nome, tipo, tamanho, decimais in campos:
            arquivo.write(
                nome.encode("latin-1")[:11].ljust(11, b"\x00")
                + tipo.encode("latin-1") + b"\x00" * 4
                + bytes([tamanho, decimais]) + b"\x00" * 14
            )
        arquivo.write(b"\r")
        for registro in registros:
            valores = [
                formatar_cpf(registro["cpf"]) if registro["cpf"] else "",
                registro["matricula"], registro["nome"], registro["cargo"], registro["lotacao"],
                registro["admissao"].strftime("%Y%m%d"),
                f"{registro['valor']:.2f}".rjust(12), registro["situacao"], registro["email"],
            ]
            arquivo.write(b" ")
            for (nome, tipo, tamanho, _dec), valor in zip(campos, valores):
                arquivo.write(str(valor).encode("latin-1", "replace")[:tamanho].ljust(tamanho, b" "))
        arquivo.write(b"\x1a")


if __name__ == "__main__":
    destino = sys.argv[1] if len(sys.argv) > 1 else "exemplos/entradas"
    gerar(destino)
