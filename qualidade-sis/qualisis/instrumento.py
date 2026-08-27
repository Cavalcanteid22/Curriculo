"""Instrumento de avaliação qualitativa (planilha com fórmulas).

Boa parte dos atributos listados pelo setor não está *dentro* da base — clareza,
acessibilidade, segurança, tempo de resposta, utilidade, simplicidade. Esses
atributos se avaliam com um instrumento estruturado, aplicado periodicamente
sobre o sistema, com evidência registrada.

A planilha gerada tem lista suspensa de 1 a 5, fórmulas de escore ponderado que
o Excel recalcula sozinho e formatação condicional que pinta a nota conforme o
desempenho — é a parte "planilha com fórmula" do trabalho.
"""

from __future__ import annotations

from datetime import datetime

from . import tipos as T
from .xlsxmin import Formula, LivroExcel

ESCALA = [
    (1, "Muito insatisfatório", "O atributo praticamente não é atendido; há prejuízo direto ao trabalho."),
    (2, "Insatisfatório", "Atendido de forma precária; exige contorno manual frequente."),
    (3, "Regular", "Atendido parcialmente; funciona, mas com limitações relevantes."),
    (4, "Bom", "Atendido na maior parte das situações; limitações pontuais."),
    (5, "Muito bom", "Plenamente atendido; não gera retrabalho nem dúvida."),
]

PESOS_PADRAO = {
    "Segurança": 3.0, "Acessibilidade": 3.0, "Utilidade": 3.0, "Tempo de resposta": 2.0,
    "Compreensibilidade": 2.0, "Interpretabilidade": 2.0, "Credibilidade": 2.5,
    "Relevância": 2.5, "Importância": 2.0, "Clareza": 2.0, "Legibilidade": 1.5,
    "Simplicidade": 2.0, "Localizabilidade": 1.5, "Concisão": 1.0, "Pertinência": 2.0,
    "Significância": 1.5, "Conveniência": 1.5, "Imparcialidade": 1.5,
}

VERDE, AMARELO, VERMELHO = "D8F0D8", "FCE7A8", "F4B9B8"


def gerar_instrumento(cfg, caminho, indicadores=None, escore_automatico=None):
    """Gera a planilha do instrumento qualitativo para um sistema."""
    livro = LivroExcel(caminho)
    livro.registrar_cor(VERDE, "verde")
    livro.registrar_cor(AMARELO, "amarelo")
    livro.registrar_cor(VERMELHO, "vermelho")
    livro.registrar_cor("EAF1FB", "destaque")

    _aba_orientacoes(livro, cfg)
    linha_inicial, linha_final, aba_nome = _aba_instrumento(livro, cfg)
    _aba_escala(livro)
    _aba_indicadores(livro, cfg, indicadores, escore_automatico, aba_nome,
                     linha_inicial, linha_final)
    _aba_plano(livro, cfg)
    livro.reordenar(["Orientações", "Instrumento", "Escala", "Escore consolidado",
                     "Plano de ação"])
    livro.fechar()
    return caminho


# --------------------------------------------------------------------------- #
def _aba_orientacoes(livro, cfg):
    texto = [
        ("Para que serve", "Avaliar, com evidência, os atributos de qualidade que não podem "
         "ser medidos diretamente na base de dados exportada."),
        ("Quem preenche", "Técnico responsável pelo sistema na Subcoordenadoria de Informação "
         "em Saúde, preferencialmente em dupla, com validação da coordenação."),
        ("Periodicidade", "Trimestral, e sempre que houver mudança de versão do sistema."),
        ("Como preencher", "Na aba 'Instrumento', escolha a nota de 1 a 5 na lista suspensa da "
         "coluna D. A cor da célula muda sozinha. Registre SEMPRE a evidência observada na "
         "coluna G — sem evidência, a nota não é auditável."),
        ("Como o escore é calculado", "Escore = soma(nota × peso) ÷ soma(pesos), convertido "
         "para base 100 (multiplicado por 20). As fórmulas já estão prontas."),
        ("Escore final do sistema", "A aba 'Escore consolidado' combina este resultado "
         "qualitativo com o escore automático calculado sobre a base de dados."),
        ("Uso do resultado", "Alimenta o relatório trimestral do setor, o plano de ação da aba "
         "'Plano de ação' e a série histórica de acompanhamento."),
    ]
    with livro.aba("Orientações", larguras=[30, 96], congelar_linhas=3,
                   autofiltro=False) as ab:
        ab.linha([f"Instrumento de avaliação qualitativa — {cfg.sigla}"], estilo_geral="titulo")
        ab.linha([cfg.nome])
        ab.linha([cfg.orgao])
        ab.linha_vazia()
        ab.linha(["Item", "Orientação"], estilo_geral="cabecalho")
        for chave, valor in texto:
            ab.linha([chave, valor], estilos=["negrito", "envolver"])


def _aba_instrumento(livro, cfg):
    atributos = T.ATRIBUTOS_INSTRUMENTO
    nome = "Instrumento"
    with livro.aba(nome, larguras=[24, 52, 44, 10, 8, 14, 46, 20, 14],
                   congelar_linhas=6, congelar_colunas=1) as ab:
        ab.linha([f"Avaliação qualitativa — {cfg.sigla}"], estilo_geral="titulo")
        ab.linha([cfg.nome])
        ab.linha(["Avaliador(es):", "", "Data da avaliação:", "",
                  "Período de referência:", ""], estilo_geral="negrito")
        ab.linha(["Versão do sistema avaliada:", "", "Validado por:", ""],
                 estilo_geral="negrito")
        ab.linha_vazia()
        ab.linha(["Atributo", "Definição operacional", "Evidência a verificar",
                  "Nota (1-5)", "Peso", "Nota ponderada", "Evidência observada / justificativa",
                  "Responsável", "Data"], estilo_geral="cabecalho")
        primeira = ab.n_linhas + 1
        for atributo in atributos:
            linha_atual = ab.n_linhas + 1
            peso = PESOS_PADRAO.get(atributo.nome, 1.5)
            ab.linha([
                atributo.nome, atributo.definicao,
                "; ".join(atributo.evidencias) or "definir evidência",
                "", peso,
                Formula(f'IF(D{linha_atual}="","",D{linha_atual}*E{linha_atual})'),
                "", "", "",
            ], estilos=["negrito", "envolver", "envolver", None, None, None,
                        "envolver", None, None])
        ultima = ab.n_linhas
        total = ultima + 1
        ab.linha(["TOTAL", "", "", "",
                  Formula(f"SUM(E{primeira}:E{ultima})"),
                  Formula(f"SUM(F{primeira}:F{ultima})"), "", "", ""],
                 estilo_geral="negrito")
        ab.linha(["ESCORE QUALITATIVO (0 a 100)", "", "", "", "",
                  Formula(f'IF(E{total}=0,"",F{total}/E{total}*20)'), "", "", ""],
                 estilos=["negrito", None, None, None, None, "destaque", None, None, None])
        ab.linha(["Atributos avaliados", "", "", Formula(f"COUNT(D{primeira}:D{ultima})"),
                  "", "", f"de {len(atributos)} previstos"], estilos=["negrito"])

        faixa_nota = f"D{primeira}:D{ultima}"
        ab.formatacao_condicional(faixa_nota, f'AND($D{primeira}<>"",$D{primeira}<=2)', VERMELHO)
        ab.formatacao_condicional(faixa_nota, f"$D{primeira}=3", AMARELO)
        ab.formatacao_condicional(faixa_nota, f"$D{primeira}>=4", VERDE)
        # linha inteira em vermelho quando a nota for crítica e sem justificativa
        ab.formatacao_condicional(
            f"A{primeira}:I{ultima}",
            f'AND($D{primeira}<>"",$D{primeira}<=2,$G{primeira}="")', VERMELHO)
        ab.lista_suspensa(faixa_nota, [1, 2, 3, 4, 5])
    return primeira, ultima, nome


def _aba_escala(livro):
    with livro.aba("Escala", larguras=[10, 28, 86], congelar_linhas=2, autofiltro=False) as ab:
        ab.linha(["Escala de avaliação (1 a 5)"], estilo_geral="titulo")
        ab.linha(["Nota", "Significado", "Descritor"], estilo_geral="cabecalho")
        cores = {1: "vermelho", 2: "vermelho", 3: "amarelo", 4: "verde", 5: "verde"}
        for nota, rotulo, descritor in ESCALA:
            ab.linha([nota, rotulo, descritor],
                     estilos=[cores[nota], cores[nota], "envolver"])
        ab.linha_vazia()
        ab.linha(["Regra de ouro: nota sem evidência registrada não é válida — "
                  "a linha fica vermelha até a evidência ser preenchida."],
                 estilo_geral="negrito")


def _aba_indicadores(livro, cfg, indicadores, escore_automatico, aba_instrumento,
                     linha_inicial, linha_final):
    with livro.aba("Escore consolidado", larguras=[34, 14, 16, 60],
                   congelar_linhas=2, autofiltro=False) as ab:
        ab.linha([f"Escore consolidado da qualidade — {cfg.sigla}"], estilo_geral="titulo")
        ab.linha(["Componente", "Valor (%)", "Peso", "Origem"], estilo_geral="cabecalho")
        linha_auto = ab.n_linhas + 1
        ab.linha(["Atributos medidos na base (automático)",
                  escore_automatico if escore_automatico is not None else "",
                  2.0, "Calculado pelo QualiSIS sobre o CSV do sistema"])
        linha_qual = ab.n_linhas + 1
        ab.linha(["Atributos avaliados por instrumento (qualitativo)",
                  Formula(f"'{aba_instrumento}'!F{linha_final + 2}"), 1.0,
                  "Aba 'Instrumento' desta planilha"])
        linha_final_escore = ab.n_linhas + 1
        ab.linha(["ESCORE FINAL DO SISTEMA",
                  Formula(f"IFERROR((B{linha_auto}*C{linha_auto}+B{linha_qual}*C{linha_qual})"
                          f'/(C{linha_auto}+C{linha_qual}),"")'),
                  "", "Média ponderada dos dois componentes"],
                 estilos=["negrito", "destaque", None, None])
        ab.formatacao_condicional(f"B{linha_auto}:B{linha_final_escore}",
                                  f'AND($B{linha_auto}<>"",$B{linha_auto}<80)', VERMELHO)
        ab.formatacao_condicional(f"B{linha_auto}:B{linha_final_escore}",
                                  f'AND($B{linha_auto}>=80,$B{linha_auto}<90)', AMARELO)
        ab.formatacao_condicional(f"B{linha_auto}:B{linha_final_escore}",
                                  f"$B{linha_auto}>=90", VERDE)
        ab.linha_vazia()
        ab.linha(["Indicadores automáticos da última execução"], estilo_geral="negrito")
        ab.linha(["Atributo", "Valor (%)", "Classificação", "Como é calculado"],
                 estilo_geral="cabecalho")
        for nome, dados in (indicadores or {}).items():
            ab.linha([nome, dados.get("valor"), dados.get("classificacao"),
                      dados.get("formula")], estilos=[None, None, None, "envolver"])
        if not indicadores:
            ab.linha(["(execute a análise da base para preencher automaticamente)"])


def _aba_plano(livro, cfg):
    with livro.aba("Plano de ação", larguras=[22, 46, 46, 22, 14, 16, 30],
                   congelar_linhas=2) as ab:
        ab.linha(["Atributo / achado", "Problema identificado", "Ação pactuada",
                  "Responsável", "Prazo", "Situação", "Observações"],
                 estilo_geral="cabecalho")
        exemplos = [
            ["Completude", "Campo de escolaridade em branco em parte das notificações",
             "Devolutiva às unidades com maior lacuna e reforço no treinamento",
             "", "", "Não iniciada", ""],
            ["Tempestividade", "Digitação fora do prazo pactuado",
             "Monitoramento semanal e alerta às unidades atrasadas", "", "",
             "Não iniciada", ""],
            ["Singularidade", "Registros duplicados na base acumulada",
             "Rotina mensal de identificação e exclusão de duplicidades", "", "",
             "Não iniciada", ""],
        ]
        for linha in exemplos:
            ab.linha(linha)
        for _ in range(40):
            ab.linha(["", "", "", "", "", "", ""])
        ultima = ab.n_linhas
        ab.lista_suspensa(f"F2:F{ultima}",
                          ["Não iniciada", "Em andamento", "Concluída", "Cancelada"])
        ab.formatacao_condicional(f"A2:G{ultima}", '$F2="Concluída"', VERDE)
        ab.formatacao_condicional(f"A2:G{ultima}", '$F2="Em andamento"', AMARELO)
        ab.formatacao_condicional(f"A2:G{ultima}", '$F2="Não iniciada"', VERMELHO)
        ab.linha_vazia()
        ab.linha([f"Gerado em {datetime.now().strftime('%d/%m/%Y')} — {cfg.orgao}"])
