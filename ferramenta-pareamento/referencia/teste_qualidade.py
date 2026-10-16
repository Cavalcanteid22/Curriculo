# -*- coding: utf-8 -*-
"""Verifica a medição de incompletude, as regras e as duplicidades."""

from datetime import date

from qualidade_sinan import (ALTA, BAIXA, ESSENCIAL, MEDIA, OBRIGATORIO,
                             Campo, classificar_incompletude,
                             detectar_duplicidades, medir_incompletude,
                             prioridade_da_pendencia, verificar_campos,
                             verificar_regras)

print("=== Escala de Romero e Cunha (2006) sobre a INCOMPLETUDE ===")
for valor, esperado in ((2.0, "Excelente"), (7.5, "Bom"), (15.0, "Regular"),
                        (35.0, "Ruim"), (80.0, "Muito ruim")):
    obtido = classificar_incompletude(valor)
    print("  %5.1f%% -> %-11s %s" % (valor, obtido,
                                     "ok" if obtido == esperado else "DIVERGE"))

print("\n=== Incompletude: branco e ignorado somados ===")
registros = [
    {"NU": "1", "CS_RACA": "1", "CLAS_ETIOL": "1", "CLASSI_FIN": "1"},
    {"NU": "2", "CS_RACA": "",  "CLAS_ETIOL": "2", "CLASSI_FIN": "1"},
    {"NU": "3", "CS_RACA": "9", "CLAS_ETIOL": "",  "CLASSI_FIN": "1"},
    {"NU": "4", "CS_RACA": "4", "CLAS_ETIOL": "",  "CLASSI_FIN": "2"},
]
raca = Campo("CS_RACA", "Raça/cor", ESSENCIAL)
m = medir_incompletude(registros, raca)
print("  CS_RACA: %d em branco + %d ignorado de %d = %.1f%% (%s)"
      % (m["em_branco"], m["ignorado"], m["populacao"], m["incompletude"],
         m["classificacao"]))
assert m["em_branco"] == 1 and m["ignorado"] == 1 and m["incompletude"] == 50.0

print("\n=== População aplicável: campo habilitado sob condição ===")
# A etiologia só se aplica aos casos confirmados (CLASSI_FIN = 1).
etiologia = Campo("CLAS_ETIOL", "Classificação etiológica", OBRIGATORIO,
                  aplicavel=lambda r: r.get("CLASSI_FIN") == "1",
                  regra_aplicabilidade="Apenas casos confirmados")
m = medir_incompletude(registros, etiologia)
print("  CLAS_ETIOL sobre a população aplicável: %d registros, %.1f%% (%s)"
      % (m["populacao"], m["incompletude"], m["classificacao"]))
m_todos = medir_incompletude(registros, Campo("CLAS_ETIOL", "", OBRIGATORIO))
print("  CLAS_ETIOL sobre a base inteira:        %d registros, %.1f%%"
      % (m_todos["populacao"], m_todos["incompletude"]))
print("  -> medir sobre a base inteira superestimaria a incompletude em %.1f p.p."
      % (m_todos["incompletude"] - m["incompletude"]))
assert m["populacao"] == 3 and m_todos["populacao"] == 4

print("\n=== Prioridade derivada da classe no dicionário ===")
casos = [(OBRIGATORIO, "Campo em branco", ALTA),
         (OBRIGATORIO, "Valor ignorado", MEDIA),
         (ESSENCIAL, "Campo em branco", MEDIA),
         ("Sem classificação no dicionário", "Campo em branco", BAIXA),
         (ESSENCIAL, "Violação de regra", ALTA)]
for classe, tipo, esperado in casos:
    obtido = prioridade_da_pendencia(classe, tipo)
    print("  %-32s %-18s -> %-6s %s"
          % (classe[:32], tipo, obtido, "ok" if obtido == esperado else "DIVERGE"))
    assert obtido == esperado

print("\n=== Regras de consistência do dicionário ===")
com_datas = [
    {"NU": "10", "DT_SIN_PRI": date(2026, 3, 10), "DT_NOTIFIC": date(2026, 3, 5),
     "DT_INVEST": date(2026, 3, 12), "DT_ENCERRA": date(2026, 4, 1)},
    {"NU": "11", "DT_SIN_PRI": date(2026, 1, 2), "DT_NOTIFIC": date(2026, 1, 5),
     "DT_INVEST": date(2026, 1, 8), "DT_ENCERRA": date(2026, 2, 1)},
]
for p in verificar_regras(com_datas, "NU"):
    print("  notificação %s: %s [%s]" % (p.registro, p.descricao, p.prioridade))
assert len(verificar_regras(com_datas, "NU")) == 1

print("\n=== Duplicidades e classificação pelo intervalo ===")
base = [
    {"NU_NOTIFIC": "A1", "NM_PACIENT": "MARIA JOSE DA SILVA",
     "NM_MAE_PAC": "ANA SILVA", "DT_NASC": date(1980, 5, 10),
     "DT_NOTIFIC": date(2026, 1, 10)},
    {"NU_NOTIFIC": "A2", "NM_PACIENT": "MARIA JOSE DA SILVA",
     "NM_MAE_PAC": "ANA SILVA", "DT_NASC": date(1980, 5, 10),
     "DT_NOTIFIC": date(2026, 1, 25)},   # 15 dias: lançamento duplicado
    {"NU_NOTIFIC": "A3", "NM_PACIENT": "MARIA JOSE SILVA",
     "NM_MAE_PAC": "ANA SILVA", "DT_NASC": date(1980, 5, 10),
     "DT_NOTIFIC": date(2027, 6, 1)},    # > 1 ano: provável renotificação
    {"NU_NOTIFIC": "B1", "NM_PACIENT": "CARLOS EDUARDO LIMA",
     "NM_MAE_PAC": "RITA LIMA", "DT_NASC": date(1975, 2, 2),
     "DT_NOTIFIC": date(2026, 5, 5)},
]
for par in sorted(detectar_duplicidades(base, "NU_NOTIFIC"),
                  key=lambda p: (p["a"], p["b"])):
    print("  %s x %s | %-9s nome %5.1f | %4s dias | %s"
          % (par["a"], par["b"], par["tipo"], par["escore_nome"],
             par["intervalo_dias"], par["classificacao"]))

print("\nTodas as verificações passaram.")
