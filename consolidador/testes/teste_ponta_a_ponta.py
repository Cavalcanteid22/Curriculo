"""Testes automatizados da rotina (nao exigem nenhuma biblioteca externa).

    python testes/teste_ponta_a_ponta.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nucleo import leitores, texto as tx  # noqa: E402
from nucleo.config import (CampoConfig, Perfil, RegraConsistencia, SistemaConfig,  # noqa: E402
                           perfil_padrao)
from nucleo.pipeline import executar  # noqa: E402
from nucleo.xlsx_writer import Estilo, Planilha  # noqa: E402
from testes.gerar_dados_exemplo import gerar  # noqa: E402


class TesteTexto(unittest.TestCase):
    def teste_cpf(self):
        self.assertTrue(tx.cpf_valido("529.982.247-25"))
        self.assertFalse(tx.cpf_valido("111.111.111-11"))
        self.assertFalse(tx.cpf_valido("529.982.247-26"))
        self.assertFalse(tx.cpf_valido("123"))

    def teste_cnpj(self):
        self.assertTrue(tx.cnpj_valido("11.222.333/0001-81"))
        self.assertFalse(tx.cnpj_valido("11.222.333/0001-82"))

    def teste_numeros(self):
        self.assertEqual(tx.para_numero("1.234,56"), 1234.56)
        self.assertEqual(tx.para_numero("1,234.56"), 1234.56)
        self.assertEqual(tx.para_numero("R$ 2.000,00"), 2000.0)
        self.assertEqual(tx.para_numero("(150,25)"), -150.25)
        self.assertIsNone(tx.para_numero("abc"))

    def teste_datas(self):
        self.assertEqual(tx.para_data("15/03/2024").isoformat(), "2024-03-15")
        self.assertEqual(tx.para_data("2024-03-15").isoformat(), "2024-03-15")
        self.assertEqual(tx.para_data("20240315").isoformat(), "2024-03-15")
        self.assertIsNone(tx.para_data("nao e data"))

    def teste_similaridade_nomes(self):
        self.assertGreater(tx.similaridade_nomes("NOMECOMPL", "Nome completo"), 0.79)
        self.assertGreater(tx.similaridade_nomes("DTADMISSA", "Data de admissao"), 0.79)
        self.assertGreater(tx.similaridade_nomes("Nr. CPF", "CPF"), 0.79)
        self.assertLess(tx.similaridade_nomes("Cargo", "Salario"), 0.7)

    def teste_normalizacao(self):
        self.assertEqual(tx.normalizar("  SÃO   PAULO/SP "), "sao paulo sp")
        self.assertEqual(tx.chave_cabecalho("Nr. CPF"), "nrcpf")


class TesteLeitores(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.mkdtemp(prefix="consolidador_leitores_")
        gerar(cls.pasta)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.pasta, ignore_errors=True)

    def _ler(self, nome: str):
        return leitores.ler_arquivo(os.path.join(self.pasta, nome))

    def teste_csv_com_bom_e_ponto_virgula(self):
        virgula = self._ler("SIGA_servidores_2026-07.csv")[0]
        ponto_virgula = self._ler("SIGA_servidores_2026-08.csv")[0]
        self.assertIn("CPF", virgula.colunas)
        self.assertIn("CPF", ponto_virgula.colunas)
        self.assertEqual(len(virgula.linhas), 14)

    def teste_xlsx_ignora_titulo_antes_do_cabecalho(self):
        tabela = self._ler("SIGA_complemento.xlsx")[0]
        self.assertIn("MATRICULA", tabela.colunas)
        self.assertEqual(len(tabela.linhas), 4)

    def teste_html(self):
        tabela = self._ler("RHNET_relatorio_pessoal.html")[0]
        self.assertIn("Nome completo", tabela.colunas)
        self.assertEqual(len(tabela.linhas), 18)

    def teste_dbf(self):
        tabela = self._ler("RHNET_cadastro.dbf")[0]
        self.assertIn("NOMECOMPL", tabela.colunas)
        self.assertEqual(len(tabela.linhas), 8)
        self.assertRegex(str(tabela.linhas[0]["DTADMISSA"]), r"\d{2}/\d{2}/\d{4}")

    def teste_json_e_xml(self):
        caminho_json = os.path.join(self.pasta, "extra.json")
        with open(caminho_json, "w", encoding="utf-8") as arquivo:
            arquivo.write('{"dados":[{"cpf":"1","nome":"A"},{"cpf":"2","nome":"B"}]}')
        tabela = leitores.ler_arquivo(caminho_json)[0]
        self.assertEqual(tabela.colunas, ["cpf", "nome"])
        caminho_xml = os.path.join(self.pasta, "extra.xml")
        with open(caminho_xml, "w", encoding="utf-8") as arquivo:
            arquivo.write("<raiz><item><cpf>1</cpf></item><item><cpf>2</cpf></item></raiz>")
        self.assertEqual(len(leitores.ler_arquivo(caminho_xml)[0].linhas), 2)

    def teste_extensao_nao_suportada(self):
        caminho = os.path.join(self.pasta, "arquivo.zip")
        open(caminho, "wb").close()
        with self.assertRaises(leitores.ErroLeitura):
            leitores.ler_arquivo(caminho)


class TestePlanilhaEscritaLeitura(unittest.TestCase):
    """A planilha gerada precisa ser relida corretamente (ida e volta)."""

    def teste_ida_e_volta(self):
        pasta = tempfile.mkdtemp(prefix="consolidador_xlsx_")
        try:
            caminho = os.path.join(pasta, "teste.xlsx")
            planilha = Planilha()
            aba = planilha.aba("Dados")
            aba.escrever_linha(["Nome", "Valor"], estilo=Estilo(negrito=True, fundo="1F4E79"))
            aba.escrever_linha(["Maria & João <teste>", 1234.5])
            planilha.salvar(caminho)
            tabela = leitores.ler_arquivo(caminho)[0]
            self.assertEqual(tabela.colunas, ["Nome", "Valor"])
            self.assertEqual(tabela.linhas[0]["Nome"], "Maria & João <teste>")
            self.assertEqual(tx.para_numero(tabela.linhas[0]["Valor"]), 1234.5)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)


class TesteRegrasDeConsistencia(unittest.TestCase):
    def teste_comparador(self):
        from nucleo.qualidade import _comparar
        self.assertFalse(_comparar("31/12/2035", "31/12/2030", "<="))
        self.assertTrue(_comparar("01/01/2020", "31/12/2030", "<="))
        self.assertFalse(_comparar("-50", "0", ">"))
        self.assertTrue(_comparar("120,50", "0", ">"))
        self.assertTrue(_comparar("ATIVO", "ativo", "=="))

    def teste_regra_gera_ocorrencia(self):
        pasta = tempfile.mkdtemp(prefix="consolidador_regras_")
        try:
            for nome, linha in (("ALFA_base.csv", "1,Contrato A,01/02/2024,10/01/2024"),
                                ("BETA_base.csv", "1,Contrato A,01/02/2024,10/03/2024")):
                with open(os.path.join(pasta, nome), "w", encoding="utf-8") as arquivo:
                    arquivo.write("CODIGO,OBJETO,INICIO,FIM\n" + linha + "\n")
            perfil = perfil_padrao()
            perfil.campos = [
                CampoConfig(nome="CODIGO", tipo="codigo", chave=True),
                CampoConfig(nome="INICIO", tipo="data"),
                CampoConfig(nome="FIM", tipo="data"),
            ]
            perfil.qualidade.regras_consistencia = [
                RegraConsistencia(nome="vigencia", campo_a="FIM", operador=">=", campo_b="INICIO",
                                  descricao="Fim da vigencia anterior ao inicio"),
            ]
            resultado = executar([pasta], os.path.join(pasta, "saidas"), perfil=perfil)
            inconsistentes = [
                o for q in (resultado.qualidade_a, resultado.qualidade_b)
                for o in q.ocorrencias if o.dimensao == "Consistencia"
            ]
            self.assertEqual(len(inconsistentes), 1)
            self.assertIn("anterior ao inicio", inconsistentes[0].descricao)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)


class TesteRotinaCompleta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.mkdtemp(prefix="consolidador_rotina_")
        cls.entradas = os.path.join(cls.pasta, "entradas")
        cls.saidas = os.path.join(cls.pasta, "saidas")
        gerar(cls.entradas)
        cls.resultado = executar([cls.entradas], cls.saidas)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.pasta, ignore_errors=True)

    def teste_gerou_os_dois_produtos(self):
        self.assertTrue(os.path.isfile(self.resultado.caminho_planilha))
        self.assertTrue(os.path.isfile(self.resultado.caminho_relatorio))
        self.assertEqual(self.resultado.erros, [])

    def teste_identificou_os_dois_sistemas(self):
        nomes = {self.resultado.nome_a, self.resultado.nome_b}
        self.assertEqual(nomes, {"SIGA", "RHNET"})
        for arquivo in self.resultado.arquivos:
            esperado = "SIGA" if arquivo.nome.startswith("SIGA") else "RHNET"
            self.assertEqual(arquivo.sistema, esperado, arquivo.nome)

    def teste_consolidou_colunas_equivalentes(self):
        rhnet = self._sistema("RHNET")
        self.assertEqual(len(rhnet.tabela.linhas), 26)
        # O DBF corta o nome do campo em 10 caracteres; nao pode virar coluna separada.
        self.assertNotIn("NOMECOMPL", rhnet.colunas_dados)
        self.assertIn("Nome completo", rhnet.colunas_dados)
        preenchidos = sum(1 for l in rhnet.tabela.linhas if tx.limpar(l.get("Nome completo")))
        self.assertEqual(preenchidos, 26)

    def teste_analise_de_qualidade(self):
        siga = self.resultado.qualidade_a if self.resultado.nome_a == "SIGA" else self.resultado.qualidade_b
        descricoes = " | ".join(o.descricao for o in siga.ocorrencias)
        self.assertIn("digito verificador invalido", descricoes)   # CPF 111.111.111-11
        self.assertIn("repetido", descricoes)                      # matricula duplicada
        self.assertIn("identico", descricoes)                      # registro duplicado
        self.assertIn("E-mail em formato invalido", descricoes)
        self.assertIn("fora da faixa plausivel", descricoes)       # admissao em 1899
        self.assertIn("outlier", descricoes)                       # valor de 987.654,32
        self.assertIn("Espacos extras", descricoes)
        self.assertGreater(siga.nota_geral, 0)
        self.assertLessEqual(siga.nota_geral, 100)
        for nota in siga.notas_dimensao.values():
            self.assertGreaterEqual(nota, 0)
            self.assertLessEqual(nota, 100)

    def teste_pareamento(self):
        pareamento = self.resultado.pareamento
        estatisticas = self.resultado.estatisticas()
        so_rhnet = estatisticas["somente_a"] if self.resultado.nome_a == "RHNET" else estatisticas["somente_b"]
        so_siga = estatisticas["somente_a"] if self.resultado.nome_a == "SIGA" else estatisticas["somente_b"]
        self.assertEqual(so_rhnet, 2)   # Erica e Felipe existem so no RHNET
        self.assertEqual(so_siga, 7)    # seis exclusivos do SIGA + uma duplicidade
        self.assertGreaterEqual(pareamento.total_pares, 24)
        self.assertTrue(any(p.tipo.startswith("Provavel") for p in pareamento.pares),
                        "o registro sem chave deveria ter sido pareado por similaridade")
        self.assertGreater(pareamento.pares_divergentes, 0)
        for item in pareamento.somente_a + pareamento.somente_b:
            self.assertTrue(item.motivo, "todo registro exclusivo precisa de motivo descrito")

    def teste_abas_da_planilha(self):
        with zipfile.ZipFile(self.resultado.caminho_planilha) as pacote:
            workbook = ET.fromstring(pacote.read("xl/workbook.xml"))
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        nomes = [aba.get("name") for aba in workbook.iter(f"{ns}sheet")]
        self.assertEqual(len(nomes), 9)
        esperadas = [
            "Resumo",
            f"Consolidado {self.resultado.nome_a}", f"Consolidado {self.resultado.nome_b}",
            f"Qualidade {self.resultado.nome_a}", f"Qualidade {self.resultado.nome_b}",
            "Pareamento",
            f"Somente em {self.resultado.nome_a}", f"Somente em {self.resultado.nome_b}",
            "Arquivos lidos",
        ]
        self.assertEqual(nomes, esperadas)

    def teste_planilha_pode_ser_relida(self):
        tabelas = leitores.ler_arquivo(self.resultado.caminho_planilha)
        self.assertGreaterEqual(len(tabelas), 7)
        pareamento = [t for t in tabelas if t.aba == "Pareamento"][0]
        self.assertGreaterEqual(len(pareamento.linhas), 20)

    def teste_realce_nas_abas_de_exclusivos(self):
        """As linhas exclusivas precisam sair coloridas, e nao apenas listadas."""
        with zipfile.ZipFile(self.resultado.caminho_planilha) as pacote:
            estilos = ET.fromstring(pacote.read("xl/styles.xml"))
            nomes = [n for n in pacote.namelist() if n.startswith("xl/worksheets/")]
            conteudos = {n: pacote.read(n) for n in nomes}
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        cores = [
            (cor.get("rgb") or "").upper()
            for cor in estilos.iter(f"{ns}fgColor")
        ]
        self.assertIn("FFFCE4D6", cores)  # laranja: exclusivos do primeiro sistema
        self.assertIn("FFDDEBF7", cores)  # azul: exclusivos do segundo sistema
        self.assertIn("FFFFF2CC", cores)  # amarelo: divergencias no pareamento
        self.assertTrue(any(b'<c r="A1"' in dados for dados in conteudos.values()))

    def teste_relatorio_word(self):
        with zipfile.ZipFile(self.resultado.caminho_relatorio) as pacote:
            documento = pacote.read("word/document.xml").decode("utf-8")
            self.assertIn("word/styles.xml", pacote.namelist())
            self.assertIn("word/numbering.xml", pacote.namelist())
        ET.fromstring(documento)  # precisa ser XML valido
        for trecho in (
            "Sumario executivo", "1. Objetivo e escopo", "2. Metodologia",
            "3. Arquivos processados", "4. Consolidacao das bases",
            "5. Analise dos atributos de qualidade", "6. Pareamento entre os sistemas",
            "7. Comparacao", "8. Conclusoes e recomendacoes",
            self.resultado.nome_a, self.resultado.nome_b,
        ):
            self.assertIn(trecho, documento, f"faltou '{trecho}' no relatorio")

    def teste_perfil_configurado(self):
        """Com perfil, o usuario manda nas regras: nomes, chaves e criticas."""
        perfil = Perfil(
            nome="Teste",
            sistemas=[
                SistemaConfig(id="A", nome="Folha", padroes_arquivo=[r"^SIGA"],
                              mapeamento={"CPF": ["CPF", "Nr. CPF", "NRCPF"],
                                          "Nome": ["NOME DO SERVIDOR", "Nome completo", "NOMECOMPL"],
                                          "Admissao": ["DT_ADMISSAO", "Data de admissao", "DTADMISSA"]}),
                SistemaConfig(id="B", nome="Pessoal", padroes_arquivo=[r"^RHNET"],
                              mapeamento={"CPF": ["Nr. CPF", "NRCPF", "CPF"],
                                          "Nome": ["Nome completo", "NOMECOMPL"],
                                          "Admissao": ["Data de admissao", "DTADMISSA"]}),
            ],
            campos=[
                CampoConfig(nome="CPF", tipo="cpf", obrigatorio=True, chave=True, unico=True),
                CampoConfig(nome="Nome", tipo="texto", obrigatorio=True),
                CampoConfig(nome="Admissao", tipo="data"),
            ],
        )
        perfil.pareamento.chaves_primarias = ["CPF"]
        perfil.pareamento.campos_similaridade = ["Nome"]
        perfil.qualidade.regras_consistencia = [
            RegraConsistencia(nome="admissao_no_passado", campo_a="Admissao", operador="<=",
                              valor="31/12/2030", descricao="Admissao em data futura"),
        ]
        saida = os.path.join(self.pasta, "saidas_perfil")
        resultado = executar([self.entradas], saida, perfil=perfil)
        self.assertEqual({resultado.nome_a, resultado.nome_b}, {"Folha", "Pessoal"})
        self.assertEqual(resultado.pareamento.chaves_usadas[0][0], "CPF")
        obrigatorios = [
            o for o in resultado.qualidade_a.ocorrencias
            if "obrigatorio" in o.descricao
        ]
        self.assertTrue(obrigatorios, "CPF em branco deveria acusar campo obrigatorio")
        self.assertTrue(os.path.isfile(resultado.caminho_planilha))

    def teste_nome_informado_pelo_usuario_prevalece(self):
        perfil = perfil_padrao()
        perfil.sistemas[0].nome = "Folha de pagamento"
        perfil.sistemas[1].nome = "Cadastro funcional"
        resultado = executar(
            [self.entradas], os.path.join(self.pasta, "saidas_nomes"), perfil=perfil
        )
        self.assertEqual(
            {resultado.nome_a, resultado.nome_b},
            {"Folha de pagamento", "Cadastro funcional"},
        )

    def teste_atribuicao_manual_prevalece(self):
        caminho = os.path.join(self.entradas, "RHNET_cadastro.dbf")
        resultado = executar(
            [self.entradas], os.path.join(self.pasta, "saidas_manual"),
            atribuicoes_manuais={caminho: "B"},
        )
        arquivo = [a for a in resultado.arquivos if a.caminho == caminho][0]
        self.assertEqual(arquivo.sistema, resultado.nome_b)
        self.assertIn("manualmente", arquivo.justificativa)

    def teste_entrada_vazia_nao_quebra(self):
        saida = os.path.join(self.pasta, "saidas_vazias")
        resultado = executar([os.path.join(self.pasta, "inexistente")], saida)
        self.assertTrue(resultado.erros)
        self.assertEqual(resultado.caminho_planilha, "")

    def teste_um_sistema_so(self):
        """Se o usuario mandar so os arquivos de um sistema, a rotina avisa."""
        saida = os.path.join(self.pasta, "saidas_um_sistema")
        apenas = [
            os.path.join(self.entradas, nome)
            for nome in os.listdir(self.entradas) if nome.startswith("SIGA")
        ]
        atribuicoes = {caminho: "A" for caminho in apenas}
        resultado = executar(apenas, saida, perfil=perfil_padrao(), atribuicoes_manuais=atribuicoes)
        self.assertTrue(os.path.isfile(resultado.caminho_planilha))
        self.assertTrue(any("Nenhum arquivo" in a for a in resultado.deteccao.avisos))

    def _sistema(self, nome: str):
        if self.resultado.consolidado_a.nome == nome:
            return self.resultado.consolidado_a
        return self.resultado.consolidado_b


if __name__ == "__main__":
    unittest.main(verbosity=2)
