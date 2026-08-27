/* Base fictícia do SIM, gerada na hora, para conhecer a ferramenta sem usar
   dado real. Nomes, números de DO e datas são inventados por sorteio.       */

'use strict';

function gerarExemploSIM(n) {
  n = n || 900;
  let semente = 20260807;
  const rnd = () => {                      // xorshift32: reprodutível e bem distribuído
    semente ^= semente << 13; semente >>>= 0;
    semente ^= semente >>> 17;
    semente ^= semente << 5; semente >>>= 0;
    return semente / 4294967296;
  };
  const escolha = lista => lista[Math.floor(rnd() * lista.length)];
  const inteiro = (a, b) => a + Math.floor(rnd() * (b - a + 1));
  const talvez = (prob, valor, alternativo) => (rnd() > prob ? valor : (alternativo || ''));

  const PRENOMES = ['MARIA', 'JOSE', 'ANA', 'JOAO', 'ANTONIO', 'FRANCISCA', 'CARLOS', 'PAULO',
    'ADRIANA', 'LUCAS', 'JULIANA', 'MARCOS', 'PATRICIA', 'RAFAEL', 'CAMILA', 'BRUNO'];
  const SOBRENOMES = ['SILVA', 'SANTOS', 'OLIVEIRA', 'SOUZA', 'PEREIRA', 'COSTA', 'RODRIGUES',
    'ALMEIDA', 'NASCIMENTO', 'LIMA', 'ARAUJO', 'FERREIRA', 'CARVALHO', 'GOMES'];
  const CNES = ['2748080', '0003859', '2400123', '6432198', '9999999', '2748081', '12345'];
  const CID = ['I219', 'J189', 'C349', 'E149', 'I64', 'A419', 'R99', 'W878', 'X959', 'V892'];
  const nome = () => `${escolha(PRENOMES)} ${escolha(SOBRENOMES)} ${escolha(SOBRENOMES)}`;
  const dataBR = dias => {
    const dt = new Date(dias * 86400000);
    const p = x => String(x).padStart(2, '0');
    return `${p(dt.getUTCDate())}/${p(dt.getUTCMonth() + 1)}/${dt.getUTCFullYear()}`;
  };

  const hoje = Math.floor(Date.now() / 86400000);
  const inicio = hoje - 400;
  const colunas = ['NUMERODO', 'TIPOBITO', 'DTOBITO', 'HORAOBITO', 'DTNASC', 'IDADE', 'SEXO',
    'RACACOR', 'ESTCIV', 'ESC', 'OCUP', 'CODMUNRES', 'LOCOCOR', 'CODESTAB', 'CODMUNOCOR',
    'IDADEMAE', 'GRAVIDEZ', 'GESTACAO', 'PARTO', 'OBITOPARTO', 'PESO', 'OBITOGRAV', 'OBITOPUERP',
    'ASSISTMED', 'EXAME', 'CIRURGIA', 'NECROPSIA', 'LINHAA', 'CAUSABAS', 'CIRCOBITO', 'ACIDTRAB',
    'FONTE', 'ATESTANTE', 'TPPOS', 'DTINVESTIG', 'DTCONINV', 'FONTEINV', 'DTCADASTRO',
    'NOME', 'NOMEMAE'];

  const linhas = [];
  for (let i = 0; i < n; i++) {
    const dtObito = inicio + inteiro(0, 330);
    const idade = inteiro(0, 95);
    const dtNasc = dtObito - idade * 365 - inteiro(0, 364);
    const sexo = escolha(['1', '2']);
    const fetal = rnd() < 0.08;
    const atraso = escolha([3, 7, 12, 20, 28, 35, 60, 95, 140]);
    const causa = talvez(0.04, escolha(CID), 'XX99');
    const investigado = rnd() < 0.25 ? 'S' : 'N';
    const reg = {
      NUMERODO: String(9000000 + i),
      TIPOBITO: fetal ? '1' : '2',
      DTOBITO: dataBR(dtObito),
      HORAOBITO: talvez(0.12, String(inteiro(0, 23)).padStart(2, '0') + String(inteiro(0, 59)).padStart(2, '0'), '9999'),
      DTNASC: dataBR(rnd() < 0.01 ? dtObito + inteiro(1, 300) : dtNasc),
      IDADE: '4' + String(Math.min(idade, 99)).padStart(2, '0'),
      SEXO: sexo,
      RACACOR: talvez(0.22, escolha(['1', '2', '3', '4', '5']), '9'),
      ESTCIV: talvez(0.18, escolha(['1', '2', '3', '4', '5'])),
      ESC: talvez(0.3, escolha(['1', '2', '3', '4', '5']), '9'),
      OCUP: talvez(0.25, String(inteiro(1000, 999999))),
      CODMUNRES: talvez(0.03, '292740', '29274'),
      LOCOCOR: talvez(0.06, escolha(['1', '2', '3', '4', '5']), '9'),
      CODESTAB: talvez(0.15, escolha(CNES)),
      CODMUNOCOR: '292740',
      IDADEMAE: fetal ? String(inteiro(15, 44)) : '',
      GRAVIDEZ: fetal ? escolha(['1', '1', '2']) : '',
      GESTACAO: fetal ? talvez(0.25, escolha(['3', '4', '5'])) : '',
      PARTO: fetal ? escolha(['1', '2', '9']) : '',
      OBITOPARTO: fetal ? talvez(0.3, escolha(['1', '2', '3'])) : '',
      PESO: fetal ? talvez(0.2, String(inteiro(500, 4200)), '99999') : '',
      OBITOGRAV: '', OBITOPUERP: '',
      ASSISTMED: talvez(0.1, escolha(['1', '2']), '9'),
      EXAME: escolha(['1', '2', '9']),
      CIRURGIA: escolha(['1', '2', '9']),
      NECROPSIA: escolha(['1', '2', '9']),
      LINHAA: escolha(CID),
      CAUSABAS: causa,
      CIRCOBITO: '', ACIDTRAB: '', FONTE: '',
      ATESTANTE: talvez(0.12, escolha(['1', '2', '3', '4', '5'])),
      TPPOS: investigado,
      DTINVESTIG: investigado === 'S' ? dataBR(dtObito + inteiro(10, 200)) : '',
      DTCONINV: investigado === 'S' ? talvez(0.35, dataBR(dtObito + inteiro(20, 260))) : '',
      FONTEINV: investigado === 'S' ? talvez(0.3, escolha(['1', '2', '3', '4', '5', '6'])) : '',
      DTCADASTRO: dataBR(dtObito + atraso),
      NOME: nome(),
      NOMEMAE: talvez(0.1, nome())
    };
    if (sexo === '2' && idade >= 10 && idade <= 49) {
      reg.OBITOGRAV = escolha(['1', '2', '2', '9']);
      reg.OBITOPUERP = escolha(['1', '2', '3', '9']);
    }
    if (rnd() < 0.012) { reg.SEXO = '1'; reg.OBITOGRAV = '1'; }   // incoerência proposital
    if ('VWXY'.includes(causa[0])) {
      reg.CIRCOBITO = talvez(0.3, escolha(['1', '2', '3', '4']), '9');
      reg.FONTE = talvez(0.45, escolha(['1', '2', '3', '4']));
      reg.ACIDTRAB = escolha(['1', '2', '9']);
    }
    linhas.push(reg);
  }
  for (let i = 0; i < Math.max(4, Math.round(n / 150)); i++) {   // duplicidades propositais
    linhas.push(Object.assign({}, linhas[inteiro(0, linhas.length - 1)]));
  }

  const corpo = linhas.map(l => colunas.map(c => l[c] === undefined ? '' : l[c]).join(';'));
  return '﻿' + [colunas.join(';')].concat(corpo).join('\r\n');
}
