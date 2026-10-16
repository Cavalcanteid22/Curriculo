# -*- coding: utf-8 -*-
"""Verifica se cada categoria é atribuída ao caso que a define."""

from datetime import date

from pareamento_siclom_sinan import Notificacao, Usuario, classificar

# Base de notificações fictícia, construída para exercitar as sete categorias.
NOTIFICACOES = [
    Notificacao("0000100", "MARIA JOSE DA SILVA", "ANA SILVA", date(1980, 5, 10)),
    Notificacao("0000200", "JOAO PEDRO SANTOS", "RITA SANTOS", date(1975, 3, 22)),
    Notificacao("0000300", "CARLA MENDES LIMA", "LUCIA LIMA", date(1990, 8, 1)),
    Notificacao("0000400", "PAULO ROBERTO DIAS", "EDNA DIAS", date(1968, 12, 5)),
    Notificacao("0000500", "TEREZA CRISTINA ROCHA", "IVONE ROCHA", date(1988, 2, 14)),
]

CASOS = [
    # (descrição, usuário, categoria esperada)
    ("número declarado e confere",
     Usuario("u1", "MARIA JOSE DA SILVA", "ANA SILVA", date(1980, 5, 10), "100"),
     "1"),
    ("número declarado com zeros à esquerda",
     Usuario("u1b", "MARIA JOSE DA SILVA", "ANA SILVA", date(1980, 5, 10), "0000100"),
     "1"),
    ("número inexistente, mas nome e data conferem",
     Usuario("u2", "JOAO PEDRO SANTOS", "RITA SANTOS", date(1975, 3, 22), "999999"),
     "2"),
    ("sem número, nome e data conferem",
     Usuario("u3", "CARLA MENDES LIMA", "LUCIA LIMA", date(1990, 8, 1), ""),
     "3"),
    ("sem número, nome confere, data diverge",
     Usuario("u4a", "PAULO ROBERTO DIAS", "EDNA DIAS", date(1970, 1, 1), ""),
     "4A"),
    ("número existe mas é de outro paciente",
     Usuario("u4b", "FERNANDO ALVES COSTA", "MARTA COSTA", date(1995, 6, 30), "500"),
     "4B"),
    ("número inexistente, nome similar, data diverge",
     Usuario("u5", "TEREZA CRISTINA ROCHA", "IVONE ROCHA", date(1991, 9, 9), "888888"),
     "5"),
    ("número inexistente e nenhum nome parecido",
     Usuario("u6", "RICARDO NUNES BARROS", "SONIA BARROS", date(1982, 4, 4), "777777"),
     "6"),
    ("sem número e sem correspondência",
     Usuario("u7", "BEATRIZ GOMES PIRES", "CLARA PIRES", date(1993, 7, 19), ""),
     "7"),
]

print("%-46s %-9s %-9s %s" % ("CASO", "ESPERADO", "OBTIDO", "SITUAÇÃO"))
print("-" * 86)
falhas = 0
for descricao, usuario, esperado in CASOS:
    r = classificar(usuario, NOTIFICACOES)
    ok = r.codigo == esperado
    falhas += 0 if ok else 1
    print("%-46s %-9s %-9s %s" % (descricao[:46], esperado, r.codigo,
                                  "ok" if ok else "DIVERGE"))

print("-" * 86)
print("%d de %d casos corretos" % (len(CASOS) - falhas, len(CASOS)))
raise SystemExit(1 if falhas else 0)
