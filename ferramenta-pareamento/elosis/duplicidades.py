# -*- coding: utf-8 -*-
"""
Detecção de duplicidades intrabase (ELO-SIS).

Garcia, Miranda e Sousa (2022) advertem que bases contendo registros
duplicados, ou registros distintos referentes à mesma pessoa, produzem
diferentes possibilidades de análise combinatória nas funções de junção. A
consequência prática é que a duplicidade não tratada antes do pareamento
multiplica pares espúrios. A depuração precede, portanto, o linkage.

São distinguidos três fenômenos que a rotina manual costuma tratar como um só:

1. Duplicata técnica — mesmo registro importado duas vezes (mesma chave
   primária do sistema);
2. Duplicata de conteúdo — registros de chaves primárias distintas com
   conteúdo idêntico nas variáveis de identificação;
3. Duplicata provável — registros que, por similaridade, aparentam referir-se
   à mesma pessoa, sem identidade exata. Exige verificação manual.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import pandas as pd

from . import normalizacao as nz
from .perfis import PerfilSistema
from .qualidade import AMARELO, VERMELHO, Achado
from .similaridade import chave_fonetica_nome, similaridade_data, similaridade_nome


@dataclass
class GrupoDuplicidade:
    identificador: int
    tipo: str
    linhas: list[int]
    chave: str
    escore: float
    descricao: str
    recomendacao: str

    def como_linhas(self, base: str, quadro: pd.DataFrame,
                    mapeamento: dict[str, str]) -> list[dict]:
        saida = []
        for ordem, linha in enumerate(self.linhas, start=1):
            registro = {
                "BASE": base,
                "GRUPO_DUPLICIDADE": f"{base}-D{self.identificador:05d}",
                "TIPO_DUPLICIDADE": self.tipo,
                "ORDEM_NO_GRUPO": ordem,
                "PAPEL": "Registro de referência" if ordem == 1 else "Duplicata candidata",
                "LINHA_NA_BASE": linha + 2,  # +2: cabeçalho e índice base 1
                "REGISTROS_NO_GRUPO": len(self.linhas),
                "ESCORE_SIMILARIDADE": round(self.escore, 4),
                "CHAVE_AGRUPADORA": self.chave,
            }
            for canonica, coluna in mapeamento.items():
                if canonica in ("NOME", "NOME_MAE", "DATA_NASCIMENTO", "SEXO",
                                "CPF", "NUMERO_REGISTRO", "DATA_EVENTO"):
                    registro[canonica] = str(quadro[coluna].at[linha])
            registro["DESCRICAO"] = self.descricao
            registro["RECOMENDACAO"] = self.recomendacao
            saida.append(registro)
        return saida


def _chave_identificacao(quadro: pd.DataFrame, mapeamento: dict[str, str]) -> pd.Series:
    """Chave composta normalizada: nome + nome da mãe + data de nascimento."""
    partes = []
    for canonica, normalizador in (("NOME", nz.normalizar_nome),
                                   ("NOME_MAE", nz.normalizar_nome),
                                   ("DATA_NASCIMENTO", nz.normalizar_data)):
        coluna = mapeamento.get(canonica)
        if coluna:
            partes.append(quadro[coluna].map(normalizador))
        else:
            partes.append(pd.Series("", index=quadro.index))
    return partes[0] + "|" + partes[1] + "|" + partes[2]


def detectar_duplicidades(quadro: pd.DataFrame, perfil: PerfilSistema,
                          mapeamento: dict[str, str],
                          limiar_provavel: float = 0.92,
                          maximo_comparacoes: int = 5_000_000
                          ) -> tuple[list[GrupoDuplicidade], list[Achado]]:
    """Identifica os três tipos de duplicidade e produz os achados associados."""
    grupos: list[GrupoDuplicidade] = []
    achados: list[Achado] = []
    contador = 0
    ja_agrupadas: set[int] = set()

    # ------------------------------------------------------------------ #
    # 1. Duplicata técnica: mesma chave primária do sistema
    # ------------------------------------------------------------------ #
    coluna_registro = mapeamento.get("NUMERO_REGISTRO")
    if coluna_registro:
        chaves = quadro[coluna_registro].astype(str).str.strip()
        validas = chaves[chaves != ""]
        for chave, indices in validas.groupby(validas).groups.items():
            linhas = sorted(int(i) for i in indices)
            if len(linhas) < 2:
                continue
            contador += 1
            grupos.append(GrupoDuplicidade(
                identificador=contador, tipo="DUPLICATA_TECNICA", linhas=linhas,
                chave=str(chave), escore=1.0,
                descricao=(
                    f"{len(linhas)} registros compartilham o mesmo número de "
                    f"identificação no {perfil.sigla} ('{chave}'), que deveria "
                    f"ser único."),
                recomendacao=(
                    "Manter um único registro e excluir os demais no sistema de "
                    "origem. Antes da exclusão, verificar se as duplicatas "
                    "diferem em algum campo: nesse caso, consolidar a "
                    "informação mais completa no registro mantido.")))
            ja_agrupadas.update(linhas)
            for linha in linhas[1:]:
                achados.append(Achado(
                    linha=linha, variavel="NUMERO_REGISTRO",
                    tipo="DUPLICATA_TECNICA", gravidade=VERMELHO,
                    descricao=(f"Número de registro '{chave}' repetido em "
                               f"{len(linhas)} linhas da base."),
                    valor_observado=str(chave),
                    justificativa=(
                        "A chave primária do sistema deve identificar um único "
                        "evento. A repetição duplica o evento nas contagens e "
                        "multiplica pares espúrios no relacionamento de bases."),
                    recomendacao=("Excluir a duplicata no sistema de origem, "
                                  "preservando o registro mais completo."),
                    dimensao="Consistência"))

    # ------------------------------------------------------------------ #
    # 2. Duplicata de conteúdo: identificação idêntica, chave primária distinta
    # ------------------------------------------------------------------ #
    chave_identidade = _chave_identificacao(quadro, mapeamento)
    identificaveis = chave_identidade[chave_identidade.str.replace("|", "",
                                                                   regex=False) != ""]
    for chave, indices in identificaveis.groupby(identificaveis).groups.items():
        linhas = sorted(int(i) for i in indices)
        if len(linhas) < 2:
            continue
        if all(l in ja_agrupadas for l in linhas):
            continue
        # Exige que a chave tenha pelo menos nome e uma segunda variável.
        componentes = [p for p in str(chave).split("|") if p]
        if len(componentes) < 2:
            continue
        contador += 1
        grupos.append(GrupoDuplicidade(
            identificador=contador, tipo="DUPLICATA_DE_CONTEUDO", linhas=linhas,
            chave=str(chave), escore=1.0,
            descricao=(
                f"{len(linhas)} registros com números de identificação distintos "
                f"apresentam exatamente a mesma identificação nominal (nome, "
                f"nome da mãe e data de nascimento)."),
            recomendacao=(
                "Verificar se se trata do mesmo evento notificado/registrado "
                "mais de uma vez. Em caso positivo, encerrar a duplicata "
                "conforme o fluxo do sistema. Em caso negativo — por exemplo, "
                "homônimos com mesma data de nascimento e mesmo nome de mãe —, "
                "registrar a justificativa para evitar reincidência da análise.")))
        ja_agrupadas.update(linhas)
        for linha in linhas[1:]:
            achados.append(Achado(
                linha=linha, variavel="NOME", tipo="DUPLICATA_DE_CONTEUDO",
                gravidade=VERMELHO,
                descricao=("Identificação nominal idêntica à de outro registro "
                           "da mesma base."),
                valor_observado=str(chave)[:120],
                justificativa=(
                    "Registros distintos com identificação integralmente "
                    "coincidente indicam duplicidade de digitação ou "
                    "importação repetida do mesmo lote."),
                recomendacao=("Confrontar os dois registros no sistema e "
                              "eliminar a duplicidade."),
                dimensao="Consistência"))

    # ------------------------------------------------------------------ #
    # 3. Duplicata provável: similaridade elevada sob blocagem
    # ------------------------------------------------------------------ #
    blocos = _blocos_para_duplicidade(quadro, mapeamento)
    comparacoes = 0
    coluna_nome = mapeamento.get("NOME")
    coluna_mae = mapeamento.get("NOME_MAE")
    coluna_nascimento = mapeamento.get("DATA_NASCIMENTO")

    if coluna_nome:
        nomes = quadro[coluna_nome].map(nz.normalizar_nome)
        maes = (quadro[coluna_mae].map(nz.normalizar_nome) if coluna_mae
                else pd.Series("", index=quadro.index))
        nascimentos = (quadro[coluna_nascimento].map(nz.normalizar_data)
                       if coluna_nascimento
                       else pd.Series("", index=quadro.index))

        # Um mesmo par costuma cair em mais de um bloco; sem este controle o
        # par seria contado tantas vezes quantas as chaves que o reúnem.
        pares_avaliados: set[tuple[int, int]] = set()

        for linhas_bloco in blocos.values():
            if len(linhas_bloco) < 2 or len(linhas_bloco) > 400:
                continue  # blocos muito grandes indicam chave pouco seletiva
            for i, linha_a in enumerate(linhas_bloco):
                for linha_b in linhas_bloco[i + 1:]:
                    if comparacoes >= maximo_comparacoes:
                        break
                    par = (min(linha_a, linha_b), max(linha_a, linha_b))
                    if par in pares_avaliados:
                        continue
                    pares_avaliados.add(par)
                    comparacoes += 1
                    if linha_a in ja_agrupadas and linha_b in ja_agrupadas:
                        continue
                    escore = _escore_duplicidade(
                        nomes.at[linha_a], nomes.at[linha_b],
                        maes.at[linha_a], maes.at[linha_b],
                        nascimentos.at[linha_a], nascimentos.at[linha_b])
                    if escore < limiar_provavel:
                        continue
                    contador += 1
                    grupos.append(GrupoDuplicidade(
                        identificador=contador, tipo="DUPLICATA_PROVAVEL",
                        linhas=[linha_a, linha_b],
                        chave=f"{nomes.at[linha_a]} ~ {nomes.at[linha_b]}",
                        escore=escore,
                        descricao=(
                            f"Dois registros da base apresentam escore de "
                            f"similaridade de {escore:.3f} nas variáveis de "
                            f"identificação, sem coincidência exata."),
                        recomendacao=(
                            "Verificação manual obrigatória. Confrontar os "
                            "documentos-fonte para decidir entre duplicidade "
                            "(com erro de digitação em um dos registros) e "
                            "pessoas distintas com nomes semelhantes.")))
                    for linha in (linha_a, linha_b):
                        achados.append(Achado(
                            linha=linha, variavel="NOME",
                            tipo="DUPLICATA_PROVAVEL", gravidade=AMARELO,
                            descricao=(f"Similaridade de {escore:.3f} com outro "
                                       f"registro da mesma base."),
                            valor_observado=str(nomes.at[linha])[:120],
                            justificativa=(
                                "Similaridade elevada sem identidade exata "
                                "sugere duplicidade com erro de digitação, "
                                "mas não a comprova."),
                            recomendacao=("Conferir os documentos-fonte dos dois "
                                          "registros antes de qualquer exclusão."),
                            dimensao="Consistência"))
    return grupos, achados


def _blocos_para_duplicidade(quadro: pd.DataFrame,
                             mapeamento: dict[str, str]) -> dict[str, list[int]]:
    """Agrupa registros comparáveis, evitando a comparação de todos com todos.

    A blocagem é o que torna a detecção viável em bases grandes: sem ela, uma
    base de 100 mil registros exigiria cerca de cinco bilhões de comparações.
    """
    coluna_nome = mapeamento.get("NOME")
    coluna_nascimento = mapeamento.get("DATA_NASCIMENTO")
    coluna_mae = mapeamento.get("NOME_MAE")
    blocos: dict[str, list[int]] = defaultdict(list)

    for linha in quadro.index:
        nome = nz.normalizar_nome(quadro[coluna_nome].at[linha]) if coluna_nome else ""
        if not nome:
            continue
        fonetica = chave_fonetica_nome(nome)
        nascimento = (nz.normalizar_data(quadro[coluna_nascimento].at[linha])
                      if coluna_nascimento else "")
        mae = nz.normalizar_nome(quadro[coluna_mae].at[linha]) if coluna_mae else ""

        # Múltiplas chaves de blocagem: basta coincidir em uma para serem comparados.
        if nascimento:
            blocos[f"N:{fonetica}|{nascimento}"].append(linha)
            blocos[f"A:{nome[:4]}|{nascimento}"].append(linha)
        if mae:
            blocos[f"M:{fonetica}|{chave_fonetica_nome(mae)}"].append(linha)
        if nascimento and mae:
            blocos[f"D:{nascimento}|{chave_fonetica_nome(mae)}"].append(linha)
    return blocos


def _escore_duplicidade(nome_a: str, nome_b: str, mae_a: str, mae_b: str,
                        nascimento_a: str, nascimento_b: str) -> float:
    """Escore ponderado para duplicidade intrabase.

    Usa a mesma ponderação do pareamento interbases (0,4 / 0,3 / 0,3),
    redistribuindo o peso das variáveis ausentes entre as disponíveis, de modo
    que a ausência de um campo não penalize o escore por si só.
    """
    componentes = []
    if nome_a and nome_b:
        componentes.append((0.40, similaridade_nome(nome_a, nome_b)))
    if mae_a and mae_b:
        componentes.append((0.30, similaridade_nome(mae_a, mae_b)))
    if nascimento_a and nascimento_b:
        componentes.append((0.30, similaridade_data(nascimento_a, nascimento_b)))
    if not componentes:
        return 0.0
    peso_total = sum(p for p, _ in componentes)
    if peso_total < 0.55:
        return 0.0  # informação insuficiente para afirmar duplicidade
    return sum(p * v for p, v in componentes) / peso_total


def resumir_duplicidades(grupos: list[GrupoDuplicidade],
                         total_registros: int, sigla: str) -> list[dict]:
    contagem: dict[str, list[int]] = defaultdict(list)
    for grupo in grupos:
        contagem[grupo.tipo].append(len(grupo.linhas))
    resumo = []
    for tipo, tamanhos in contagem.items():
        registros = sum(tamanhos)
        excedentes = sum(t - 1 for t in tamanhos)
        resumo.append({
            "BASE": sigla,
            "TIPO_DUPLICIDADE": tipo,
            "GRUPOS": len(tamanhos),
            "REGISTROS_ENVOLVIDOS": registros,
            "REGISTROS_EXCEDENTES": excedentes,
            "PROPORCAO_DA_BASE_%": round(100 * excedentes / total_registros, 3)
            if total_registros else 0.0,
        })
    return resumo
