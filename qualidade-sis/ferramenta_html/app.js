/* QualiSIS no navegador — leitura do CSV, execução e interface.
   Tudo acontece na máquina do usuário: o arquivo nunca é enviado a lugar nenhum. */

'use strict';

const $ = sel => document.querySelector(sel);
const $$ = sel => Array.from(document.querySelectorAll(sel));
const TAM_BLOCO = 4 * 1024 * 1024;      // 4 MB por leitura
const LIMITE_LINHAS_TABELA = 20000;     // linhas inconsistentes guardadas para exibir/exportar
const LIMITE_OCORRENCIAS_CSV = 300000;

const estado = {
  sistema: null,
  arquivo: null,
  arquivoAnterior: null,
  resultado: null,
  pagina: 0,
  filtroTipo: '',
  filtroTexto: ''
};

/* ---------------------------------------------------------------- formato */
function nBR(v, casas) {
  if (v === null || v === undefined || v === '' || Number.isNaN(v)) return '—';
  return Number(v).toLocaleString('pt-BR',
    { minimumFractionDigits: casas || 0, maximumFractionDigits: casas || 0 });
}
function pctBR(v) { return (v === null || v === undefined) ? '—' : nBR(v, 1) + '%'; }
function esc(txt) {
  return String(txt === null || txt === undefined ? '' : txt)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function tamanhoLegivel(bytes) {
  const un = ['B', 'KB', 'MB', 'GB'];
  let i = 0, v = bytes;
  while (v >= 1024 && i < un.length - 1) { v /= 1024; i++; }
  return nBR(v, i ? 1 : 0) + ' ' + un[i];
}

/* --------------------------------------------------------- leitura do CSV */
class ParserCSV {
  constructor(sep) {
    this.sep = sep; this.resto = ''; this.emAspas = false; this.campos = []; this.campo = '';
  }
  alimentar(txt, cb) {
    if (!this.emAspas && this.campo === '' && this.campos.length === 0 && txt.indexOf('"') === -1) {
      const buffer = this.resto + txt;
      const linhas = buffer.split('\n');
      this.resto = linhas.pop();
      for (const l of linhas) {
        const lim = l.charCodeAt(l.length - 1) === 13 ? l.slice(0, -1) : l;
        if (lim !== '') cb(lim.split(this.sep));
      }
      return;
    }
    const s = this.resto + txt;
    this.resto = '';
    for (let i = 0; i < s.length; i++) {
      const ch = s[i];
      if (this.emAspas) {
        if (ch === '"') {
          if (s[i + 1] === '"') { this.campo += '"'; i++; } else { this.emAspas = false; }
        } else { this.campo += ch; }
        continue;
      }
      if (ch === '"' && this.campo === '') { this.emAspas = true; continue; }
      if (ch === this.sep) { this.campos.push(this.campo); this.campo = ''; continue; }
      if (ch === '\n') {
        this.campos.push(this.campo);
        const linha = this.campos;
        this.campos = []; this.campo = '';
        if (!(linha.length === 1 && linha[0].trim() === '')) cb(linha);
        continue;
      }
      if (ch === '\r') continue;
      this.campo += ch;
    }
  }
  finalizar(cb) {
    if (this.resto) this.alimentar('\n', cb);
    if (this.campo !== '' || this.campos.length) {
      this.campos.push(this.campo);
      const linha = this.campos;
      this.campos = []; this.campo = '';
      if (!(linha.length === 1 && linha[0].trim() === '')) cb(linha);
    }
  }
}

/* --------------------------------------------------------- leitura do DBF */
class ParserDBF {
  static async lerArquivo(file, cb) {
    const cabecalho = new Uint8Array(await file.slice(0, 32).arrayBuffer());
    const numRegistros = new DataView(cabecalho.buffer).getUint32(4, true);
    const tamHeader = new DataView(cabecalho.buffer).getUint16(8, true);
    const tamRegistro = new DataView(cabecalho.buffer).getUint16(10, true);

    const campos = [];
    const fieldData = new Uint8Array(await file.slice(32, tamHeader).arrayBuffer());
    for (let i = 0; i < fieldData.length; i += 32) {
      if (fieldData[i] === 0x0D) break;
      const nome = new TextDecoder().decode(fieldData.slice(i, i + 11)).split('\0')[0].trim();
      const tipo = String.fromCharCode(fieldData[i + 11]);
      const tamanho = fieldData[i + 16];
      const decimais = fieldData[i + 17];
      if (nome) campos.push({ nome, tipo, tamanho, decimais });
    }

    cb(campos.map(c => c.nome));

    const offset = tamHeader;
    for (let regNum = 0; regNum < numRegistros; regNum++) {
      const inicio = offset + regNum * tamRegistro;
      const fim = Math.min(inicio + tamRegistro, file.size);
      const regData = new Uint8Array(await file.slice(inicio, fim).arrayBuffer());

      if (regData[0] !== 0x20) continue;

      const valores = [];
      let pos = 1;
      for (const campo of campos) {
        const dados = regData.slice(pos, pos + campo.tamanho);
        pos += campo.tamanho;
        const txt = new TextDecoder().decode(dados).trim();
        valores.push(txt);
      }
      cb(valores);
    }
  }
}

async function detectarFormato(file) {
  const amostraBuf = await file.slice(0, 32).arrayBuffer();
  const primeirosBytes = new Uint8Array(amostraBuf);

  // Detecta DBF: tipo de arquivo + ano >= 2000
  if ([0x03, 0x83, 0x8B, 0xCB].includes(primeirosBytes[0])) {
    const ano = primeirosBytes[1] + 1900;
    if (ano >= 1900 && ano <= 2100) return { tipo: 'dbf' };
  }

  // Senão, trata como CSV
  const totalBuf = await file.slice(0, Math.min(file.size, 262144)).arrayBuffer();
  let encoding = 'utf-8';
  try { new TextDecoder('utf-8', { fatal: true }).decode(totalBuf); }
  catch (e) { encoding = 'windows-1252'; }
  const texto = new TextDecoder(encoding).decode(totalBuf);
  const primeira = texto.split('\n')[0] || '';
  let sep = ';', melhor = 0;
  for (const cand of [';', ',', '\t', '|']) {
    const qtd = primeira.split(cand).length - 1;
    if (qtd > melhor) { melhor = qtd; sep = cand; }
  }
  return { tipo: 'csv', encoding, sep };
}

async function percorrer(file, formato, aoLinha, aoProgresso) {
  if (formato.tipo === 'dbf') {
    let numero = 0;
    await ParserDBF.lerArquivo(file, (dados) => {
      numero++;
      aoLinha(dados, numero);
      if (aoProgresso && numero % 100 === 0) {
        aoProgresso(Math.min(numero / 10000, 1), numero);
      }
    });
    return numero;
  }

  const parser = new ParserCSV(formato.sep);
  const decoder = new TextDecoder(formato.encoding);
  let lido = 0, numero = 0;
  for (let off = 0; off < file.size; off += TAM_BLOCO) {
    const buf = await file.slice(off, off + TAM_BLOCO).arrayBuffer();
    lido += buf.byteLength;
    const texto = decoder.decode(buf, { stream: true });
    parser.alimentar(texto, campos => { numero++; aoLinha(campos, numero); });
    if (aoProgresso) {
      aoProgresso(lido / file.size, numero);
      await new Promise(r => setTimeout(r, 0));
    }
  }
  parser.finalizar(campos => { numero++; aoLinha(campos, numero); });
  return numero;
}

/* --------------------------------------------------------------- análise */
function colunasDe(cabecalho, cfg) {
  const vistas = {};
  return cabecalho.map((bruto, i) => {
    let nome = normalizarColuna(bruto);
    if (cfg.apelidos[nome]) nome = cfg.apelidos[nome];
    if (!nome) nome = 'COLUNA_' + (i + 1);
    if (vistas[nome]) { vistas[nome]++; nome = nome + '_' + vistas[nome]; } else { vistas[nome] = 1; }
    return nome;
  });
}

async function analisar(file, cfgBruta, opcoes) {
  const op = opcoes || {};
  const aoEtapa = op.aoEtapa || (() => {});
  const cfg = prepararConfig(cfgBruta);
  const formato = await detectarFormato(file);

  const diaExtracao = op.diaExtracao !== undefined && op.diaExtracao !== null
    ? op.diaExtracao : Math.floor(file.lastModified / 86400000);

  /* --- passagem 1: cabeçalho e duplicidades ---------------------------- */
  let colunas = null, motor = null;
  const vistos = new Set(), duplicados = new Set();
  await percorrer(file, formato, (campos, numero) => {
    if (numero === 1) {
      colunas = colunasDe(campos, cfg);
      motor = new Motor(cfg, colunas, diaExtracao);
      return;
    }
    for (const h of motor.hashesDup(campos)) {
      if (vistos.has(h)) duplicados.add(h); else vistos.add(h);
    }
  }, (fracao, n) => aoEtapa(1, fracao, n));
  vistos.clear();
  if (!motor) throw new Error('O arquivo parece vazio — não há nem uma linha de cabeçalho.');

  /* --- passagem 2: crítica registro a registro -------------------------- */
  const ag = new Agregador(motor);
  const linhas = [];
  const ocorrenciasCSV = [];
  let linhasOmitidas = 0;
  const chavesAtuais = new Set();
  const assinaturasAtuais = new Set();
  const comparar = !!op.anterior;
  const novas = {}, persistentes = {}, novasCampo = {}, persistentesCampo = {};

  await percorrer(file, formato, (campos, numero) => {
    if (numero === 1) return;
    const resultado = motor.avaliar(campos, duplicados);
    ag.adicionar(campos, resultado);

    const chaveHash = hashTexto(motor.chaveRegistro(campos) || ('__linha__' + numero));
    if (comparar) chavesAtuais.add(chaveHash);

    if (resultado.oc.length) {
      if (linhas.length < LIMITE_LINHAS_TABELA) {
        const porCampo = {};
        let gravidade = 0;
        const tiposPresentes = [];
        const detalhes = [];
        for (const o of resultado.oc) {
          const atual = porCampo[o.campo];
          if (!atual || TIPOS[o.tipo].peso > TIPOS[atual].peso) porCampo[o.campo] = o.tipo;
          gravidade += TIPOS[o.tipo].peso;
          if (!tiposPresentes.includes(o.tipo)) tiposPresentes.push(o.tipo);
          if (detalhes.length < 12) detalhes.push(`[${TIPOS[o.tipo].rotulo}] ${o.descricao}`);
        }
        tiposPresentes.sort((a, b) => TIPOS[b].peso - TIPOS[a].peso);
        linhas.push({ numero, valores: campos, porCampo, tipos: tiposPresentes,
          dominante: tiposPresentes[0], gravidade: Math.round(gravidade * 10) / 10,
          qtd: resultado.oc.length, detalhe: detalhes.join(' | '),
          chave: motor.chaveRegistro(campos).replace(/\|+$/, '') });
      } else {
        linhasOmitidas++;
      }
      for (const o of resultado.oc) {
        if (ocorrenciasCSV.length < LIMITE_OCORRENCIAS_CSV) {
          ocorrenciasCSV.push([numero, motor.chaveRegistro(campos), o.campo,
            (cfg.campos[o.campo] || {}).rotulo || o.campo, o.tipo, TIPOS[o.tipo].rotulo,
            o.regra, o.valor, o.descricao]);
        }
        if (comparar) {
          const assinatura = chaveHash + '|' + o.campo + '|' + o.tipo + '|' + o.regra;
          assinaturasAtuais.add(assinatura);
          if (op.anterior.assinaturas.has(assinatura)) {
            persistentes[o.tipo] = (persistentes[o.tipo] || 0) + 1;
            persistentesCampo[o.campo] = (persistentesCampo[o.campo] || 0) + 1;
          } else {
            novas[o.tipo] = (novas[o.tipo] || 0) + 1;
            novasCampo[o.campo] = (novasCampo[o.campo] || 0) + 1;
          }
        }
      }
    }
  }, (fracao, n) => aoEtapa(2, fracao, n));

  /* --- comparação com o envio anterior --------------------------------- */
  let comparacao = null;
  if (comparar) {
    const corrigidas = {}, semRegistro = {}, corrigidasCampo = {};
    let registrosNovos = 0, registrosMantidos = 0;
    chavesAtuais.forEach(c => {
      if (op.anterior.chaves.has(c)) registrosMantidos++; else registrosNovos++;
    });
    let registrosAusentes = 0;
    op.anterior.chaves.forEach(c => { if (!chavesAtuais.has(c)) registrosAusentes++; });
    op.anterior.assinaturas.forEach(ass => {
      if (assinaturasAtuais.has(ass)) return;
      const partes = ass.split('|');
      const chave = partes[0], campo = partes[1], tipo = partes[2];
      if (chavesAtuais.has(chave)) {
        corrigidas[tipo] = (corrigidas[tipo] || 0) + 1;
        corrigidasCampo[campo] = (corrigidasCampo[campo] || 0) + 1;
      } else {
        semRegistro[tipo] = (semRegistro[tipo] || 0) + 1;
      }
    });
    const soma = o => Object.values(o).reduce((a, b) => a + b, 0);
    comparacao = { corrigidas, persistentes, novas, semRegistro, corrigidasCampo,
      persistentesCampo, novasCampo, registrosNovos, registrosMantidos, registrosAusentes,
      totalCorrigidas: soma(corrigidas), totalPersistentes: soma(persistentes),
      totalNovas: soma(novas), totalSemRegistro: soma(semRegistro),
      registrosAnterior: op.anterior.chaves.size, arquivo: op.anterior.nome };
    const base = comparacao.totalCorrigidas + comparacao.totalPersistentes;
    comparacao.resolutividade = base ? Math.round(1000 * comparacao.totalCorrigidas / base) / 10 : null;
  }

  const indicadores = ag.indicadores();
  return { cfg, motor, ag, colunas, formato, linhas, linhasOmitidas, ocorrenciasCSV,
    indicadores, escore: ag.escoreGeral(indicadores), comparacao, diaExtracao,
    arquivo: file.name, tamanho: file.size,
    duplicidadesEncontradas: duplicados.size };
}

/** Processa o envio anterior só para extrair as assinaturas das ocorrências. */
async function assinaturasDe(file, cfgBruta, aoEtapa, diaExtracao) {
  const cfg = prepararConfig(cfgBruta);
  const formato = await detectarFormato(file);
  const dia = diaExtracao !== undefined && diaExtracao !== null
    ? diaExtracao : Math.floor(file.lastModified / 86400000);
  let colunas = null, motor = null;
  const vistos = new Set(), duplicados = new Set();
  await percorrer(file, formato, (campos, numero) => {
    if (numero === 1) { colunas = colunasDe(campos, cfg); motor = new Motor(cfg, colunas, dia); return; }
    for (const h of motor.hashesDup(campos)) {
      if (vistos.has(h)) duplicados.add(h); else vistos.add(h);
    }
  }, (f, n) => aoEtapa(0, f, n));
  vistos.clear();
  const chaves = new Set(), assinaturas = new Set();
  await percorrer(file, formato, (campos, numero) => {
    if (numero === 1) return;
    const r = motor.avaliar(campos, duplicados);
    const chaveHash = hashTexto(motor.chaveRegistro(campos) || ('__linha__' + numero));
    chaves.add(chaveHash);
    for (const o of r.oc) assinaturas.add(chaveHash + '|' + o.campo + '|' + o.tipo + '|' + o.regra);
  }, (f, n) => aoEtapa(0.5, f, n));
  return { chaves, assinaturas, nome: file.name };
}

/* ------------------------------------------------------------- interface */
function montarSistemas() {
  const alvo = $('#sistemas');
  alvo.innerHTML = '';
  const ordem = ['sim', 'sinasc', 'sinan', 'sinan_online', 'esus_sinan'];
  const listadas = Object.keys(CONFIGS).sort((a, b) => {
    const ia = ordem.indexOf(a), ib = ordem.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
  });
  listadas.forEach(sigla => {
    const cfg = CONFIGS[sigla];
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'sistema';
    b.setAttribute('aria-pressed', 'false');
    b.dataset.sigla = sigla;
    b.innerHTML = `<b>${esc(cfg.sistema)}</b><small>${esc(cfg.nome_completo)}</small>`;
    b.addEventListener('click', () => {
      estado.sistema = sigla;
      $$('.sistema').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.sigla === sigla)));
      atualizarBotao();
    });
    alvo.appendChild(b);
  });
}

function atualizarBotao() {
  const pronto = !!(estado.sistema && estado.arquivo);
  $('#analisar').disabled = !pronto;
  $('#resumo-escolha').innerHTML = pronto
    ? `Pronto: <strong>${esc(CONFIGS[estado.sistema].sistema)}</strong> · <code>${esc(estado.arquivo.name)}</code> (${tamanhoLegivel(estado.arquivo.size)})`
    : 'Escolha o sistema e o arquivo para liberar o botão.';
}

function ligarArquivo(inputId, zonaId, campo, rotuloId) {
  const input = $(inputId), zona = $(zonaId);
  const definir = file => {
    if (!file) return;
    estado[campo] = file;
    $(rotuloId).innerHTML = `<strong>${esc(file.name)}</strong> · ${tamanhoLegivel(file.size)}`;
    atualizarBotao();
  };
  input.addEventListener('change', () => definir(input.files[0]));
  ['dragenter', 'dragover'].forEach(ev => zona.addEventListener(ev, e => {
    e.preventDefault(); zona.classList.add('sobre');
  }));
  ['dragleave', 'drop'].forEach(ev => zona.addEventListener(ev, e => {
    e.preventDefault(); zona.classList.remove('sobre');
  }));
  zona.addEventListener('drop', e => definir(e.dataTransfer.files[0]));
  zona.addEventListener('click', e => { if (e.target.tagName !== 'BUTTON') input.click(); });
  zona.querySelectorAll('button').forEach(b => b.addEventListener('click', () => input.click()));
}

function mostrarProgresso(texto, fracao) {
  $('#progresso').classList.remove('oculto');
  $('#barra').style.width = Math.round(fracao * 100) + '%';
  $('#texto-progresso').textContent = texto;
}

async function executar() {
  const cfg = CONFIGS[estado.sistema];
  $('#analisar').disabled = true;
  $('#erro').classList.add('oculto');
  $('#resultados').innerHTML = '';
  const dataInf = $('#data-extracao').value;
  const diaExtracao = dataInf ? converterData(dataInf) : null;

  try {
    let anterior = null;
    const temAnterior = !!estado.arquivoAnterior;
    const passos = temAnterior ? 4 : 2;
    let passoAtual = 0;
    const etapa = (qual, fracao, n) => {
      const nomes = { 0: 'Lendo o envio anterior', 0.5: 'Analisando o envio anterior',
        1: 'Procurando duplicidades', 2: 'Aplicando as críticas' };
      const base = { 0: 0, 0.5: 1, 1: temAnterior ? 2 : 0, 2: temAnterior ? 3 : 1 }[qual];
      mostrarProgresso(`${nomes[qual]} — ${nBR(n)} registros lidos`,
        (base + fracao) / passos);
    };

    if (temAnterior) {
      anterior = await assinaturasDe(estado.arquivoAnterior, cfg, etapa, diaExtracao);
    }
    const resultado = await analisar(estado.arquivo, cfg,
      { aoEtapa: etapa, anterior, diaExtracao });
    estado.resultado = resultado;
    estado.pagina = 0;
    mostrarProgresso('Concluído.', 1);
    setTimeout(() => $('#progresso').classList.add('oculto'), 600);
    renderizar(resultado);
    $('#navegacao').classList.remove('oculto');
    $('#resultados').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (erro) {
    console.error(erro);
    $('#progresso').classList.add('oculto');
    const caixa = $('#erro');
    caixa.classList.remove('oculto');
    caixa.innerHTML = `<strong>Não foi possível analisar este arquivo.</strong><br>${esc(erro.message || erro)}
      <br><br>Confira se o arquivo é o CSV exportado do sistema e se o sistema escolhido é o certo.`;
  } finally {
    $('#analisar').disabled = false;
  }
}

/* ---------------------------------------------------------- renderização */
function medidor(valor, cor) {
  const v = valor === null || valor === undefined ? 0 : Math.max(0, Math.min(100, valor));
  return `<div class="medidor"><span class="valor">${pctBR(valor)}</span>
    <span class="trilho"><span class="preenchido" style="width:${v}%;background:${cor}"></span></span></div>`;
}
function pastilha(texto, cor) {
  return `<span class="pastilha" style="color:${cor}">${esc(texto)}</span>`;
}
function amostra(tipo) { return `<span class="amostra" style="background:var(--c-${tipo})"></span>`; }

function legendaTipos(tiposUsados) {
  return `<div class="legenda">${tiposUsados.map(t =>
    `<span>${amostra(t)}${esc(TIPOS[t].rotulo)}</span>`).join('')}</div>`;
}

function renderizar(r) {
  const ag = r.ag, m = r.motor;
  const partes = [];
  const [faixa, cor] = classificar(r.escore);
  const tiposUsados = ORDEM_TIPOS.filter(t => ag.porTipo[t] > 0);

  /* resumo ------------------------------------------------------------- */
  const ladrilhos = [
    ['Registros analisados', nBR(ag.n), 'linhas da base'],
    ['Registros com inconsistência', nBR(ag.nComInc),
      pctBR(ag.n ? 100 * ag.nComInc / ag.n : null) + ' do total'],
    ['Ocorrências detectadas', nBR(ag.nOcorrencias),
      nBR(ag.n ? ag.nOcorrencias / ag.n : 0, 2) + ' por registro'],
    ['Registros completos', nBR(ag.nCompletos), 'todos os campos essenciais preenchidos']
  ];
  if (r.comparacao) {
    ladrilhos.push(['Resolutividade', pctBR(r.comparacao.resolutividade),
      `${nBR(r.comparacao.totalCorrigidas)} corrigidas desde o envio anterior`]);
  }
  partes.push(`<section class="painel" id="p-resumo">
    <div class="cabeca-painel"><h2>Resumo da base</h2>
      <span class="nota">${esc(r.arquivo)} · ${tamanhoLegivel(r.tamanho)} ·
      eventos de ${dataParaTexto(ag.diaMinEvento)} a ${dataParaTexto(ag.diaMaxEvento)}</span></div>
    <div class="heroi"><div class="escore" style="color:${cor}">${pctBR(r.escore)}</div>
      <div>${pastilha(faixa, cor)}
      <p class="nota" style="margin-top:6px">Escore global ponderado dos atributos que podem ser
      medidos na base. Compare cada sistema com ele mesmo ao longo do tempo.</p></div></div>
    <div class="mosaico">${ladrilhos.map(([rot, val, obs]) =>
      `<div class="ladrilho"><div class="rot">${esc(rot)}</div><div class="val">${val}</div>
       <div class="obs">${esc(obs)}</div></div>`).join('')}</div>
  </section>`);

  /* indicadores --------------------------------------------------------- */
  partes.push(`<section class="painel" id="p-indicadores">
    <h2>Indicadores por atributo de qualidade</h2>
    <p class="nota">Cada percentual traz numerador, denominador e fórmula — dá para refazer a conta
    à mão. Os atributos que não se medem na base (clareza, acessibilidade, segurança, utilidade…)
    são avaliados pelo instrumento em planilha, descrito na metodologia.</p>
    <div class="rolagem"><table><thead><tr><th>Atributo</th><th>Indicador</th>
      <th>Classificação</th><th class="num">Numerador</th><th class="num">Denominador</th>
      <th>Como é calculado</th></tr></thead><tbody>
      ${r.indicadores.map(d => `<tr>
        <td><strong>${esc(d.atributo)}</strong></td>
        <td style="min-width:170px">${medidor(d.valor, d.cor)}</td>
        <td>${d.valor === null ? '—' : pastilha(d.classificacao, d.cor)}</td>
        <td class="num">${nBR(d.numerador)}</td><td class="num">${nBR(d.denominador)}</td>
        <td class="nota">${esc(d.formula)}${d.observacao ? ' — ' + esc(d.observacao) : ''}</td>
      </tr>`).join('')}
    </tbody></table></div></section>`);

  /* tipos --------------------------------------------------------------- */
  const maxTipo = Math.max(...ORDEM_TIPOS.map(t => ag.porTipo[t] || 0), 1);
  partes.push(`<section class="painel" id="p-tipos">
    <h2>Inconsistências por tipo</h2>
    <p class="nota">A cor de cada tipo é a mesma usada na tabela de linhas, mais abaixo.</p>
    <div class="rolagem"><table><thead><tr><th>Tipo</th><th class="num">Ocorrências</th>
      <th>Peso no total</th><th class="num">Registros atingidos</th><th class="num">% dos registros</th>
      <th>Gravidade</th><th>Atributos impactados</th></tr></thead><tbody>
      ${tiposUsados.map(t => {
        const n = ag.porTipo[t], regs = ag.regPorTipo[t];
        return `<tr><td>${amostra(t)}<strong>${esc(TIPOS[t].rotulo)}</strong>
          <div class="nota" style="font-size:12px">${esc(TIPOS[t].descricao)}</div></td>
          <td class="num">${nBR(n)}</td>
          <td style="min-width:150px"><div class="medidor"><span class="valor">${pctBR(100 * n / ag.nOcorrencias)}</span>
            <span class="trilho"><span class="preenchido" style="width:${100 * n / maxTipo}%;background:var(--c-${t})"></span></span></div></td>
          <td class="num">${nBR(regs)}</td><td class="num">${pctBR(100 * regs / ag.n)}</td>
          <td>${esc(TIPOS[t].gravidade)}</td><td class="nota">${esc(TIPOS[t].atributos)}</td></tr>`;
      }).join('')}
    </tbody></table></div></section>`);

  /* campos -------------------------------------------------------------- */
  const campos = ag.resumoCampos();
  partes.push(`<section class="painel" id="p-campos">
    <h2>Campo a campo</h2>
    <p class="nota">Ordenado pelo total de problemas. É desta lista que sai o que cobrar das
    unidades notificadoras.</p>
    ${legendaTipos(tiposUsados)}
    <div class="rolagem"><table><thead><tr><th>Campo</th><th>Essencial</th><th>Preenchimento</th>
      <th class="num">Em branco</th><th class="num">Ignorados</th><th class="num">Inválidos</th>
      <th class="num">Incoerências</th><th class="num">Duplicidades</th><th class="num">Fora do prazo</th>
      <th>Valores inválidos mais frequentes</th></tr></thead><tbody>
      ${campos.slice(0, 60).map(l => {
        const [, corC] = classificar(l.pctPreenchimento);
        return `<tr><td><strong>${esc(l.rotulo)}</strong><div class="nota mono" style="font-size:11.5px">${esc(l.campo)}</div></td>
        <td>${l.essencial ? 'Sim' : ''}</td><td style="min-width:160px">${medidor(l.pctPreenchimento, corC)}</td>
        <td class="num">${nBR(l.vazios)}</td><td class="num">${nBR(l.ignorados)}</td>
        <td class="num">${nBR(l.invalidos)}</td><td class="num">${nBR(l.incoerencias)}</td>
        <td class="num">${nBR(l.duplicidades)}</td><td class="num">${nBR(l.foraPrazo)}</td>
        <td class="nota">${esc(l.frequentes.map(([v, n]) => `${v} (${n})`).join('; '))}</td></tr>`;
      }).join('')}
    </tbody></table></div></section>`);

  /* prazos -------------------------------------------------------------- */
  const temp = ag.resumoTempestividade();
  if (temp.length) {
    partes.push(`<section class="painel" id="p-prazos">
      <h2>Prazos e oportunidade</h2>
      <p class="nota">Use a <strong>mediana</strong>, não a média: a média é puxada por poucos
      registros muito atrasados. Intervalo negativo não é atraso, é erro de digitação de data.</p>
      <div class="rolagem"><table><thead><tr><th>Indicador de prazo</th><th class="num">Prazo</th>
        <th class="num">Registros</th><th>Dentro do prazo</th><th class="num">Média</th>
        <th class="num">P25</th><th class="num">Mediana</th><th class="num">P75</th>
        <th class="num">P90</th><th class="num">Máximo</th><th class="num">Negativos</th>
      </tr></thead><tbody>
        ${temp.map(t => {
          const [, corT] = classificar(t.pctNoPrazo);
          return `<tr><td><strong>${esc(t.rotulo)}</strong></td><td class="num">${nBR(t.prazo)} d</td>
          <td class="num">${nBR(t.registros)}</td><td style="min-width:160px">${medidor(t.pctNoPrazo, corT)}</td>
          <td class="num">${nBR(t.media, 1)}</td><td class="num">${nBR(t.p25)}</td>
          <td class="num">${nBR(t.mediana)}</td><td class="num">${nBR(t.p75)}</td>
          <td class="num">${nBR(t.p90)}</td><td class="num">${nBR(t.maximo)}</td>
          <td class="num">${nBR(t.negativos)}</td></tr>`;
        }).join('')}
      </tbody></table></div></section>`);
  }

  /* estratos ------------------------------------------------------------ */
  if (m.estratos.length) {
    const blocos = m.estratos.map(campo => {
      const dados = ag.resumoEstratos(campo, 15);
      if (!dados.length) return '';
      const rot = (r.cfg.campos[campo] || {}).rotulo || campo;
      return `<h3>${esc(rot)}</h3><div class="rolagem"><table><thead><tr><th>Valor</th>
        <th class="num">Registros</th><th class="num">Ocorrências</th>
        <th>Registros com inconsistência</th><th class="num">Ocorrências por registro</th>
        </tr></thead><tbody>${dados.map(d => {
          const [, corE] = classificar(100 - (d.pctComInc || 0));
          return `<tr><td>${esc(d.valor)}</td><td class="num">${nBR(d.registros)}</td>
          <td class="num">${nBR(d.ocorrencias)}</td>
          <td style="min-width:160px">${medidor(d.pctComInc, corE)}</td>
          <td class="num">${nBR(d.porRegistro, 2)}</td></tr>`;
        }).join('')}</tbody></table></div>`;
    }).join('');
    partes.push(`<section class="painel" id="p-estratos"><h2>Onde estão os problemas</h2>
      <p class="nota">Por unidade notificadora, agravo, local de ocorrência — a lista de trabalho
      da devolutiva.</p>${blocos}</section>`);
  }

  /* comparativo --------------------------------------------------------- */
  if (r.comparacao) {
    const c = r.comparacao;
    const linhasTipo = ORDEM_TIPOS.map(t => {
      const corr = c.corrigidas[t] || 0, pers = c.persistentes[t] || 0, nov = c.novas[t] || 0;
      const sem = c.semRegistro[t] || 0;
      const antes = corr + pers + sem;
      if (!antes && !nov) return '';
      const resolvido = (corr + pers) ? Math.round(1000 * corr / (corr + pers)) / 10 : null;
      const [, corR] = classificar(resolvido);
      return `<tr><td>${amostra(t)}${esc(TIPOS[t].rotulo)}</td><td class="num">${nBR(antes)}</td>
        <td class="num">${nBR(corr)}</td><td style="min-width:150px">${medidor(resolvido, corR)}</td>
        <td class="num">${nBR(pers)}</td><td class="num">${nBR(nov)}</td>
        <td class="num">${nBR(sem)}</td></tr>`;
    }).join('');
    const tiles = [
      ['Taxa de resolutividade', pctBR(c.resolutividade), 'corrigidas ÷ (corrigidas + persistentes)'],
      ['Corrigidas', nBR(c.totalCorrigidas), 'apontadas antes e resolvidas'],
      ['Persistentes', nBR(c.totalPersistentes), 'apontadas antes e ainda abertas'],
      ['Novas', nBR(c.totalNovas), 'surgiram neste envio'],
      ['Registros novos', nBR(c.registrosNovos), 'entraram na base acumulada'],
      ['Registros que sumiram', nBR(c.registrosAusentes), 'conferir expurgo ou exclusão']
    ];
    partes.push(`<section class="painel" id="p-comparativo">
      <h2>Comparação com o envio anterior</h2>
      <p class="nota">Referência: <code>${esc(c.arquivo)}</code> (${nBR(c.registrosAnterior)} registros).
      Cada registro é acompanhado pela chave
      <code>${esc(r.cfg.chave_registro.join(' + ') || 'configurada')}</code>.</p>
      <div class="mosaico">${tiles.map(([rot, val, obs]) =>
        `<div class="ladrilho"><div class="rot">${esc(rot)}</div><div class="val">${val}</div>
         <div class="obs">${esc(obs)}</div></div>`).join('')}</div>
      <h3>Por tipo de inconsistência</h3>
      <div class="rolagem"><table><thead><tr><th>Tipo</th><th class="num">Existiam antes</th>
        <th class="num">Corrigidas</th><th>% resolvido</th><th class="num">Persistentes</th>
        <th class="num">Novas</th><th class="num">Sem registro</th></tr></thead>
        <tbody>${linhasTipo}</tbody></table></div>
      <div class="aviso">"Sem registro" são inconsistências do envio anterior cujo registro não
      está mais na base. Não conte como correção antes de conferir o que houve com ele.</div>
    </section>`);
  }

  /* providências --------------------------------------------------------- */
  partes.push(`<section class="painel" id="p-providencias"><h2>Providências sugeridas</h2>
    <ul class="providencias">${providencias(r).map(t => `<li>${t}</li>`).join('')}</ul></section>`);

  /* tabela de linhas ------------------------------------------------------ */
  partes.push(`<section class="painel" id="p-linhas">
    <div class="cabeca-painel"><h2>Linhas com inconsistência</h2>
      <span class="nota">${nBR(r.linhas.length)} linha(s) listada(s)${r.linhasOmitidas
        ? ` — outras ${nBR(r.linhasOmitidas)} não couberam na tela; use a exportação` : ''}</span></div>
    ${legendaTipos(tiposUsados)}
    <div class="filtros">
      <label class="campo">Tipo
        <select id="filtro-tipo"><option value="">todos</option>
          ${tiposUsados.map(t => `<option value="${t}">${esc(TIPOS[t].rotulo)}</option>`).join('')}
        </select></label>
      <label class="campo">Procurar
        <input type="search" id="filtro-texto" placeholder="nome, número, unidade…" size="26"></label>
      <span class="nota" id="contagem-filtro"></span>
    </div>
    <div class="tabelao" id="tabelao"></div>
    <div class="paginacao">
      <button class="botao discreto" id="pagina-anterior">← anteriores</button>
      <span id="rotulo-pagina"></span>
      <button class="botao discreto" id="pagina-proxima">próximas →</button>
    </div></section>`);

  /* exportar -------------------------------------------------------------- */
  partes.push(`<section class="painel" id="p-exportar"><h2>Levar o resultado para fora</h2>
    <p class="nota">A página inteira imprime em A4 (ou salva em PDF) pela impressão do navegador.
    Os arquivos abaixo abrem no Excel.</p>
    <div class="acoes-download">
      <button class="botao" id="btn-imprimir">Imprimir / salvar em PDF</button>
      <button class="botao secundario" id="btn-planilha">Baixar planilha colorida</button>
      <button class="botao secundario" id="btn-ocorrencias">Baixar lista de ocorrências (CSV)</button>
      <button class="botao secundario" id="btn-indicadores">Baixar indicadores (CSV)</button>
    </div>
    <p class="nota" id="aviso-download" style="margin-top:10px"></p>
    <h3>Ficha técnica desta análise</h3>
    <div class="rolagem"><table><tbody>
      ${[['Sistema', `${r.cfg.sistema} — ${r.cfg.nome_completo}`],
         ['Arquivo', r.arquivo], ['Tamanho', tamanhoLegivel(r.tamanho)],
         ['Codificação detectada', r.formato.encoding],
         ['Separador detectado', r.formato.sep === '\t' ? 'tabulação' : r.formato.sep],
         ['Data de extração considerada', dataParaTexto(r.diaExtracao)],
         ['Colunas no arquivo', nBR(r.colunas.length)],
         ['Campos avaliados', nBR(m.camposAtivos.length) + ' de ' + nBR(Object.keys(r.cfg.campos).length) + ' do dicionário'],
         ['Regras cruzadas aplicadas', nBR(m.regras.length)],
         ['Chaves de duplicidade', m.chavesDup.map(c => c.nome || c.id).join(' · ') || '—'],
         ['Campos do dicionário ausentes no arquivo',
          Object.keys(r.cfg.campos).filter(c => !m.camposAtivos.includes(c)).join(', ') || 'nenhum'],
         ['Colunas do arquivo fora do dicionário',
          r.colunas.filter(c => !(c in r.cfg.campos)).join(', ') || 'nenhuma'],
         ['Análise feita em', new Date().toLocaleString('pt-BR')]
        ].map(([k, v]) => `<tr><td style="width:270px"><strong>${esc(k)}</strong></td>
          <td class="nota">${esc(v)}</td></tr>`).join('')}
    </tbody></table></div></section>`);

  $('#resultados').innerHTML = partes.join('');
  ligarInteracoes(r);
  desenharTabela();
}

function providencias(r) {
  const ag = r.ag, itens = [];
  const campos = ag.resumoCampos();
  const brancos = campos.filter(c => c.essencial && (c.pctPreenchimento || 100) < 90).slice(0, 5);
  if (brancos.length) {
    itens.push('Priorizar o preenchimento dos campos essenciais com maior lacuna: ' +
      brancos.map(c => `<strong>${esc(c.rotulo)}</strong> (${pctBR(c.pctPreenchimento)} preenchido)`).join(', ') +
      ' — devolutiva às unidades e reforço no treinamento.');
  }
  const ign = campos.filter(c => (c.pctIgnorado || 0) > 10)
    .sort((a, b) => b.pctIgnorado - a.pctIgnorado).slice(0, 5);
  if (ign.length) {
    itens.push("Reduzir o uso do código 'ignorado' em " +
      ign.map(c => `<strong>${esc(c.rotulo)}</strong> (${pctBR(c.pctIgnorado)})`).join(', ') +
      ' — o campo consta preenchido, mas não gera informação utilizável.');
  }
  if (ag.regPorTipo.duplicidade) {
    itens.push(`Conferir <strong>${nBR(ag.regPorTipo.duplicidade)} registro(s)</strong> marcados como
      duplicidade (filtro "Duplicidade" na tabela) e resolver no sistema de origem. Duplicidade
      provável é hipótese a conferir, nunca ordem de exclusão automática.`);
  }
  ag.resumoTempestividade().forEach(t => {
    if (t.pctNoPrazo !== null && t.pctNoPrazo < 80) {
      itens.push(`Melhorar a oportunidade de <strong>${esc(t.rotulo)}</strong>: apenas
        ${pctBR(t.pctNoPrazo)} dentro do prazo de ${t.prazo} dias (mediana observada:
        ${nBR(t.mediana)} dias).`);
    }
    if (t.negativos) {
      itens.push(`Corrigir ${nBR(t.negativos)} registro(s) com intervalo negativo em
        <strong>${esc(t.rotulo)}</strong> — indica erro de digitação de data.`);
    }
  });
  r.motor.estratos.forEach(campo => {
    const piores = ag.resumoEstratos(campo, 200).filter(d => d.registros >= 30)
      .sort((a, b) => (b.pctComInc || 0) - (a.pctComInc || 0)).slice(0, 3);
    if (piores.length && piores[0].pctComInc) {
      const rot = (r.cfg.campos[campo] || {}).rotulo || campo;
      itens.push(`Pactuar plano de correção com os maiores focos em <strong>${esc(rot)}</strong>: ` +
        piores.map(d => `${esc(d.valor)} (${pctBR(d.pctComInc)})`).join(', ') + '.');
    }
  });
  if (r.comparacao) {
    if ((r.comparacao.resolutividade || 0) < 50) {
      itens.push(`Resolutividade abaixo de 50%: rever o fluxo de devolutiva — as listas estão
        chegando a quem pode corrigir? Há prazo pactuado de retorno?`);
    }
    if (r.comparacao.totalNovas > r.comparacao.totalCorrigidas) {
      itens.push(`Entraram mais inconsistências novas do que foram corrigidas: atuar na origem
        (crítica no momento da digitação), não só na correção posterior.`);
    }
  }
  const fracos = r.indicadores.filter(d => d.valor !== null)
    .sort((a, b) => a.valor - b.valor).slice(0, 3);
  if (fracos.length) {
    itens.push('Atributos com pior desempenho nesta avaliação: ' +
      fracos.map(d => `<strong>${esc(d.atributo)}</strong> (${pctBR(d.valor)})`).join(', ') +
      ' — definir meta de melhoria para o próximo envio.');
  }
  itens.push(`Guardar este arquivo CSV: na próxima análise, informe-o em "envio anterior" para
    medir quanto do que foi apontado hoje já terá sido corrigido.`);
  return itens;
}

/* ------------------------------------------------------- tabela de linhas */
function linhasFiltradas() {
  const r = estado.resultado;
  if (!r) return [];
  const texto = estado.filtroTexto.trim().toUpperCase();
  return r.linhas.filter(l => {
    if (estado.filtroTipo && !l.tipos.includes(estado.filtroTipo)) return false;
    if (texto && !l.valores.some(v => String(v).toUpperCase().includes(texto))) return false;
    return true;
  });
}

function desenharTabela() {
  const r = estado.resultado;
  if (!r) return;
  const POR_PAGINA = 100;
  const dados = linhasFiltradas();
  const total = dados.length;
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));
  if (estado.pagina >= paginas) estado.pagina = paginas - 1;
  const fatia = dados.slice(estado.pagina * POR_PAGINA, (estado.pagina + 1) * POR_PAGINA);

  const cabecalho = ['Linha', 'Chave', 'Problemas', 'Gravidade', 'Tipos']
    .concat(r.colunas.map(c => (r.cfg.campos[c] || {}).rotulo || c)).concat(['O que há de errado']);
  const corpo = fatia.map(l => {
    const celulas = r.colunas.map((c, i) => {
      const tipo = l.porCampo[c];
      return `<td class="${tipo || ''}">${esc(l.valores[i] === undefined ? '' : l.valores[i])}</td>`;
    }).join('');
    return `<tr class="marcada" style="--cor-linha:var(--c-${l.dominante})">
      <td>${l.numero}</td><td>${esc(l.chave)}</td><td class="num">${l.qtd}</td>
      <td class="num">${nBR(l.gravidade, 1)}</td>
      <td>${l.tipos.map(t => amostra(t)).join('')}${esc(l.tipos.map(t => TIPOS[t].rotulo).join(', '))}</td>
      ${celulas}<td class="detalhe" title="${esc(l.detalhe)}">${esc(l.detalhe)}</td></tr>`;
  }).join('');

  $('#tabelao').innerHTML = `<table><thead><tr>${cabecalho.map(c =>
    `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${corpo ||
    '<tr><td colspan="6">Nenhuma linha corresponde ao filtro.</td></tr>'}</tbody></table>`;
  $('#rotulo-pagina').textContent = `página ${estado.pagina + 1} de ${paginas}`;
  $('#contagem-filtro').textContent = `${nBR(total)} linha(s) no filtro atual`;
  $('#pagina-anterior').disabled = estado.pagina === 0;
  $('#pagina-proxima').disabled = estado.pagina >= paginas - 1;
}

/* -------------------------------------------------------------- exportar */
async function entregarArquivo(nome, conteudo, alternativaTxt) {
  const aviso = $('#aviso-download');
  const escrever = t => { if (aviso) aviso.textContent = t; };
  try {
    if (window.claude && typeof window.claude.use === 'function') {
      const downloads = await window.claude.use('downloads');
      if (downloads) {
        try {
          await downloads.save({ filename: nome, data: conteudo });
          escrever(`Arquivo "${nome}" enviado para download.`);
          return;
        } catch (erro) {
          if (erro && erro.code === 'extension_not_enabled' && alternativaTxt) {
            await downloads.save({ filename: alternativaTxt, data: conteudo });
            escrever(`Baixado como "${alternativaTxt}". Renomeie a extensão para abrir no Excel.`);
            return;
          }
          if (erro && erro.code === 'declined') { escrever('Download cancelado.'); return; }
          throw erro;
        }
      }
    }
    const blob = new Blob([conteudo], { type: 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = nome;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    escrever(`Arquivo "${nome}" salvo na pasta de downloads.`);
  } catch (erro) {
    escrever('Não foi possível salvar o arquivo aqui. Use "Imprimir / salvar em PDF", ' +
      'ou abra esta página salva no seu computador.');
    console.error(erro);
  }
}

function csvDe(cabecalho, linhas) {
  const limpa = v => {
    const t = String(v === null || v === undefined ? '' : v);
    return /[;"\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
  };
  return '﻿' + [cabecalho.join(';')].concat(linhas.map(l => l.map(limpa).join(';'))).join('\r\n');
}

function planilhaColorida() {
  const r = estado.resultado;
  /* cores claras fixas: a planilha abre no Excel com fundo branco, independentemente
     do tema em que a página estiver sendo vista */
  const cores = { duplicidade: '#FAE0DF', em_branco: '#FBEECB', ignorado: '#FBE1D3',
    codigo_invalido: '#E6E2FA', data_invalida: '#D9E8F8', incoerencia: '#D6EFE7',
    formato_invalido: '#FADFEB', fora_de_faixa: '#DFF0D4', fora_do_prazo: '#E6E9E8' };
  const cab = ['Linha', 'Chave', 'Problemas', 'Gravidade', 'Tipos']
    .concat(r.colunas.map(c => (r.cfg.campos[c] || {}).rotulo || c)).concat(['O que há de errado']);
  const linhas = r.linhas.map(l => {
    const celulas = r.colunas.map((c, i) => {
      const tipo = l.porCampo[c];
      const fundo = tipo ? ` style="background:${cores[tipo]}"` : '';
      return `<td${fundo}>${esc(l.valores[i] === undefined ? '' : l.valores[i])}</td>`;
    }).join('');
    const cor = cores[l.dominante];
    return `<tr><td style="background:${cor}">${l.numero}</td>
      <td style="background:${cor}">${esc(l.chave)}</td>
      <td style="background:${cor}">${l.qtd}</td>
      <td style="background:${cor}">${nBR(l.gravidade, 1)}</td>
      <td style="background:${cor}">${esc(l.tipos.map(t => TIPOS[t].rotulo).join(', '))}</td>
      ${celulas}<td>${esc(l.detalhe)}</td></tr>`;
  }).join('');
  const legenda = ORDEM_TIPOS.map(t =>
    `<tr><td style="background:${cores[t]}">${esc(TIPOS[t].rotulo)}</td>
     <td>${esc(TIPOS[t].descricao)}</td></tr>`).join('');
  return `<html><head><meta charset="utf-8"><title>Inconsistências ${esc(r.cfg.sistema)}</title></head>
    <body><h2>Inconsistências — ${esc(r.cfg.sistema)} — ${esc(r.arquivo)}</h2>
    <table border="1" cellspacing="0" cellpadding="3">
      <tr>${cab.map(c => `<th style="background:#2f4858;color:#fff">${esc(c)}</th>`).join('')}</tr>
      ${linhas}</table>
    <h3>Legenda das cores</h3><table border="1" cellspacing="0" cellpadding="3">${legenda}</table>
    </body></html>`;
}

/* ------------------------------------------------------------ interações */
function ligarInteracoes(r) {
  $('#filtro-tipo').addEventListener('change', e => {
    estado.filtroTipo = e.target.value; estado.pagina = 0; desenharTabela();
  });
  let temporizador = null;
  $('#filtro-texto').addEventListener('input', e => {
    clearTimeout(temporizador);
    const v = e.target.value;
    temporizador = setTimeout(() => {
      estado.filtroTexto = v; estado.pagina = 0; desenharTabela();
    }, 220);
  });
  $('#pagina-anterior').addEventListener('click', () => {
    if (estado.pagina > 0) { estado.pagina--; desenharTabela(); }
  });
  $('#pagina-proxima').addEventListener('click', () => { estado.pagina++; desenharTabela(); });
  $('#btn-imprimir').addEventListener('click', () => window.print());
  $('#btn-planilha').addEventListener('click', () => {
    entregarArquivo(`${r.cfg.sistema}_inconsistencias.html`, planilhaColorida(),
      `${r.cfg.sistema}_inconsistencias.txt`);
  });
  $('#btn-ocorrencias').addEventListener('click', () => {
    const csv = csvDe(['linha', 'chave', 'campo', 'rotulo', 'tipo', 'tipo_rotulo', 'regra',
      'valor', 'descricao'], r.ocorrenciasCSV);
    entregarArquivo(`${r.cfg.sistema}_ocorrencias.csv`, csv, `${r.cfg.sistema}_ocorrencias.txt`);
  });
  $('#btn-indicadores').addEventListener('click', () => {
    const csv = csvDe(['atributo', 'valor_pct', 'classificacao', 'numerador', 'denominador',
      'formula', 'observacao'],
      r.indicadores.map(d => [d.atributo, d.valor, d.classificacao, d.numerador, d.denominador,
        d.formula, d.observacao]));
    entregarArquivo(`${r.cfg.sistema}_indicadores.csv`, csv, `${r.cfg.sistema}_indicadores.txt`);
  });
}

/* ----------------------------------------------------------------- início */
document.addEventListener('DOMContentLoaded', () => {
  montarSistemas();
  ligarArquivo('#arquivo', '#zona-arquivo', 'arquivo', '#rotulo-arquivo');
  ligarArquivo('#arquivo-anterior', '#zona-anterior', 'arquivoAnterior', '#rotulo-anterior');
  $('#analisar').addEventListener('click', executar);
  $('#exemplo').addEventListener('click', carregarExemplo);
  atualizarBotao();
});

/* Base fictícia embutida, para conhecer a ferramenta sem usar dado real. */
function carregarExemplo() {
  const csv = gerarExemploSIM();
  const file = new File([csv], 'EXEMPLO_SIM_ficticio.csv', { type: 'text/csv' });
  estado.sistema = 'sim';
  $$('.sistema').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.sigla === 'sim')));
  estado.arquivo = file;
  $('#rotulo-arquivo').innerHTML =
    `<strong>EXEMPLO_SIM_ficticio.csv</strong> · ${tamanhoLegivel(file.size)} · dados inventados`;
  atualizarBotao();
  executar();
}
