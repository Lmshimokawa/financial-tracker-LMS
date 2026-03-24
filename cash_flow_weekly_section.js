// === FLUXO DE CAIXA (PARCELAS) ===
if (data.fluxoRealizado) {
  lines.push('');
  lines.push('\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501');
  lines.push('');
  lines.push('\ud83d\udcb5 *FLUXO DE CAIXA REALIZADO (Parcelas)*');
  lines.push(`   Total: ${fmtBRL(data.fluxoRealizado.total)} (${data.fluxoRealizado.qtd} parcelas)`);
  if (Object.keys(data.fluxoRealizado.porFormaPagamento).length > 0) {
    lines.push('');
    Object.entries(data.fluxoRealizado.porFormaPagamento)
      .sort((a, b) => b[1].total - a[1].total)
      .forEach(([fp, info]) => {
        lines.push(`   \u2022 ${fp}: ${fmtBRL(info.total)} (${info.count} parc.)`);
      });
  }
  if (Object.keys(data.fluxoRealizado.porCategoria).length > 0) {
    lines.push('');
    lines.push('   Por categoria:');
    Object.entries(data.fluxoRealizado.porCategoria)
      .sort((a, b) => b[1].total - a[1].total)
      .slice(0, 5)
      .forEach(([cat, info]) => {
        lines.push(`   \u2022 ${cat}: ${fmtBRL(info.total)}`);
      });
  }
}

if (data.fluxoComprometido && Object.keys(data.fluxoComprometido.meses).length > 0) {
  lines.push('');
  lines.push('\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501');
  lines.push('');
  lines.push('\ud83d\udcb3 *FLUXO COMPROMETIDO NO CR\u00c9DITO*');
  lines.push(`   Total 4 meses: ${fmtBRL(data.fluxoComprometido.totalGeral)}`);
  lines.push('');
  Object.entries(data.fluxoComprometido.meses).forEach(([mes, info]) => {
    lines.push(`   \ud83d\udcc5 *${mes}*: ${fmtBRL(info.total)} (${info.qtd} parc.)`);
    if (info.porCartao && Object.keys(info.porCartao).length > 0) {
      Object.entries(info.porCartao)
        .sort((a, b) => b[1].total - a[1].total)
        .forEach(([cartao, cInfo]) => {
          lines.push(`      \u2514 ${cartao}: ${fmtBRL(cInfo.total)}`);
        });
    }
  });
}
