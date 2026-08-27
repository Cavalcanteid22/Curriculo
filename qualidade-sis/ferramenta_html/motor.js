/* QualiSIS no navegador — motor de crítica.
   Porte fiel do motor em Python (qualisis/regras.py e analise.py): mesmas
   regras, mesmos indicadores, mesmas fórmulas. Roda inteiramente na máquina
   do usuário: nenhum dado sai do computador.                               */

'use strict';

/* ------------------------------------------------------------------ tipos */
const TIPOS = {
  duplicidade: {
    rotulo: 'Duplicidade', gravidade: 'Alta', peso: 3,
    descricao: 'Registro repetido pela chave do sistema ou por chave provável (nome + data + mãe).',
    atributos: 'Singularidade, Confiabilidade, Precisão'
  },
  em_branco: {
    rotulo: 'Campo em branco', gravidade: 'Alta', peso: 2,
    descricao: 'Campo essencial sem preenchimento.',
    atributos: 'Completude, Suficiência, Abrangência'
  },
  ignorado: {
    rotulo: 'Ignorado / Não informado', gravidade: 'Média', peso: 1.5,
    descricao: 'Preenchido com 9, 99, 999 ou "IGNORADO": consta preenchido, mas não informa nada.',
    atributos: 'Confiabilidade, Valor informativo, Utilidade'
  },
  codigo_invalido: {
    rotulo: 'Código inválido', gravidade: 'Alta', peso: 2.5,
    descricao: 'Valor fora do domínio do dicionário de dados (categoria, CID, município, CNES).',
    atributos: 'Validade, Correção, Precisão, Inequivocidade'
  },
  data_invalida: {
    rotulo: 'Data inválida ou incoerente', gravidade: 'Alta', peso: 2.5,
    descricao: 'Data inexistente, fora do plausível, no futuro ou fora de ordem cronológica.',
    atributos: 'Validade, Logicidade, Coerência, Veracidade'
  },
  incoerencia: {
    rotulo: 'Incoerência entre campos', gravidade: 'Alta', peso: 2.5,
    descricao: 'Combinação impossível entre campos do mesmo registro.',
    atributos: 'Coerência, Logicidade, Compatibilidade, Veracidade'
  },
  formato_invalido: {
    rotulo: 'Formato inválido', gravidade: 'Média', peso: 1.5,
    descricao: 'Conteúdo fora da máscara esperada (CNS, CPF, CEP, telefone, nº de DO/DN).',
    atributos: 'Formato, Legibilidade, Interpretabilidade'
  },
  fora_de_faixa: {
    rotulo: 'Valor fora de faixa', gravidade: 'Média', peso: 2,
    descricao: 'Valor numérico fora dos limites plausíveis (peso, idade, Apgar, consultas).',
    atributos: 'Quantidade, Precisão, Veracidade, Correção'
  },
  fora_do_prazo: {
    rotulo: 'Fora do prazo', gravidade: 'Média', peso: 1.5,
    descricao: 'Notificação, digitação ou encerramento fora do prazo pactuado.',
    atributos: 'Tempestividade, Atualidade, Tempo de resposta'
  }
};
const ORDEM_TIPOS = ['duplicidade', 'em_branco', 'ignorado', 'codigo_invalido', 'data_invalida',
  'incoerencia', 'formato_invalido', 'fora_de_faixa', 'fora_do_prazo'];

const FAIXAS = [
  [95, 'Excelente', 'var(--bom)'],
  [90, 'Bom', 'var(--bom)'],
  [80, 'Regular', 'var(--atencao)'],
  [50, 'Ruim', 'var(--serio)'],
  [0, 'Muito ruim', 'var(--critico)']
];

function classificar(pct) {
  if (pct === null || pct === undefined || Number.isNaN(pct)) return ['Não avaliado', 'var(--tinta-3)'];
  for (const [limite, rotulo, cor] of FAIXAS) if (pct >= limite) return [rotulo, cor];
  return ['Muito ruim', 'var(--critico)'];
}

const PESOS_ATRIBUTO = {
  Completude: 3, Suficiência: 2, Confiabilidade: 3, Validade: 3, Correção: 3, Precisão: 2,
  Coerência: 3, Logicidade: 2, Singularidade: 3, Tempestividade: 3, Atualidade: 2,
  Abrangência: 2, Formato: 1.5, Veracidade: 2, Inequivocidade: 1.5, Compatibilidade: 1.5,
  Mensurabilidade: 1.5, 'Valor informativo': 2, Ordem: 1
};

const IGNORADOS_TEXTO = new Set(['IGNORADO', 'IGNORADA', 'IGN', 'NAO INFORMADO', 'NÃO INFORMADO',
  'NAO INFORMADA', 'NÃO INFORMADA', 'SEM INFORMACAO', 'SEM INFORMAÇÃO', 'NI', 'N/I',
  'NAO SE APLICA', 'NÃO SE APLICA', '-', '--', '...']);

/* ------------------------------------------------------------ utilidades */
function semAcento(txt) {
  return txt.normalize('NFKD').replace(/[̀-ͯ]/g, '');
}
function normalizarColuna(nome) {
  let t = String(nome == null ? '' : nome).replace(/﻿/g, '').trim();
  t = semAcento(t).replace(/[\s.\-]+/g, '_').replace(/_+/g, '_');
  return t.replace(/^_|_$/g, '').toUpperCase();
}
function normalizarTexto(valor) {
  return semAcento(String(valor == null ? '' : valor)).toUpperCase().replace(/[^A-Z0-9]+/g, '');
}
function soDigitos(valor) { return String(valor == null ? '' : valor).replace(/\D/g, ''); }

function validoCPF(valor) {
  const n = soDigitos(valor);
  if (n.length !== 11 || /^(\d)\1{10}$/.test(n)) return false;
  for (const tam of [9, 10]) {
    let soma = 0;
    for (let i = 0; i < tam; i++) soma += Number(n[i]) * (tam + 1 - i);
    if ((soma * 10) % 11 % 10 !== Number(n[tam])) return false;
  }
  return true;
}
function validoCNS(valor) {
  const n = soDigitos(valor);
  if (n.length !== 15) return false;
  if (!'12789'.includes(n[0])) return false;
  let soma = 0;
  for (let i = 0; i < 15; i++) soma += Number(n[i]) * (15 - i);
  return soma % 11 === 0;
}
const RE_CID10 = /^[A-Z]\d{2}(\.?\d)?$/;
const VALIDADORES = {
  cpf: validoCPF,
  cns: validoCNS,
  cid10: v => RE_CID10.test(String(v).trim().toUpperCase()),
  ibge: v => [6, 7].includes(soDigitos(v).length),
  cnes: v => soDigitos(v).length === 7,
  cep: v => soDigitos(v).length === 8
};

/* Datas: devolve o número de dias desde 1970 (inteiro) ou null. */
const DIAS_MS = 86400000;
function converterData(valor) {
  const txt = String(valor == null ? '' : valor).trim();
  if (!txt) return null;
  const curto = txt.split(/[ T]/)[0];
  let a, m, d;
  let mm;
  if ((mm = /^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$/.exec(curto))) {
    d = +mm[1]; m = +mm[2]; a = +mm[3];
  } else if ((mm = /^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$/.exec(curto))) {
    a = +mm[1]; m = +mm[2]; d = +mm[3];
  } else if ((mm = /^(\d{4})(\d{2})(\d{2})$/.exec(curto))) {
    a = +mm[1]; m = +mm[2]; d = +mm[3];
  } else if ((mm = /^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})$/.exec(curto))) {
    d = +mm[1]; m = +mm[2]; a = 2000 + +mm[3];
    if (a > 2069) a -= 100;
  } else {
    return null;
  }
  if (m < 1 || m > 12 || d < 1 || d > 31 || a < 1) return null;
  const dt = new Date(Date.UTC(a, m - 1, d));
  if (dt.getUTCFullYear() !== a || dt.getUTCMonth() !== m - 1 || dt.getUTCDate() !== d) return null;
  return Math.round(dt.getTime() / DIAS_MS);
}
function dataParaTexto(dias) {
  if (dias === null || dias === undefined) return '—';
  const dt = new Date(dias * DIAS_MS);
  const p = n => String(n).padStart(2, '0');
  return `${p(dt.getUTCDate())}/${p(dt.getUTCMonth() + 1)}/${dt.getUTCFullYear()}`;
}
function mesDe(dias) {
  const dt = new Date(dias * DIAS_MS);
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}`;
}
function converterNumero(valor) {
  const txt = String(valor == null ? '' : valor).trim().replace(/\./g, '').replace(',', '.');
  if (!txt) return null;
  const n = Number(txt);
  return Number.isFinite(n) ? n : null;
}
function hashTexto(txt) {           /* FNV-1a de 32 bits + tamanho: colisão desprezível aqui */
  let h = 0x811c9dc5;
  for (let i = 0; i < txt.length; i++) {
    h ^= txt.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return ((h >>> 0).toString(36)) + ':' + txt.length;
}

/* ------------------------------------------------------------ preparação */
function prepararConfig(bruta) {
  const cfg = JSON.parse(JSON.stringify(bruta));
  cfg.campos = cfg.campos || {};
  const campos = {};
  for (const [nome, specBruta] of Object.entries(cfg.campos)) {
    const spec = Object.assign({}, specBruta);
    spec.rotulo = spec.rotulo || nome;
    spec.tipo = spec.tipo || 'texto';
    spec.obrigatorio = !!spec.obrigatorio;
    spec.essencial = spec.essencial === undefined ? spec.obrigatorio : !!spec.essencial;
    spec.bloco = spec.bloco || 'Geral';
    if (Array.isArray(spec.dominio)) {
      const d = {};
      spec.dominio.forEach(v => { d[String(v).toUpperCase()] = String(v); });
      spec.dominio = d;
    } else if (spec.dominio && typeof spec.dominio === 'object') {
      const d = {};
      for (const [k, v] of Object.entries(spec.dominio)) d[String(k).trim().toUpperCase()] = v;
      spec.dominio = d;
    } else {
      spec.dominio = null;
    }
    const ign = new Set((spec.ignorado || []).map(v => String(v).trim().toUpperCase()));
    if (spec.ignorado_texto_padrao !== false) IGNORADOS_TEXTO.forEach(v => ign.add(v));
    spec.ignorado = ign;
    if (spec.regex) spec._regex = new RegExp(spec.regex);
    if (spec.data_minima) spec._dmin = converterData(spec.data_minima);
    if (spec.data_maxima) spec._dmax = converterData(spec.data_maxima);
    campos[normalizarColuna(nome)] = spec;
  }
  cfg.campos = campos;
  cfg.chave_registro = (cfg.chave_registro || []).map(normalizarColuna);
  cfg.campos_estratificacao = (cfg.campos_estratificacao || []).map(normalizarColuna);
  (cfg.chaves_duplicidade || []).forEach(ch => { ch.campos = (ch.campos || []).map(normalizarColuna); });
  cfg.apelidos = {};
  for (const [k, v] of Object.entries(cfg.apelidos_colunas || {})) {
    cfg.apelidos[normalizarColuna(k)] = normalizarColuna(v);
  }
  cfg.parametros = cfg.parametros || {};
  cfg._dataMinima = converterData(cfg.parametros.data_minima_plausivel || '1900-01-01');
  cfg.data_referencia = cfg.data_referencia ? normalizarColuna(cfg.data_referencia) : null;
  return cfg;
}

/* ---------------------------------------------------------------- motor */
class Motor {
  constructor(cfg, colunas, diaExtracao) {
    this.cfg = cfg;
    this.colunas = colunas;
    this.diaExtracao = diaExtracao;
    this.idx = {};
    colunas.forEach((c, i) => { if (!(c in this.idx)) this.idx[c] = i; });

    this.camposAtivos = Object.keys(cfg.campos).filter(c => c in this.idx);
    this.essenciais = this.camposAtivos.filter(c => cfg.campos[c].essencial);
    this.comDominio = this.camposAtivos.filter(c => cfg.campos[c].dominio);
    this.chavesDup = (cfg.chaves_duplicidade || []).filter(ch => ch.campos.every(c => c in this.idx));
    this.tempestividade = (cfg.tempestividade || []).filter(t =>
      normalizarColuna(t.data_inicial) in this.idx && normalizarColuna(t.data_final) in this.idx);
    this.tempestividade.forEach(t => {
      t._ini = normalizarColuna(t.data_inicial);
      t._fim = normalizarColuna(t.data_final);
    });
    this.regras = (cfg.regras_cruzadas || []).filter(r => this._aplicavel(r));
    this.estratos = cfg.campos_estratificacao.filter(c => c in this.idx);
    this.chaveCampos = cfg.chave_registro.filter(c => c in this.idx);
    if (!this.chaveCampos.length) this.chaveCampos = this.camposAtivos.slice(0, 3);
    this.diaMax = diaExtracao;
    this.diaMin = cfg._dataMinima;
  }

  _aplicavel(regra) {
    const usados = new Set();
    (regra.campos || []).forEach(c => usados.add(normalizarColuna(c)));
    (regra.entao_preenchido || []).forEach(c => usados.add(normalizarColuna(c)));
    ['campo', 'campo_a', 'campo_b', 'entao_campo'].forEach(k => {
      if (regra[k]) usados.add(normalizarColuna(regra[k]));
    });
    condicoes(regra.se).forEach(c => { if (c.campo) usados.add(normalizarColuna(c.campo)); });
    (regra.combinacoes_proibidas || []).forEach(comb =>
      Object.keys(comb).forEach(c => usados.add(normalizarColuna(c))));
    for (const c of usados) if (!(c in this.idx)) return false;
    return true;
  }

  valor(linha, campo) {
    const i = this.idx[campo];
    if (i === undefined) return '';
    const v = linha[i];
    return v === undefined || v === null ? '' : String(v).trim();
  }

  chaveRegistro(linha) {
    return this.chaveCampos.map(c => normalizarTexto(this.valor(linha, c))).join('|');
  }

  hashesDup(linha) {
    const saida = [];
    for (let i = 0; i < this.chavesDup.length; i++) {
      const ch = this.chavesDup[i];
      const partes = [];
      let faltou = false;
      for (const campo of ch.campos) {
        let v = this.valor(linha, campo);
        const spec = this.cfg.campos[campo];
        if (spec && spec.tipo === 'data') {
          const d = converterData(v);
          v = d === null ? v : String(d);
        }
        const norm = normalizarTexto(v);
        if (!norm) { faltou = true; break; }
        partes.push(norm);
      }
      if (faltou || !partes.length) continue;
      saida.push(i + '#' + hashTexto(partes.join('')));
    }
    return saida;
  }

  avaliar(linha, duplicados) {
    const oc = [];
    const datas = {};
    const numeros = {};
    const cfg = this.cfg;

    for (const campo of this.camposAtivos) {
      const spec = cfg.campos[campo];
      const valor = this.valor(linha, campo);
      if (valor === '') {
        if (spec.obrigatorio || spec.essencial) {
          oc.push({ campo, tipo: 'em_branco', regra: 'CAMPO_OBRIGATORIO', valor: '',
            descricao: `'${spec.rotulo}' é campo essencial e está em branco.` });
        }
        continue;
      }
      const vup = valor.toUpperCase();
      if (spec.ignorado.has(vup)) {
        oc.push({ campo, tipo: 'ignorado', regra: 'CODIGO_IGNORADO', valor,
          descricao: `'${spec.rotulo}' preenchido como ignorado/não informado ('${valor}').` });
        continue;
      }
      if (spec.tipo === 'data') {
        const d = converterData(valor);
        if (d === null) {
          oc.push({ campo, tipo: 'data_invalida', regra: 'DATA_NAO_RECONHECIDA', valor,
            descricao: `'${spec.rotulo}' não é uma data válida ('${valor}').` });
        } else {
          datas[campo] = d;
          const dmax = spec._dmax !== undefined && spec._dmax !== null ? spec._dmax : this.diaMax;
          const dmin = spec._dmin !== undefined && spec._dmin !== null ? spec._dmin : this.diaMin;
          if (d > dmax) {
            oc.push({ campo, tipo: 'data_invalida', regra: 'DATA_FUTURA', valor,
              descricao: `'${spec.rotulo}' posterior ao limite aceito (${dataParaTexto(dmax)}).` });
          } else if (d < dmin) {
            oc.push({ campo, tipo: 'data_invalida', regra: 'DATA_IMPLAUSIVEL', valor,
              descricao: `'${spec.rotulo}' anterior ao limite plausível (${dataParaTexto(dmin)}).` });
          }
        }
        continue;
      }
      if (spec.tipo === 'inteiro' || spec.tipo === 'decimal') {
        const n = converterNumero(valor);
        if (n === null) {
          oc.push({ campo, tipo: 'formato_invalido', regra: 'NUMERO_INVALIDO', valor,
            descricao: `'${spec.rotulo}' deveria ser numérico ('${valor}').` });
          continue;
        }
        if (spec.tipo === 'inteiro' && !Number.isInteger(n)) {
          oc.push({ campo, tipo: 'formato_invalido', regra: 'NUMERO_NAO_INTEIRO', valor,
            descricao: `'${spec.rotulo}' deveria ser inteiro ('${valor}').` });
        }
        numeros[campo] = n;
        const min = spec.min, max = spec.max;
        if ((min !== undefined && n < min) || (max !== undefined && n > max)) {
          oc.push({ campo, tipo: 'fora_de_faixa', regra: 'FORA_DE_FAIXA', valor,
            descricao: `'${spec.rotulo}' = ${valor} fora da faixa plausível [${min}, ${max}].` });
        }
        continue;
      }
      if (spec.dominio && !(vup in spec.dominio)) {
        const validos = Object.keys(spec.dominio).slice(0, 8).join(', ');
        oc.push({ campo, tipo: 'codigo_invalido', regra: 'FORA_DO_DOMINIO', valor,
          descricao: `'${spec.rotulo}' = '${valor}' não consta no dicionário de dados (válidos: ${validos}…).` });
        continue;
      }
      if (spec.validador && VALIDADORES[spec.validador] && !VALIDADORES[spec.validador](valor)) {
        const tipo = ['cid10', 'ibge', 'cnes'].includes(spec.validador) ? 'codigo_invalido' : 'formato_invalido';
        oc.push({ campo, tipo, regra: 'VALIDADOR_' + spec.validador.toUpperCase(), valor,
          descricao: `'${spec.rotulo}' = '${valor}' não passa na validação de ${spec.validador.toUpperCase()}.` });
        continue;
      }
      if (spec._regex && !spec._regex.test(valor)) {
        oc.push({ campo, tipo: 'formato_invalido', regra: 'FORMATO', valor,
          descricao: `'${spec.rotulo}' = '${valor}' não obedece ao formato esperado (${spec.formato_descricao || spec.regex}).` });
        continue;
      }
      if (spec.tamanho) {
        const alvo = spec.so_digitos ? soDigitos(valor) : valor;
        if (alvo.length !== spec.tamanho) {
          oc.push({ campo, tipo: 'formato_invalido', regra: 'TAMANHO', valor,
            descricao: `'${spec.rotulo}' deveria ter ${spec.tamanho} caracteres.` });
        }
      }
    }

    for (const regra of this.regras) this._regra(regra, linha, datas, numeros, oc);

    const atrasos = {};
    for (const t of this.tempestividade) {
      const ini = datas[t._ini], fim = datas[t._fim];
      if (ini === undefined || fim === undefined) continue;
      const dias = fim - ini;
      atrasos[t.id] = dias;
      if (t.prazo_dias !== undefined && dias > t.prazo_dias) {
        oc.push({ campo: t._fim, tipo: 'fora_do_prazo', regra: t.id, valor: String(dias),
          descricao: `${t.rotulo}: ${dias} dias (prazo de ${t.prazo_dias} dias).` });
      }
      if (dias < 0) {
        oc.push({ campo: t._fim, tipo: 'data_invalida', regra: t.id + '_NEGATIVO', valor: String(dias),
          descricao: `${t.rotulo}: intervalo negativo (${dias} dias).` });
      }
    }

    if (duplicados) {
      for (const h of this.hashesDup(linha)) {
        if (!duplicados.has(h)) continue;
        const ch = this.chavesDup[Number(h.split('#')[0])];
        for (const campo of ch.campos) {
          oc.push({ campo, tipo: 'duplicidade', regra: ch.id || 'DUP', valor: this.valor(linha, campo),
            descricao: `${ch.nome || 'Chave duplicada'}: registro repetido por ${ch.campos.join(', ')}.` });
        }
      }
    }

    return { oc, atrasos, dataRef: cfg.data_referencia ? datas[cfg.data_referencia] : undefined };
  }

  _cond(se, linha) {
    const conds = condicoes(se);
    if (!conds.length) return true;
    const modo = (se && !Array.isArray(se) && se.modo) ? se.modo : 'todas';
    const res = conds.map(cond => {
      const campo = normalizarColuna(cond.campo || '');
      const valor = this.valor(linha, campo).toUpperCase();
      let ok = true;
      if (cond.valores) ok = cond.valores.map(v => String(v).toUpperCase()).includes(valor);
      if (cond.valores_diferentes_de) {
        ok = ok && !cond.valores_diferentes_de.map(v => String(v).toUpperCase()).includes(valor);
      }
      if (cond.preenchido === true) ok = ok && valor !== '';
      if (cond.preenchido === false) ok = ok && valor === '';
      return ok;
    });
    return modo === 'todas' ? res.every(Boolean) : res.some(Boolean);
  }

  _regra(regra, linha, datas, numeros, oc) {
    const rid = regra.id || regra.tipo;
    const desc = regra.descricao || rid;
    const tipoInc = regra.tipo_inconsistencia;

    switch (regra.tipo) {
      case 'ordem_datas': {
        const a = normalizarColuna(regra.campos[0]), b = normalizarColuna(regra.campos[1]);
        const da = datas[a], db = datas[b];
        if (da === undefined || db === undefined) return;
        const delta = db - da;
        const min = regra.min_dias === undefined ? 0 : regra.min_dias;
        const max = regra.max_dias;
        if (delta < min || (max !== undefined && delta > max)) {
          oc.push({ campo: b, tipo: tipoInc || 'data_invalida', regra: rid,
            valor: this.valor(linha, b), descricao: `${desc} (diferença observada: ${delta} dias).` });
        }
        return;
      }
      case 'condicional_obrigatorio': {
        if (!this._cond(regra.se, linha)) return;
        for (const bruto of regra.entao_preenchido || []) {
          const campo = normalizarColuna(bruto);
          const valor = this.valor(linha, campo);
          const spec = this.cfg.campos[campo];
          if (valor === '' || (spec && spec.ignorado.has(valor.toUpperCase()))) {
            oc.push({ campo, tipo: tipoInc || 'incoerencia', regra: rid, valor, descricao: desc });
          }
        }
        return;
      }
      case 'condicional_proibido': {
        if (!this._cond(regra.se, linha)) return;
        const campo = normalizarColuna(regra.entao_campo);
        const valor = this.valor(linha, campo).toUpperCase();
        const proibidos = (regra.valores_proibidos || []).map(v => String(v).toUpperCase());
        if (proibidos.includes(valor) || (regra.proibido_preenchido && valor !== '')) {
          oc.push({ campo, tipo: tipoInc || 'incoerencia', regra: rid,
            valor: this.valor(linha, campo), descricao: desc });
        }
        return;
      }
      case 'condicional_valores': {
        if (!this._cond(regra.se, linha)) return;
        const campo = normalizarColuna(regra.entao_campo);
        const valor = this.valor(linha, campo).toUpperCase();
        const esperados = (regra.valores_esperados || []).map(v => String(v).toUpperCase());
        if (valor !== '' && !esperados.includes(valor)) {
          oc.push({ campo, tipo: tipoInc || 'incoerencia', regra: rid,
            valor: this.valor(linha, campo), descricao: desc });
        }
        return;
      }
      case 'faixa_condicional': {
        if (!this._cond(regra.se, linha)) return;
        const campo = normalizarColuna(regra.campo);
        const n = numeros[campo] !== undefined ? numeros[campo] : converterNumero(this.valor(linha, campo));
        if (n === null || n === undefined) return;
        if ((regra.min !== undefined && n < regra.min) || (regra.max !== undefined && n > regra.max)) {
          oc.push({ campo, tipo: tipoInc || 'fora_de_faixa', regra: rid,
            valor: this.valor(linha, campo), descricao: `${desc} (valor: ${this.valor(linha, campo)}).` });
        }
        return;
      }
      case 'comparacao_numerica': {
        const a = normalizarColuna(regra.campo_a), b = normalizarColuna(regra.campo_b);
        const na = numeros[a] !== undefined ? numeros[a] : converterNumero(this.valor(linha, a));
        const nb = numeros[b] !== undefined ? numeros[b] : converterNumero(this.valor(linha, b));
        if (na === null || nb === null || na === undefined || nb === undefined) return;
        const op = regra.operador || '<=';
        const ok = { '<=': na <= nb, '<': na < nb, '>=': na >= nb, '>': na > nb,
          '==': na === nb, '!=': na !== nb }[op];
        if (ok === false) {
          oc.push({ campo: a, tipo: tipoInc || 'incoerencia', regra: rid,
            valor: this.valor(linha, a), descricao: desc });
        }
        return;
      }
      case 'coerencia_valores': {
        for (const comb of regra.combinacoes_proibidas || []) {
          const bate = Object.entries(comb).every(([k, v]) =>
            this.valor(linha, normalizarColuna(k)).toUpperCase() === String(v).toUpperCase());
          if (!bate) continue;
          for (const k of Object.keys(comb)) {
            const campo = normalizarColuna(k);
            oc.push({ campo, tipo: tipoInc || 'incoerencia', regra: rid,
              valor: this.valor(linha, campo), descricao: desc });
          }
        }
        return;
      }
      default:
    }
  }
}

function condicoes(se) {
  if (!se) return [];
  return Array.isArray(se) ? se : [se];
}

/* ----------------------------------------------------------- agregador */
class Agregador {
  constructor(motor) {
    this.motor = motor;
    this.cfg = motor.cfg;
    this.n = 0;
    this.nComInc = 0;
    this.nCompletos = 0;
    this.nOcorrencias = 0;
    this.porTipo = {};
    this.regPorTipo = {};
    this.porCampo = {};          // campo -> {tipo: n}
    this.porRegra = {};          // regra -> {n, tipo, descricao}
    this.preenchidos = {};
    this.vazios = {};
    this.preenchidosDominio = 0;
    this.valoresInvalidos = {};  // campo -> {valor: n}
    this.serie = {};             // AAAA-MM -> {registros, ocorrencias, comInc}
    this.estratos = {};          // campo -> valor -> {...}
    this.atrasos = {};           // id -> {dias: n}
    this.noPrazo = {};
    this.totalPrazo = {};
    this.diaMinEvento = null;
    this.diaMaxEvento = null;
    ORDEM_TIPOS.forEach(t => { this.porTipo[t] = 0; this.regPorTipo[t] = 0; });
    motor.camposAtivos.forEach(c => { this.preenchidos[c] = 0; this.vazios[c] = 0; this.porCampo[c] = {}; });
    motor.estratos.forEach(c => { this.estratos[c] = {}; });
  }

  adicionar(linha, resultado) {
    const m = this.motor;
    this.n++;
    let vaziosEssenciais = 0;
    for (const campo of m.camposAtivos) {
      if (m.valor(linha, campo) !== '') {
        this.preenchidos[campo]++;
        if (m.cfg.campos[campo].dominio) this.preenchidosDominio++;
      } else {
        this.vazios[campo]++;
        if (m.cfg.campos[campo].essencial) vaziosEssenciais++;
      }
    }
    if (!vaziosEssenciais) this.nCompletos++;

    const tiposNoRegistro = new Set();
    for (const o of resultado.oc) {
      this.nOcorrencias++;
      this.porTipo[o.tipo] = (this.porTipo[o.tipo] || 0) + 1;
      const alvo = this.porCampo[o.campo] || (this.porCampo[o.campo] = {});
      alvo[o.tipo] = (alvo[o.tipo] || 0) + 1;
      const r = this.porRegra[o.regra] || (this.porRegra[o.regra] = { n: 0, tipo: o.tipo, descricao: o.descricao });
      r.n++;
      tiposNoRegistro.add(o.tipo);
      if (['codigo_invalido', 'fora_de_faixa', 'data_invalida'].includes(o.tipo) && o.valor) {
        const mapa = this.valoresInvalidos[o.campo] || (this.valoresInvalidos[o.campo] = {});
        const chave = String(o.valor).slice(0, 60);
        if (Object.keys(mapa).length < 40 || chave in mapa) mapa[chave] = (mapa[chave] || 0) + 1;
      }
    }
    tiposNoRegistro.forEach(t => { this.regPorTipo[t] = (this.regPorTipo[t] || 0) + 1; });
    const temInc = resultado.oc.length > 0;
    if (temInc) this.nComInc++;

    for (const [id, dias] of Object.entries(resultado.atrasos)) {
      const hist = this.atrasos[id] || (this.atrasos[id] = {});
      hist[dias] = (hist[dias] || 0) + 1;
      this.totalPrazo[id] = (this.totalPrazo[id] || 0) + 1;
      const t = m.tempestividade.find(x => x.id === id);
      if (t && t.prazo_dias !== undefined && dias >= 0 && dias <= t.prazo_dias) {
        this.noPrazo[id] = (this.noPrazo[id] || 0) + 1;
      }
    }

    const dref = resultado.dataRef;
    if (dref !== undefined && dref !== null) {
      const chave = mesDe(dref);
      const b = this.serie[chave] || (this.serie[chave] = { registros: 0, ocorrencias: 0, comInc: 0 });
      b.registros++; b.ocorrencias += resultado.oc.length; if (temInc) b.comInc++;
      if (this.diaMinEvento === null || dref < this.diaMinEvento) this.diaMinEvento = dref;
      if (this.diaMaxEvento === null || dref > this.diaMaxEvento) this.diaMaxEvento = dref;
    }

    for (const campo of m.estratos) {
      let valor = m.valor(linha, campo) || '(em branco)';
      const mapa = this.estratos[campo];
      if (Object.keys(mapa).length >= 800 && !(valor in mapa)) valor = '(outros)';
      const b = mapa[valor] || (mapa[valor] = { registros: 0, ocorrencias: 0, comInc: 0 });
      b.registros++; b.ocorrencias += resultado.oc.length; if (temInc) b.comInc++;
    }
  }

  /* --------------------------------------------------------- indicadores */
  indicadores() {
    const m = this.motor;
    const N = this.n;
    const pct = (a, b) => (!b ? null : Math.round(1000 * a / b) / 10);
    const nCampos = m.camposAtivos.length;
    const celulas = N * nCampos;
    const celEssenciais = N * m.essenciais.length;
    let vaziosEssenciais = 0;
    m.essenciais.forEach(c => { vaziosEssenciais += (this.porCampo[c] || {}).em_branco || 0; });
    let celVazias = 0;
    Object.values(this.vazios).forEach(v => { celVazias += v; });
    const preenchidas = celulas - celVazias;
    const ign = this.porTipo.ignorado;
    const invalidos = this.porTipo.codigo_invalido + this.porTipo.data_invalida +
      this.porTipo.formato_invalido + this.porTipo.fora_de_faixa;
    const regIncoerentes = this.regPorTipo.incoerencia;
    const regDup = this.regPorTipo.duplicidade;
    const regData = this.regPorTipo.data_invalida;
    const regFaixa = this.regPorTipo.fora_de_faixa;

    const ind = [];
    const add = (nome, valor, num, den, formula, obs) => {
      const [classe, cor] = classificar(valor);
      ind.push({ atributo: nome, valor, numerador: num, denominador: den, formula,
        observacao: obs || '', classificacao: classe, cor });
    };

    add('Completude', pct(celEssenciais - vaziosEssenciais, celEssenciais),
      celEssenciais - vaziosEssenciais, celEssenciais,
      'campos essenciais preenchidos ÷ (registros × campos essenciais)');
    add('Suficiência', pct(this.nCompletos, N), this.nCompletos, N,
      'registros com TODOS os campos essenciais preenchidos ÷ registros');
    add('Confiabilidade', pct(preenchidas - ign, preenchidas), preenchidas - ign, preenchidas,
      "campos preenchidos com valor informativo ÷ campos preenchidos (exclui 'ignorado')");
    add('Validade', pct(this.preenchidosDominio - this.porTipo.codigo_invalido, this.preenchidosDominio),
      this.preenchidosDominio - this.porTipo.codigo_invalido, this.preenchidosDominio,
      'valores dentro do domínio ÷ valores preenchidos em campos com domínio definido');
    add('Correção', pct(preenchidas - invalidos, preenchidas), preenchidas - invalidos, preenchidas,
      'campos sem erro detectável (domínio, data, formato, faixa) ÷ campos preenchidos');
    const semFormatoFaixa = preenchidas - this.porTipo.fora_de_faixa - this.porTipo.formato_invalido;
    add('Precisão', pct(semFormatoFaixa, preenchidas), semFormatoFaixa, preenchidas,
      'campos sem erro de faixa/formato ÷ campos preenchidos');
    add('Coerência', pct(N - regIncoerentes, N), N - regIncoerentes, N,
      'registros sem incoerência entre campos ÷ registros');
    add('Logicidade', pct(Math.max(N - regIncoerentes - regData, 0), N),
      Math.max(N - regIncoerentes - regData, 0), N,
      'registros sem incoerência lógica nem data impossível ÷ registros');
    add('Singularidade', pct(N - regDup, N), N - regDup, N,
      'registros não duplicados ÷ registros');

    let numT = 0, denT = 0;
    Object.values(this.noPrazo).forEach(v => { numT += v; });
    Object.values(this.totalPrazo).forEach(v => { denT += v; });
    add('Tempestividade', pct(numT, denT), numT, denT,
      'registros dentro do prazo pactuado ÷ registros com as duas datas preenchidas');

    let defasagem = null, valorAtual = null;
    const prazoRef = this.cfg.parametros.defasagem_aceitavel_dias || 30;
    if (this.diaMaxEvento !== null) {
      defasagem = m.diaExtracao - this.diaMaxEvento;
      valorAtual = defasagem > prazoRef
        ? Math.round(10 * Math.max(0, Math.min(100, 100 * prazoRef / Math.max(defasagem, 1)))) / 10
        : 100;
    }
    add('Atualidade', valorAtual, defasagem, prazoRef,
      'defasagem entre a extração e o evento mais recente, comparada ao prazo aceitável',
      defasagem === null ? '' : `Defasagem observada: ${defasagem} dias`);

    const campoAbr = this.cfg.parametros.campo_abrangencia
      ? normalizarColuna(this.cfg.parametros.campo_abrangencia) : null;
    let valorAbr = null, numAbr = 0, denAbr = 0;
    const esperados = this.cfg.parametros.estratos_esperados || [];
    if (campoAbr && esperados.length && this.estratos[campoAbr]) {
      const presentes = new Set(Object.keys(this.estratos[campoAbr]));
      numAbr = esperados.filter(e => presentes.has(String(e))).length;
      denAbr = esperados.length;
      valorAbr = pct(numAbr, denAbr);
    } else if (campoAbr && campoAbr in this.preenchidos) {
      numAbr = this.preenchidos[campoAbr]; denAbr = N; valorAbr = pct(numAbr, denAbr);
    }
    add('Abrangência', valorAbr, numAbr, denAbr,
      'registros com o campo de território preenchido ÷ registros (ou estratos esperados presentes)');

    add('Formato', pct(preenchidas - this.porTipo.formato_invalido, preenchidas),
      preenchidas - this.porTipo.formato_invalido, preenchidas,
      'campos com máscara/estrutura corretas ÷ campos preenchidos');
    const suspeitos = regData + regFaixa + regIncoerentes;
    add('Veracidade', pct(Math.max(N - suspeitos, 0), N), Math.max(N - suspeitos, 0), N,
      'registros sem indício de erro material ÷ registros');
    const inequiv = preenchidas - ign - this.porTipo.codigo_invalido;
    add('Inequivocidade', pct(inequiv, preenchidas), inequiv, preenchidas,
      "campos com significado único (sem 'ignorado' e sem código fora do domínio) ÷ campos preenchidos");

    const totalDic = Object.keys(this.cfg.campos).length;
    add('Compatibilidade', pct(nCampos, totalDic), nCampos, totalDic,
      'campos do dicionário oficial presentes na exportação ÷ campos do dicionário');
    add('Mensurabilidade', pct(nCampos, totalDic), nCampos, totalDic,
      'variáveis necessárias aos indicadores do setor disponíveis na base');

    const uteis = preenchidas - ign - invalidos;
    add('Valor informativo', pct(uteis, celulas), uteis, celulas,
      'campos preenchidos, válidos e não ignorados ÷ total de campos da base');
    add('Ordem', pct(N - regData, N), N - regData, N,
      'registros com sequência cronológica coerente ÷ registros');

    return ind;
  }

  escoreGeral(indicadores) {
    let soma = 0, pesos = 0;
    for (const d of indicadores) {
      if (d.valor === null || d.valor === undefined) continue;
      const peso = PESOS_ATRIBUTO[d.atributo] || 1;
      soma += d.valor * peso; pesos += peso;
    }
    return pesos ? Math.round(10 * soma / pesos) / 10 : null;
  }

  resumoCampos() {
    const m = this.motor;
    const pct = (a, b) => (!b ? null : Math.round(1000 * a / b) / 10);
    const linhas = m.camposAtivos.map(campo => {
      const spec = m.cfg.campos[campo];
      const oc = this.porCampo[campo] || {};
      const total = Object.values(oc).reduce((a, b) => a + b, 0);
      const preench = this.preenchidos[campo] || 0;
      const invalidos = (oc.codigo_invalido || 0) + (oc.data_invalida || 0) +
        (oc.formato_invalido || 0) + (oc.fora_de_faixa || 0);
      const frequentes = Object.entries(this.valoresInvalidos[campo] || {})
        .sort((a, b) => b[1] - a[1]).slice(0, 6);
      return { campo, rotulo: spec.rotulo, bloco: spec.bloco, essencial: spec.essencial,
        preenchidos: preench, vazios: this.vazios[campo] || 0,
        pctPreenchimento: pct(preench, this.n), ignorados: oc.ignorado || 0,
        pctIgnorado: pct(oc.ignorado || 0, Math.max(preench, 1)), invalidos,
        incoerencias: oc.incoerencia || 0, duplicidades: oc.duplicidade || 0,
        foraPrazo: oc.fora_do_prazo || 0, total, tipos: oc, frequentes };
    });
    linhas.sort((a, b) => b.total - a.total || a.campo.localeCompare(b.campo));
    return linhas;
  }

  resumoRegras() {
    return Object.entries(this.porRegra)
      .map(([regra, d]) => ({ regra, tipo: d.tipo, descricao: d.descricao, n: d.n,
        pct: this.n ? Math.round(1000 * d.n / this.n) / 10 : null }))
      .sort((a, b) => b.n - a.n);
  }

  resumoTempestividade() {
    const quantil = (pares, total, q) => {
      let acc = 0;
      for (const [v, f] of pares) { acc += f; if (acc >= q * total) return v; }
      return pares.length ? pares[pares.length - 1][0] : null;
    };
    return Object.entries(this.atrasos).map(([id, hist]) => {
      const pares = Object.entries(hist).map(([d, f]) => [Number(d), f]).sort((a, b) => a[0] - b[0]);
      const total = pares.reduce((a, b) => a + b[1], 0);
      const t = this.motor.tempestividade.find(x => x.id === id) || {};
      const soma = pares.reduce((a, b) => a + b[0] * b[1], 0);
      return { id, rotulo: t.rotulo || id, prazo: t.prazo_dias, registros: total,
        noPrazo: this.noPrazo[id] || 0,
        pctNoPrazo: total ? Math.round(1000 * (this.noPrazo[id] || 0) / total) / 10 : null,
        media: total ? Math.round(10 * soma / total) / 10 : null,
        p25: quantil(pares, total, 0.25), mediana: quantil(pares, total, 0.5),
        p75: quantil(pares, total, 0.75), p90: quantil(pares, total, 0.9),
        maximo: pares.length ? pares[pares.length - 1][0] : null,
        negativos: pares.filter(p => p[0] < 0).reduce((a, b) => a + b[1], 0),
        histograma: pares };
    });
  }

  resumoEstratos(campo, top) {
    const mapa = this.estratos[campo] || {};
    return Object.entries(mapa)
      .map(([valor, v]) => ({ valor, registros: v.registros, ocorrencias: v.ocorrencias,
        comInc: v.comInc,
        pctComInc: v.registros ? Math.round(1000 * v.comInc / v.registros) / 10 : null,
        porRegistro: v.registros ? Math.round(100 * v.ocorrencias / v.registros) / 100 : 0 }))
      .sort((a, b) => b.registros - a.registros).slice(0, top || 25);
  }

  resumoSerie() {
    return Object.entries(this.serie).sort((a, b) => a[0].localeCompare(b[0]))
      .map(([periodo, v]) => ({ periodo, registros: v.registros, ocorrencias: v.ocorrencias,
        comInc: v.comInc,
        pctComInc: v.registros ? Math.round(1000 * v.comInc / v.registros) / 10 : null }));
  }
}
