const prop = $('Set Report Config (Monthly)').first().json.prop;
const monthReportRaw = $('Get Month Report').all();
const categoriasRaw = $('Get Categorias1').all();
const contasRaw = $('Get Contas1').all();
const month2Raw = $('Get Month M-2').all();
const month3Raw = $('Get Month M-3').all();
const month4Raw = $('Get Month M-4').all();
const formasPagamentoRaw = $('Get Formas Pagamento1').all();
const parcelasRaw = $('Get Parcelas Cash Flow1').all();

const agora = new Date();
const hojeStr = agora.toLocaleString('en-US', { timeZone: 'America/Sao_Paulo' });
const hoje = new Date(hojeStr);

const mesRelatorio = hoje.getMonth() === 0 ? 11 : hoje.getMonth() - 1;
const anoRelatorio = hoje.getMonth() === 0 ? hoje.getFullYear() - 1 : hoje.getFullYear();

const nomesMeses = ['Janeiro', 'Fevereiro', 'Marco', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
const nomesMesesCurto = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

const getMesLabel = (offset) => { let m = mesRelatorio - offset; if (m < 0) m += 12; return nomesMesesCurto[m]; };

const categoriasMap = {};
const categoriasInfo = {};
categoriasRaw.forEach(item => {
  const props = item.json?.properties || {};
  const id = item.json?.id;
  let nome = '';
  for (const [key, value] of Object.entries(props)) {
    if (value.type === 'title' && value.title?.length > 0) { nome = value.title[0]?.plain_text || ''; break; }
  }
  const orcamento = props[prop.orcamento]?.number ?? 0;
  if (id && nome) { categoriasMap[id] = nome; categoriasInfo[nome] = { orcamento }; }
});

const contasMap = {};
contasRaw.forEach(item => {
  const props = item.json?.properties || {};
  const id = item.json?.id;
  let nome = '';
  for (const [key, value] of Object.entries(props)) {
    if (value.type === 'title' && value.title?.length > 0) { nome = value.title[0]?.plain_text || ''; break; }
  }
  if (id && nome) contasMap[id] = nome;
});

const formasPagamentoMap = {};
const formasPagamentoTipo = {};
formasPagamentoRaw.forEach(item => {
  const props = item.json?.properties || {};
  const id = item.json?.id;
  let nome = '';
  for (const [key, value] of Object.entries(props)) {
    if (value.type === 'title' && value.title?.length > 0) { nome = value.title[0]?.plain_text || ''; break; }
  }
  const tipo = props['Tipo Forma de Pagamento']?.select?.name || props[prop.tipo_forma_pagamento]?.select?.name || '';
  if (id && nome) { formasPagamentoMap[id] = nome; formasPagamentoTipo[id] = tipo; }
});

const processExpenses = (raw, comDetalhes = false) => {
  return raw.map(item => {
    const p = item.json?.properties ?? {};
    const catRelation = p[prop.categoria]?.relation || [];
    const categoriaId = catRelation[0]?.id || null;
    const categoria = categoriaId ? (categoriasMap[categoriaId] || 'Sem categoria') : 'Sem categoria';
    const contaRelation = p['Conta']?.relation || [];
    const contaId = contaRelation[0]?.id || null;
    const conta = contaId ? (contasMap[contaId] || 'Sem conta') : 'Sem conta';
    const base = { data: p['Data']?.date?.start ?? null, valor: p['Valor']?.number ?? 0, categoria, conta };
    if (comDetalhes) {
      base.despesa = p[prop.title]?.title?.[0]?.text?.content ?? p[prop.title]?.title?.[0]?.plain_text ?? 'Sem titulo';
      const fpRelation = p[prop.forma_pagamento]?.relation || [];
      const fpId = fpRelation[0]?.id || null;
      base.formaPagamento = fpId ? (formasPagamentoMap[fpId] || 'Sem forma') : 'Sem forma';
    }
    return base;
  }).filter(e => e.data);
};

const expensesMesReport = processExpenses(monthReportRaw, true);
const expensesMes2 = processExpenses(month2Raw);
const expensesMes3 = processExpenses(month3Raw);
const expensesMes4 = processExpenses(month4Raw);

const totalMes = expensesMesReport.reduce((sum, e) => sum + e.valor, 0);
const qtdTransacoes = expensesMesReport.length;
const diasNoMes = new Date(anoRelatorio, mesRelatorio + 1, 0).getDate();
const mediaDiaria = qtdTransacoes > 0 ? totalMes / diasNoMes : 0;
const mediaTransacao = qtdTransacoes > 0 ? totalMes / qtdTransacoes : 0;

const totalMes2 = expensesMes2.reduce((sum, e) => sum + e.valor, 0);
const totalMes3 = expensesMes3.reduce((sum, e) => sum + e.valor, 0);
const totalMes4 = expensesMes4.reduce((sum, e) => sum + e.valor, 0);
const mediaMeses = (totalMes2 + totalMes3 + totalMes4) / 3;
const variacaoVsMesAnterior = totalMes2 > 0 ? ((totalMes - totalMes2) / totalMes2 * 100) : 0;

const porCategoria = {};
expensesMesReport.forEach(e => {
  if (!porCategoria[e.categoria]) porCategoria[e.categoria] = { total: 0, count: 0 };
  porCategoria[e.categoria].total += e.valor; porCategoria[e.categoria].count++;
});

const analiseOrcamento = [];
let totalOrcamento = 0;
Object.entries(categoriasInfo).forEach(([nome, info]) => {
  const gasto = porCategoria[nome]?.total || 0;
  const orcamento = info.orcamento;
  totalOrcamento += orcamento;
  const uso = orcamento > 0 ? (gasto / orcamento) : (gasto > 0 ? 999 : 0);
  const diferenca = orcamento - gasto;
  analiseOrcamento.push({ nome, gasto, orcamento, uso, diferenca, count: porCategoria[nome]?.count || 0 });
});
analiseOrcamento.sort((a, b) => b.uso - a.uso);

const porConta = {};
expensesMesReport.forEach(e => {
  if (!porConta[e.conta]) porConta[e.conta] = { total: 0, count: 0 };
  porConta[e.conta].total += e.valor; porConta[e.conta].count++;
});

const porPagamento = {};
expensesMesReport.forEach(e => {
  const fp = e.formaPagamento || 'Sem forma';
  if (!porPagamento[fp]) porPagamento[fp] = { total: 0, count: 0 };
  porPagamento[fp].total += e.valor; porPagamento[fp].count++;
});

const top5Despesas = [...expensesMesReport].sort((a, b) => b.valor - a.valor).slice(0, 5);

const evolucaoCategoria = {};
[expensesMesReport, expensesMes2, expensesMes3, expensesMes4].forEach((expenses, idx) => {
  expenses.forEach(e => {
    if (!evolucaoCategoria[e.categoria]) evolucaoCategoria[e.categoria] = [0, 0, 0, 0];
    evolucaoCategoria[e.categoria][idx] += e.valor;
  });
});

const mesesLabels = [getMesLabel(0), getMesLabel(1), getMesLabel(2), getMesLabel(3)];
const totaisMeses = [totalMes, totalMes2, totalMes3, totalMes4];
const usoOrcamentoTotal = totalOrcamento > 0 ? (totalMes / totalOrcamento) : 0;

// ============================================================
// FLUXO DE CAIXA (PARCELAS) - baseado em Data Vencimento
// ============================================================
function getFirstRelationId(rollupProp) {
  if (!rollupProp || rollupProp.type !== 'rollup' || !rollupProp.rollup) return null;
  const r = rollupProp.rollup;
  const arr = r.results || r.array || [];
  const first = arr[0];
  if (!first) return null;
  if (first.relation) {
    if (Array.isArray(first.relation) && first.relation[0]) return first.relation[0].id || null;
    if (typeof first.relation === 'object' && first.relation.id) return first.relation.id;
  }
  if (first.id) return first.id;
  return null;
}

function getRollupSelectName(rollupProp) {
  if (!rollupProp || rollupProp.type !== 'rollup' || !rollupProp.rollup) return null;
  const r = rollupProp.rollup;
  const arr = r.results || r.array || [];
  const first = arr[0];
  if (!first) return null;
  if (first.select?.name) return first.select.name;
  if (first.formula?.string) return first.formula.string;
  return null;
}

const fmtISO = (d) => d.toISOString().split('T')[0];
const getDiasMes = (ano, mes) => new Date(ano, mes + 1, 0).getDate();

const primeiroDiaMesReport = new Date(anoRelatorio, mesRelatorio, 1);
const ultimoDiaMesReport = new Date(anoRelatorio, mesRelatorio + 1, 0);
const diasMesReport = ultimoDiaMesReport.getDate();
const primeiroDiaMesAnterior = new Date(anoRelatorio, mesRelatorio - 1, 1);
const ultimoDiaMesAnterior = new Date(anoRelatorio, mesRelatorio, 0);
const diasMesAnterior = ultimoDiaMesAnterior.getDate();

const parcelas = parcelasRaw.map(item => {
  const p = item.json?.properties ?? {};
  const valor = p['Valor']?.number ?? 0;
  const dataVencimento = p['Data Vencimento']?.formula?.date?.start ?? null;
  if (!dataVencimento) return null;
  const fpId = getFirstRelationId(p[prop.forma_pagamento]);
  const tipoFP = getRollupSelectName(p['Tipo Forma de Pagamento']) || (fpId ? (formasPagamentoTipo[fpId] || '') : '');
  const fpNome = fpId ? (formasPagamentoMap[fpId] || 'Sem forma') : 'Sem forma';
  const contaId = getFirstRelationId(p['Conta']);
  const conta = contaId ? (contasMap[contaId] || 'Sem conta') : 'Sem conta';
  const categoriaId = getFirstRelationId(p[prop.categoria]);
  const categoria = categoriaId ? (categoriasMap[categoriaId] || 'Sem categoria') : 'Sem categoria';
  let despesa = 'Sem titulo';
  const titleProp = p[prop.title] || p['Despesa'] || p['Receita'];
  if (titleProp?.title?.length > 0) despesa = titleProp.title.map(t => t?.plain_text || '').join('').trim() || 'Sem titulo';
  return { valor, dataVencimento, formaPagamento: fpNome, tipoFP, conta, categoria, despesa };
}).filter(Boolean);

// Calcular acumulado
const calcularAcumulado = (items, diasMes) => {
  const acumulado = {};
  let acum = 0;
  items.sort((a, b) => a.dataVencimento.localeCompare(b.dataVencimento)).forEach(e => {
    const dia = parseInt(e.dataVencimento.split('-')[2]);
    acum += e.valor;
    acumulado[dia] = acum;
  });
  for (let d = 1; d <= diasMes; d++) {
    if (!acumulado[d]) acumulado[d] = d > 1 ? (acumulado[d-1] || 0) : 0;
  }
  return acumulado;
};

// --- FLUXO REALIZADO ---
const parcelasRealizadasMesReport = parcelas.filter(p => p.dataVencimento >= fmtISO(primeiroDiaMesReport) && p.dataVencimento <= fmtISO(ultimoDiaMesReport));
const parcelasRealizadasMesAnterior = parcelas.filter(p => p.dataVencimento >= fmtISO(primeiroDiaMesAnterior) && p.dataVencimento <= fmtISO(ultimoDiaMesAnterior));

const acumRealizadoReport = calcularAcumulado(parcelasRealizadasMesReport, diasMesReport);
const acumRealizadoAnterior = calcularAcumulado(parcelasRealizadasMesAnterior, diasMesAnterior);

const fluxoRealizado = {
  totalMesReport: acumRealizadoReport[diasMesReport] || 0,
  qtdMesReport: parcelasRealizadasMesReport.length,
  totalMesAnterior: acumRealizadoAnterior[diasMesAnterior] || 0,
  qtdMesAnterior: parcelasRealizadasMesAnterior.length,
  porCategoria: {},
  acumuladoReport: acumRealizadoReport,
  acumuladoAnterior: acumRealizadoAnterior,
  diasMesReport, diasMesAnterior
};
parcelasRealizadasMesReport.forEach(p => {
  const cat = p.categoria;
  if (!fluxoRealizado.porCategoria[cat]) fluxoRealizado.porCategoria[cat] = { total: 0, count: 0 };
  fluxoRealizado.porCategoria[cat].total += p.valor;
  fluxoRealizado.porCategoria[cat].count++;
});

// --- FLUXO COMPROMETIDO CREDITO ---
const parcelasCredito = parcelas.filter(p =>
  (p.tipoFP === 'Cartao Credito' || p.tipoFP === 'Cartao de Credito')
);
const fluxoComprometido = { meses: {}, chartLabels: [], chartDatasets: {} };
const cartaoSet = new Set();
for (let offset = 0; offset < 4; offset++) {
  const mesInicio = new Date(anoRelatorio, mesRelatorio + offset, 1);
  const mesFim = new Date(anoRelatorio, mesRelatorio + offset + 1, 0);
  const mesKey = nomesMesesCurto[mesInicio.getMonth()] + '/' + mesInicio.getFullYear();
  fluxoComprometido.chartLabels.push(mesKey);
  const parcelasMes = parcelasCredito.filter(p => p.dataVencimento >= fmtISO(mesInicio) && p.dataVencimento <= fmtISO(mesFim));
  const totalMesCred = parcelasMes.reduce((s, p) => s + p.valor, 0);
  const porCartao = {};
  parcelasMes.forEach(p => {
    cartaoSet.add(p.formaPagamento);
    if (!porCartao[p.formaPagamento]) porCartao[p.formaPagamento] = { total: 0, count: 0 };
    porCartao[p.formaPagamento].total += p.valor;
    porCartao[p.formaPagamento].count++;
  });
  fluxoComprometido.meses[mesKey] = { total: totalMesCred, qtd: parcelasMes.length, porCartao };
}
fluxoComprometido.totalGeral = Object.values(fluxoComprometido.meses).reduce((s, m) => s + m.total, 0);

const chartColors = ['#E53935', '#FB8C00', '#8E24AA', '#43A047', '#1E88E5', '#6D4C41'];
let colorIdx = 0;
for (const cartao of cartaoSet) {
  const data = fluxoComprometido.chartLabels.map(mesKey => {
    return fluxoComprometido.meses[mesKey]?.porCartao?.[cartao]?.total || 0;
  });
  fluxoComprometido.chartDatasets[cartao] = { data, color: chartColors[colorIdx % chartColors.length] };
  colorIdx++;
}

return [{
  json: {
    mesRelatorio: nomesMeses[mesRelatorio], anoRelatorio,
    mesRelatorioCurto: nomesMesesCurto[mesRelatorio],
    metricas: { totalMes, qtdTransacoes, diasNoMes, mediaDiaria, mediaTransacao, mediaMeses, variacaoVsMesAnterior },
    orcamento: { total: totalOrcamento, gasto: totalMes, uso: usoOrcamentoTotal, diferenca: totalOrcamento - totalMes },
    analiseOrcamento, porCategoria, porConta, porPagamento, top5Despesas,
    fluxoRealizado, fluxoComprometido,
    evolucao: { mesesLabels, totaisMeses, porCategoria: evolucaoCategoria }
  }
}];
