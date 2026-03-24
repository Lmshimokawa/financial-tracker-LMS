const prop = $('Set Report Config (Weekly)').first().json.prop;
const currentMonthRaw = $('Get Current Month Data').all();
const categoriasRaw = $('Get Categorias').all();
const contasRaw = $('Get Contas').all();
const month1Raw = $('Get Month -1').all();
const month2Raw = $('Get Month -2').all();
const month3Raw = $('Get Month -3').all();
const formasPagamentoRaw = $('Get Formas Pagamento').all();
const parcelasRaw = $('Get Parcelas Cash Flow').all();

const categoriasMap = {};
categoriasRaw.forEach(item => {
  const props = item.json?.properties || {};
  const id = item.json?.id;
  let nome = '';
  for (const [key, value] of Object.entries(props)) {
    if (value.type === 'title' && value.title?.length > 0) { nome = value.title[0]?.plain_text || ''; break; }
  }
  if (id && nome) categoriasMap[id] = nome;
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

const agora = new Date();
const hojeStr = agora.toLocaleString('en-US', { timeZone: 'America/Sao_Paulo' });
const hoje = new Date(hojeStr);
const diaDoMes = hoje.getDate();
const seteDiasAtras = new Date(hoje);
seteDiasAtras.setDate(hoje.getDate() - 7);

const nomesMeses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
const mesAtual = hoje.getMonth();
const getDiasMes = (ano, mes) => new Date(ano, mes + 1, 0).getDate();
const diasMes0 = getDiasMes(hoje.getFullYear(), mesAtual);
const diasMes1 = getDiasMes(hoje.getFullYear(), mesAtual - 1);
const diasMes2 = getDiasMes(hoje.getFullYear(), mesAtual - 2);
const diasMes3 = getDiasMes(hoje.getFullYear(), mesAtual - 3);
const maxDias = Math.max(diasMes0, diasMes1, diasMes2, diasMes3);

const processExpenses = (raw) => raw.map(item => {
  const p = item.json?.properties ?? {};
  return { data: p['Data']?.date?.start ?? null, valor: p['Valor']?.number ?? 0 };
}).filter(e => e.data);

const calcularAcumulado = (expenses, diasMes) => {
  const acumulado = {};
  let acum = 0;
  expenses.sort((a, b) => a.data.localeCompare(b.data)).forEach(e => {
    const dia = parseInt(e.data.split('-')[2]);
    acum += e.valor;
    acumulado[dia] = acum;
  });
  for (let d = 1; d <= diasMes; d++) {
    if (!acumulado[d]) acumulado[d] = d > 1 ? (acumulado[d-1] || 0) : 0;
  }
  return acumulado;
};

const expensesCurrentMonth = currentMonthRaw.map(item => {
  const p = item.json?.properties ?? {};
  const catRel = p[prop.categoria]?.relation || [];
  const categoriaId = catRel[0]?.id || null;
  const categoria = categoriaId ? (categoriasMap[categoriaId] || 'Sem categoria') : 'Sem categoria';
  const contaRel = p['Conta']?.relation || [];
  const contaId = contaRel[0]?.id || null;
  const conta = contaId ? (contasMap[contaId] || 'Sem conta') : 'Sem conta';
  const fpRel = p[prop.forma_pagamento]?.relation || [];
  const fpId = fpRel[0]?.id || null;
  const formaPagamento = fpId ? (formasPagamentoMap[fpId] || 'Sem forma') : 'Sem forma';
  return {
    id: p['ID_transacao']?.unique_id?.number ?? 'N/A',
    despesa: p[prop.title]?.title?.[0]?.text?.content ?? p[prop.title]?.title?.[0]?.plain_text ?? 'Sem titulo',
    data: p['Data']?.date?.start ?? null,
    valor: p['Valor']?.number ?? 0,
    categoria, conta, formaPagamento
  };
}).filter(e => e.data);

const expensesSemana = expensesCurrentMonth.filter(e => {
  const dataExp = new Date(e.data + 'T12:00:00');
  return dataExp >= seteDiasAtras && dataExp <= hoje;
});

const acumMes0 = calcularAcumulado(expensesCurrentMonth.map(e => ({ data: e.data, valor: e.valor })), diasMes0);
const acumMes1 = calcularAcumulado(processExpenses(month1Raw), diasMes1);
const acumMes2 = calcularAcumulado(processExpenses(month2Raw), diasMes2);
const acumMes3 = calcularAcumulado(processExpenses(month3Raw), diasMes3);

const totalMes0 = acumMes0[diaDoMes] || 0;
const totalMes1AteDia = acumMes1[diaDoMes] || 0;
const totalMes1Completo = acumMes1[diasMes1] || 0;

const totalSemana = expensesSemana.reduce((sum, e) => sum + e.valor, 0);
const qtdSemana = expensesSemana.length;

const porConta = {};
expensesSemana.forEach(e => {
  if (!porConta[e.conta]) porConta[e.conta] = { total: 0, count: 0 };
  porConta[e.conta].total += e.valor; porConta[e.conta].count++;
});

const porCategoria = {};
expensesSemana.forEach(e => {
  if (!porCategoria[e.categoria]) porCategoria[e.categoria] = { total: 0, count: 0 };
  porCategoria[e.categoria].total += e.valor; porCategoria[e.categoria].count++;
});

const porPagamento = {};
expensesSemana.forEach(e => {
  if (!porPagamento[e.formaPagamento]) porPagamento[e.formaPagamento] = { total: 0, count: 0 };
  porPagamento[e.formaPagamento].total += e.valor; porPagamento[e.formaPagamento].count++;
});

const categoryBudget = {};
let totalOrcamento = 0;
let totalDespesasMes = 0;
categoriasRaw.forEach(item => {
  const props = item.json?.properties || {};
  let nome = '';
  for (const [key, value] of Object.entries(props)) {
    if (value.type === 'title' && value.title?.length > 0) { nome = value.title[0]?.plain_text || ''; break; }
  }
  if (!nome) nome = 'Sem nome';
  const despesasEsteMes = props[prop.este_mes]?.rollup?.number ?? 0;
  const orcamentoMensal = props[prop.orcamento]?.number ?? 0;
  const usoPercent = props[prop.uso]?.formula?.number ?? 0;
  categoryBudget[nome] = { despesasEsteMes, orcamentoMensal, usoPercent };
  totalDespesasMes += despesasEsteMes;
  totalOrcamento += orcamentoMensal;
});

const fmtDate = (d) => `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}`;
const periodoLabel = `${fmtDate(seteDiasAtras)} a ${fmtDate(hoje)}`;

const diasLabels = [];
const valoresMes0 = [], valoresMes1 = [], valoresMes2 = [], valoresMes3 = [];
for (let d = 1; d <= maxDias; d++) {
  diasLabels.push(d.toString());
  valoresMes0.push(d <= diaDoMes ? (acumMes0[d] || 0) : null);
  valoresMes1.push(d <= diasMes1 ? (acumMes1[d] || 0) : null);
  valoresMes2.push(d <= diasMes2 ? (acumMes2[d] || 0) : null);
  valoresMes3.push(d <= diasMes3 ? (acumMes3[d] || 0) : null);
}

const getMesLabel = (offset) => { let m = mesAtual - offset; if (m < 0) m += 12; return nomesMeses[m]; };

// === FLUXO DE CAIXA (PARCELAS) ===
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

const primeiroDiaMes = new Date(hoje.getFullYear(), hoje.getMonth(), 1);
const fim3Meses = new Date(hoje.getFullYear(), hoje.getMonth() + 4, 0);
const fmtISO = (d) => d.toISOString().split('T')[0];

const parcelas = parcelasRaw.map(item => {
  const p = item.json?.properties ?? {};
  const valor = p['Valor']?.number ?? 0;
  const dataCobranca = p['Data Cobranca']?.date?.start ?? null;
  if (!dataCobranca) return null;
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
  return { valor, data: dataCobranca, formaPagamento: fpNome, tipoFP, conta, categoria, despesa };
}).filter(Boolean);

const parcelasRealizadas = parcelas.filter(p => p.data >= fmtISO(primeiroDiaMes) && p.data <= fmtISO(hoje));
const fluxoRealizado = {
  total: parcelasRealizadas.reduce((s, p) => s + p.valor, 0),
  qtd: parcelasRealizadas.length,
  porFormaPagamento: {},
  porCategoria: {}
};
parcelasRealizadas.forEach(p => {
  const fp = p.formaPagamento;
  if (!fluxoRealizado.porFormaPagamento[fp]) fluxoRealizado.porFormaPagamento[fp] = { total: 0, count: 0 };
  fluxoRealizado.porFormaPagamento[fp].total += p.valor; fluxoRealizado.porFormaPagamento[fp].count++;
  const cat = p.categoria;
  if (!fluxoRealizado.porCategoria[cat]) fluxoRealizado.porCategoria[cat] = { total: 0, count: 0 };
  fluxoRealizado.porCategoria[cat].total += p.valor; fluxoRealizado.porCategoria[cat].count++;
});

const parcelasCredito = parcelas.filter(p =>
  (p.tipoFP === 'Cartao Credito' || p.tipoFP === 'Cartao de Credito') &&
  p.data >= fmtISO(primeiroDiaMes) && p.data <= fmtISO(fim3Meses)
);
const fluxoComprometido = { meses: {} };
for (let offset = 0; offset < 4; offset++) {
  const mesInicio = new Date(hoje.getFullYear(), hoje.getMonth() + offset, 1);
  const mesFim = new Date(hoje.getFullYear(), hoje.getMonth() + offset + 1, 0);
  const mesKey = nomesMeses[mesInicio.getMonth()] + '/' + mesInicio.getFullYear();
  const parcelasMes = parcelasCredito.filter(p => p.data >= fmtISO(mesInicio) && p.data <= fmtISO(mesFim));
  const totalMesCred = parcelasMes.reduce((s, p) => s + p.valor, 0);
  const porCartao = {};
  parcelasMes.forEach(p => {
    if (!porCartao[p.formaPagamento]) porCartao[p.formaPagamento] = { total: 0, count: 0 };
    porCartao[p.formaPagamento].total += p.valor; porCartao[p.formaPagamento].count++;
  });
  fluxoComprometido.meses[mesKey] = { total: totalMesCred, qtd: parcelasMes.length, porCartao };
}
fluxoComprometido.totalGeral = Object.values(fluxoComprometido.meses).reduce((s, m) => s + m.total, 0);

return [{
  json: {
    periodo: periodoLabel, diaDoMes, maxDias,
    mesesLabels: { mes0: getMesLabel(0), mes1: getMesLabel(1), mes2: getMesLabel(2), mes3: getMesLabel(3) },
    totais: { semana: totalSemana, qtdSemana, mesAtual: totalMes0, mesAnteriorAteDia: totalMes1AteDia, mesAnteriorCompleto: totalMes1Completo },
    por_conta: porConta, por_categoria: porCategoria, por_pagamento: porPagamento,
    categoryBudget, totalOrcamento, totalDespesasMes,
    fluxoRealizado, fluxoComprometido,
    grafico: { labels: diasLabels, mes0: valoresMes0, mes1: valoresMes1, mes2: valoresMes2, mes3: valoresMes3 }
  }
}];
