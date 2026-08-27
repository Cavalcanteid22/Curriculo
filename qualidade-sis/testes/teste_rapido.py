#!/usr/bin/env python3
"""Teste rápido de fumaça: roda o fluxo inteiro em bases fictícias e confere
os pontos que não podem quebrar. Use depois de editar qualquer configuração.

    python testes/teste_rapido.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from exemplos.gerar_exemplos import gerar            # noqa: E402
from qualisis import config as config_mod            # noqa: E402
from qualisis import consolidado, processamento      # noqa: E402
from qualisis.instrumento import gerar_instrumento   # noqa: E402
from qualisis.regras import valido_cid10, valido_cns, valido_cpf  # noqa: E402

falhas = []


def checar(condicao, descricao):
    marca = "ok  " if condicao else "FALHA"
    print(f"  [{marca}] {descricao}")
    if not condicao:
        falhas.append(descricao)


def main():
    tmp = tempfile.mkdtemp(prefix="qualisis_teste_")
    try:
        print("\n1. Configurações")
        siglas = config_mod.listar()
        checar(len(siglas) >= 5, f"5 sistemas configurados (encontrados: {len(siglas)})")
        for sigla in siglas:
            cfg = config_mod.carregar(sigla)
            checar(bool(cfg.campos), f"{cfg.sigla}: dicionário de campos carregado")
            checar(bool(cfg.chave_registro), f"{cfg.sigla}: chave de registro definida")

        print("\n2. Validadores")
        checar(valido_cpf("11144477735"), "CPF válido reconhecido")
        checar(not valido_cpf("11111111111"), "CPF inválido rejeitado")
        checar(valido_cid10("I219") and not valido_cid10("XX99"), "CID-10 validado")
        checar(not valido_cns("123"), "CNS curto rejeitado")

        print("\n3. Bases de exemplo")
        bases = gerar(os.path.join(tmp, "bases"), registros=800)
        checar(len(bases) == 6, "6 arquivos gerados (2 envios × 3 sistemas)")

        print("\n4. Análise do 1º envio")
        r1 = processamento.executar(
            "sim", os.path.join(tmp, "bases", "SIM_envio1.csv"),
            pasta_saida=os.path.join(tmp, "saida"),
            pasta_historico=os.path.join(tmp, "historico"), silencioso=True)
        checar(r1["agregador"].n_registros > 0, "registros lidos")
        checar(r1["agregador"].n_ocorrencias > 0, "inconsistências detectadas")
        checar(0 <= (r1["escore"] or -1) <= 100, f"escore no intervalo válido ({r1['escore']})")
        xlsx = os.path.join(r1["destino"], "SIM_inconsistencias.xlsx")
        checar(os.path.exists(xlsx), "planilha gerada")
        with zipfile.ZipFile(xlsx) as z:
            checar(z.testzip() is None, "planilha íntegra (estrutura .xlsx válida)")
            checar("xl/styles.xml" in z.namelist(), "estilos (cores) presentes")
        checar(os.path.exists(os.path.join(r1["destino"], "SIM_relatorio.html")),
               "relatório HTML gerado")

        print("\n5. Análise do 2º envio (resolutividade)")
        r2 = processamento.executar(
            "sim", os.path.join(tmp, "bases", "SIM_envio2.csv"),
            pasta_saida=os.path.join(tmp, "saida"),
            pasta_historico=os.path.join(tmp, "historico"), silencioso=True)
        comp = r2["comparador"]
        checar(comp is not None and comp.disponivel, "comparação com o envio anterior ativa")
        if comp and comp.disponivel:
            checar(comp.total_corrigidas > 0, "ocorrências corrigidas identificadas")
            checar(comp.registros_novos > 0, "registros novos identificados")
            checar(comp.taxa_resolutividade is not None, "taxa de resolutividade calculada")
            checar(comp.registros_ausentes == 0,
                   "nenhum registro do envio anterior sumiu (base acumulativa)")

        print("\n6. Demais sistemas")
        for sigla in ("sinasc", "sinan"):
            base = os.path.join(tmp, "bases", f"{sigla.upper()}_envio1.csv")
            r = processamento.executar(sigla, base, pasta_saida=os.path.join(tmp, "saida"),
                                       pasta_historico=os.path.join(tmp, "historico"),
                                       silencioso=True)
            checar(r["agregador"].n_registros > 0, f"{sigla.upper()}: base processada")

        print("\n7. Instrumento e painel consolidado")
        inst = gerar_instrumento(r1["config"], os.path.join(tmp, "instrumento.xlsx"),
                                 indicadores=r1["indicadores"], escore_automatico=r1["escore"])
        with zipfile.ZipFile(inst) as z:
            checar("xl/worksheets/sheet2.xml" in z.namelist(), "instrumento com várias abas")
            xml = z.read("xl/worksheets/sheet2.xml").decode("utf-8")
            checar("<f>" in xml, "instrumento contém fórmulas")
            checar("dataValidation" in xml, "instrumento contém lista suspensa")
            checar("conditionalFormatting" in xml, "instrumento contém formatação condicional")
        painel = consolidado.gerar_consolidado(os.path.join(tmp, "historico"),
                                               os.path.join(tmp, "painel.html"))
        checar(os.path.getsize(painel) > 5000, "painel consolidado gerado")

        print("\n" + "=" * 62)
        if falhas:
            print(f"{len(falhas)} verificação(ões) falharam:")
            for f in falhas:
                print(f"  - {f}")
            return 1
        print("Todas as verificações passaram.")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
