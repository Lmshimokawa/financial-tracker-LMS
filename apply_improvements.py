#!/usr/bin/env python3
"""
Apply all 3 improvements to the Financial Tracker workflow:
1. Smart Document Parsing (replace "Unify content" code)
2. Telegram Message Batching (add batcher nodes before key Telegram sends)
3. Idempotency / Duplicate Detection (add check before create, modify response)
"""
import json
import copy
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

WORKFLOW_FILE = r'C:\Users\leand\financial-tracker-LMS\workflow_v3_backup.json'
OUTPUT_FILE = r'C:\Users\leand\financial-tracker-LMS\workflow_v3_improved.json'

with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
    workflow = json.load(f)

nodes = workflow['nodes']
connections = workflow['connections']

def find_node(name):
    for n in nodes:
        if n['name'] == name:
            return n
    return None

def get_pos(name):
    n = find_node(name)
    if n:
        return list(n.get('position', [0, 0]))
    return [0, 0]

def add_node(node_def):
    nodes.append(node_def)

def rewire_connection(source_name, old_target_name, new_target_name, output_index=0):
    if source_name not in connections:
        return False
    main_outputs = connections[source_name].get('main', [])
    if output_index >= len(main_outputs):
        return False
    output_list = main_outputs[output_index]
    for conn in output_list:
        if conn['node'] == old_target_name:
            conn['node'] = new_target_name
            return True
    return False

def add_connection(source_name, target_name, source_output=0, target_input=0):
    if source_name not in connections:
        connections[source_name] = {'main': []}
    main = connections[source_name]['main']
    while len(main) <= source_output:
        main.append([])
    main[source_output].append({
        'node': target_name,
        'type': 'main',
        'index': target_input
    })

# ============================================================
# IMPROVEMENT 1: Smart Document Parsing
# ============================================================
print("=== Applying Improvement 1: Smart Document Parsing ===")

SMART_PARSE_CODE = """// ============================================================
// SMART PARSE & NORMALIZE - Financial Document Parser
// ============================================================

const items = $input.all();
const MAX_TRANSACTIONS = 150;
const MAX_CONTENT_LENGTH = 12000;

function norm(s) {
  if (typeof s !== 'string') return '';
  return s.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').replace(/[^a-z0-9]/g, '').trim();
}

function parseAmount(raw) {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === 'number') return raw;
  let s = String(raw).trim();
  if (!s) return null;
  const isParenNeg = /^\\(.*\\)$/.test(s);
  if (isParenNeg) s = s.replace(/[()]/g, '');
  const hasNegSign = /^-/.test(s);
  s = s.replace(/[R$\\s]/g, '').replace(/[a-zA-Z\\u00e1\\u00e9\\u00ed\\u00f3\\u00fa\\u00e3\\u00f5\\u00e7]/gi, '');
  const lastComma = s.lastIndexOf(',');
  const lastDot = s.lastIndexOf('.');
  let cleaned;
  if (lastComma > lastDot) { cleaned = s.replace(/\\./g, '').replace(',', '.'); }
  else if (lastDot > lastComma) { cleaned = s.replace(/,/g, ''); }
  else if (lastComma >= 0 && lastDot < 0) { cleaned = s.replace(',', '.'); }
  else { cleaned = s.replace(/,/g, ''); }
  cleaned = cleaned.replace(/[^0-9.\\-]/g, '');
  const val = parseFloat(cleaned);
  if (isNaN(val)) return null;
  return (isParenNeg || hasNegSign) ? -Math.abs(val) : val;
}

function parseDate(raw) {
  if (!raw) return null;
  let s = String(raw).trim();
  if (/^\\d{4}-\\d{2}-\\d{2}/.test(s)) return s.substring(0, 10);
  const brMonths = {jan:'01',fev:'02',mar:'03',abr:'04',mai:'05',jun:'06',jul:'07',ago:'08',set:'09',out:'10',nov:'11',dez:'12'};
  const mBr = s.match(/(\\d{1,2})\\s+(?:de\\s+)?([a-z\\u00e7]+)\\.?\\s+(?:de\\s+)?(\\d{2,4})/i);
  if (mBr) {
    const day = parseInt(mBr[1], 10);
    const monthStr = mBr[2].toLowerCase().substring(0, 3);
    const month = brMonths[monthStr];
    let year = parseInt(mBr[3], 10);
    if (year < 100) year += 2000;
    if (month && day >= 1 && day <= 31) return `${year}-${month}-${String(day).padStart(2, '0')}`;
  }
  let m = s.match(/^(\\d{1,2})[\\/\\-\\.](\\d{1,2})[\\/\\-\\.](\\d{2,4})$/);
  if (m) {
    let day = parseInt(m[1], 10), month = parseInt(m[2], 10), year = parseInt(m[3], 10);
    if (year < 100) year += 2000;
    if (month > 12 && day <= 12) { [day, month] = [month, day]; }
    if (day >= 1 && day <= 31 && month >= 1 && month <= 12) return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  }
  const d = new Date(s);
  if (!isNaN(d.getTime())) return d.toISOString().substring(0, 10);
  return null;
}

function formatBRL(amount) {
  if (amount === null || amount === undefined) return 'N/A';
  const abs = Math.abs(amount);
  const formatted = abs.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return (amount < 0 ? '-' : '') + 'R$ ' + formatted;
}

function formatDateBR(isoDate) {
  if (!isoDate) return 'N/A';
  const [y, m, d] = isoDate.split('-');
  return `${d}/${m}/${y}`;
}

const COLUMN_PATTERNS = {
  date: ['data','date','dt','data_mov','data_movimentacao','data_lancamento','data_transacao','data_compra','data_pagamento','transaction_date','posting_date','vencimento','data_vencimento'],
  description: ['descricao','description','desc','titulo','title','historico','lancamento','estabelecimento','merchant','nome','name','memo','detail','detalhe','detalhes','observacao','obs','transaction'],
  amount: ['valor','amount','value','vlr','montante','total','valortransacao','price','preco'],
  debit: ['debito','debit','saida','saidas','deb','despesa'],
  credit: ['credito','credit','entrada','entradas','cred','receita'],
  category: ['categoria','category','cat','tipo','type','classificacao','grupo','group']
};

function matchColumn(header) {
  const normalized = norm(header);
  if (!normalized) return null;
  for (const [field, patterns] of Object.entries(COLUMN_PATTERNS)) {
    for (const pattern of patterns) {
      if (normalized === pattern || normalized.includes(pattern) || pattern.includes(normalized)) return field;
    }
  }
  return null;
}

function detectColumns(headers) {
  const mapping = {};
  for (const header of headers) {
    const field = matchColumn(header);
    if (field && !mapping[field]) mapping[field] = header;
  }
  return mapping;
}

function extractTransaction(row, mapping) {
  const tx = { date: null, description: null, amount: null, category: null };
  if (mapping.date && row[mapping.date] !== undefined) tx.date = parseDate(row[mapping.date]);
  if (mapping.description && row[mapping.description] !== undefined) tx.description = String(row[mapping.description]).trim();
  if (mapping.amount && row[mapping.amount] !== undefined) {
    tx.amount = parseAmount(row[mapping.amount]);
  } else {
    const debit = mapping.debit ? parseAmount(row[mapping.debit]) : null;
    const credit = mapping.credit ? parseAmount(row[mapping.credit]) : null;
    if (debit !== null && debit !== 0) tx.amount = -Math.abs(debit);
    else if (credit !== null && credit !== 0) tx.amount = Math.abs(credit);
  }
  if (mapping.category && row[mapping.category] !== undefined) tx.category = String(row[mapping.category]).trim();
  return tx;
}

function extractFromPDF(text) {
  const lines = text.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
  const transactions = [];
  let currentDate = null;
  const dateHeaderPattern = /^(\\d{1,2})\\s+(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)\\s+(\\d{4})$/i;
  const amountLinePattern = /^(.+?)\\s{2,}(-?\\s*\\d[\\d.,]*\\d?)\\s*$/;
  const brMonths2 = {jan:'01',fev:'02',mar:'03',abr:'04',mai:'05',jun:'06',jul:'07',ago:'08',set:'09',out:'10',nov:'11',dez:'12'};

  for (const line of lines) {
    const dateMatch = line.match(dateHeaderPattern);
    if (dateMatch) {
      const day = dateMatch[1].padStart(2, '0');
      const month = brMonths2[dateMatch[2].toLowerCase()];
      const year = dateMatch[3];
      if (month) currentDate = `${year}-${month}-${day}`;
      continue;
    }
    const lower = line.toLowerCase();
    if (lower.startsWith('total de entradas') || lower.startsWith('total de sa') || lower.includes('saldo') || lower.includes('rendimento')) continue;
    if (lower.includes('tem alguma d') || lower.includes('extrato gerado') || lower.includes('ouvidoria') || lower.includes('atendimento')) continue;
    if (lower.includes('valores em r$') || lower.includes('movimenta')) continue;
    if (/^\\d{1,2}\\s+de\\s+\\w+\\s+de\\s+\\d{4}\\s+a\\s+/i.test(line)) continue;
    if (/^(CPF|Ag[e\\u00ea]ncia|Conta)\\b/i.test(line)) continue;
    if (/^[\\d\\s.\\-\\/]+$/.test(line) && line.length < 15) continue;
    if (/^(Nu Financeira|Nu Pagamentos|CNPJ)/.test(line)) continue;
    if (/^\\w+\\s+\\w+\\s+Shimokawa/.test(line)) continue;

    const amountMatch = line.match(amountLinePattern);
    if (amountMatch && currentDate) {
      let desc = amountMatch[1].trim();
      const amountStr = amountMatch[2].trim();
      if (desc.length < 3) continue;
      const amount = parseAmount(amountStr);
      if (amount !== null && desc.length > 1) {
        transactions.push({ date: currentDate, description: desc.replace(/\\s+/g, ' '), amount: amount, category: null });
      }
    }
  }

  if (transactions.length === 0) {
    const lineRegex = /^(\\d{1,2}\\/\\d{1,2}(?:\\/\\d{2,4})?)\\s+(?:(\\d{1,2}\\/\\d{1,2}(?:\\/\\d{2,4})?)\\s+)?(.+?)\\s+(-?\\s*R?\\$?\\s*[\\d]+[.,\\d]*[\\d])\\s*$/;
    const relaxedRegex = /(\\d{1,2}\\/\\d{1,2}(?:\\/\\d{2,4})?)\\s+(.+?)\\s{2,}(-?\\s*R?\\$?\\s*[\\d]+[.,\\d]*[\\d])/;
    for (const line of lines) {
      let match = line.match(lineRegex);
      if (!match) { match = line.match(relaxedRegex); if (match) match = [match[0], match[1], null, match[2], match[3]]; }
      if (match) {
        const desc = (match[3] || '').trim();
        if (desc.toLowerCase().includes('saldo') || desc === 'total') continue;
        const date = parseDate(match[1]);
        const amount = parseAmount(match[4]);
        if (desc && desc.length > 1) transactions.push({ date, description: desc.replace(/\\s+/g, ' '), amount, category: null });
      }
    }
  }
  return transactions;
}

function detectDocumentType(transactions, rawContent) {
  const c = (rawContent || '').toLowerCase();
  if (c.includes('fatura') || c.includes('cart\\u00e3o') || c.includes('cartao')) return 'fatura_cartao';
  if (c.includes('extrato') || c.includes('movimenta')) return 'extrato_bancario';
  if (c.includes('nota fiscal') || c.includes('nf-e')) return 'nota_fiscal';
  if (c.includes('recibo')) return 'recibo';
  return 'documento_financeiro';
}

const DOC_TYPE_LABELS = { fatura_cartao: 'Fatura de Cart\\u00e3o de Cr\\u00e9dito', extrato_bancario: 'Extrato Banc\\u00e1rio', nota_fiscal: 'Nota Fiscal', recibo: 'Recibo', documento_financeiro: 'Documento Financeiro' };

function processTabularData(items) {
  const rows = items.map(item => item.json.row || item.json);
  if (rows.length === 0) return { transactions: [], rawContent: '', headers: [] };
  const headers = Object.keys(rows[0]);
  const mapping = detectColumns(headers);
  const transactions = [];
  for (const row of rows) {
    const tx = extractTransaction(row, mapping);
    if (!tx.description && tx.amount === null) continue;
    if (tx.description && /^(data|date|descri|valor|amount|total)/i.test(tx.description)) continue;
    transactions.push(tx);
  }
  return { transactions, rawContent: JSON.stringify(rows.slice(0, 3), null, 2), headers, mapping };
}

function processPDFData(items) {
  let rawText = '';
  if (items.length === 1) { const j = items[0].json; rawText = j.content || j.text || JSON.stringify(j); }
  else { rawText = items.map(i => i.json.content || i.json.text || JSON.stringify(i.json)).join('\\n'); }
  const transactions = extractFromPDF(rawText);
  return { transactions, rawContent: rawText };
}

function formatOutput(transactions, rawContent, fileName, fileType) {
  const docType = detectDocumentType(transactions, rawContent);
  const docTypeLabel = DOC_TYPE_LABELS[docType] || docType;
  if (transactions.length === 0) {
    const truncated = rawContent.length > MAX_CONTENT_LENGTH ? rawContent.substring(0, MAX_CONTENT_LENGTH) + '\\n[... truncado ...]' : rawContent;
    return { content: `DOCUMENTO RECEBIDO (parsing automatico nao encontrou transacoes estruturadas)\\nTipo detectado: ${docTypeLabel}\\nArquivo: ${fileName || 'N/A'}\\n\\n--- CONTEUDO BRUTO ---\\n${truncated}\\n\\nINSTRUCOES: Analise o conteudo acima e extraia as transacoes financeiras manualmente.` };
  }
  let totalIn = 0, totalOut = 0, minDate = null, maxDate = null;
  for (const tx of transactions) {
    if (tx.amount !== null) { if (tx.amount >= 0) totalIn += tx.amount; else totalOut += tx.amount; }
    if (tx.date) { if (!minDate || tx.date < minDate) minDate = tx.date; if (!maxDate || tx.date > maxDate) maxDate = tx.date; }
  }
  const displayTxs = transactions.slice(0, MAX_TRANSACTIONS);
  const wasChunked = transactions.length > MAX_TRANSACTIONS;
  let output = `DOCUMENTO FINANCEIRO PROCESSADO\\nTipo: ${docTypeLabel}\\nArquivo: ${fileName || 'N/A'}\\nTransacoes encontradas: ${transactions.length}\\n`;
  if (minDate && maxDate) output += `Periodo: ${formatDateBR(minDate)} a ${formatDateBR(maxDate)}\\n`;
  output += `\\n--- TRANSACOES ---\\n`;
  for (let i = 0; i < displayTxs.length; i++) {
    const tx = displayTxs[i];
    output += `${i + 1}. ${tx.date ? formatDateBR(tx.date) : '??/??/????'} | ${tx.description || '(sem descricao)'} | ${tx.amount !== null ? formatBRL(tx.amount) : '?'}${tx.category ? ' [' + tx.category + ']' : ''}\\n`;
  }
  if (wasChunked) output += `\\n[... mostrando ${MAX_TRANSACTIONS} de ${transactions.length} transacoes.]\\n`;
  output += `\\n--- RESUMO ---\\n`;
  if (totalIn > 0) output += `Total entradas: ${formatBRL(totalIn)}\\n`;
  if (totalOut < 0) output += `Total saidas: ${formatBRL(totalOut)}\\n`;
  output += `Saldo liquido: ${formatBRL(totalIn + totalOut)}\\n`;
  if (output.length > MAX_CONTENT_LENGTH) output = output.substring(0, MAX_CONTENT_LENGTH) + '\\n[... truncado ...]';
  return { content: output };
}

try {
  if (items.length === 0) return [{ json: { content: '(Nenhum conteudo extraido do documento.)' } }];
  const firstJson = items[0].json;
  const isPDF = (typeof firstJson.content === 'string' || typeof firstJson.text === 'string') && !firstJson.row && items.length <= 2;
  const isTabular = firstJson.row || (items.length > 1 && typeof firstJson === 'object' && !firstJson.content);
  const fileName = items[0].json.fileName || items[0].json.file_name || '';
  let result;
  if (isTabular || (!isPDF && items.length > 2)) {
    const { transactions, rawContent, headers, mapping } = processTabularData(items);
    result = formatOutput(transactions, rawContent, fileName, 'tabular');
    if (mapping && Object.keys(mapping).length > 0) {
      result.content += `\\n\\n--- MAPEAMENTO DE COLUNAS ---\\n`;
      for (const [field, col] of Object.entries(mapping)) result.content += `${field} -> "${col}"\\n`;
    }
  } else if (isPDF) {
    const { transactions, rawContent } = processPDFData(items);
    result = formatOutput(transactions, rawContent, fileName, 'pdf');
  } else {
    try {
      const { transactions, rawContent } = processTabularData(items);
      if (transactions.length > 0) { result = formatOutput(transactions, rawContent, fileName, 'tabular'); }
      else {
        const pdfResult = processPDFData(items);
        result = pdfResult.transactions.length > 0 ? formatOutput(pdfResult.transactions, pdfResult.rawContent, fileName, 'pdf') : formatOutput([], items.length === 1 ? (items[0].json.content || JSON.stringify(items[0].json, null, 2)) : JSON.stringify(items.map(i => i.json), null, 2), fileName, 'unknown');
      }
    } catch (e) { result = formatOutput([], JSON.stringify(items.map(i => i.json), null, 2), fileName, 'unknown'); }
  }
  return [{ json: result }];
} catch (error) {
  let fallback = '';
  try { fallback = items.length === 1 ? (items[0].json.content || JSON.stringify(items[0].json, null, 2)) : JSON.stringify(items.map(i => i.json), null, 2); } catch (_) { fallback = '(Erro)'; }
  if (fallback.length > MAX_CONTENT_LENGTH) fallback = fallback.substring(0, MAX_CONTENT_LENGTH);
  return [{ json: { content: `ERRO NO PARSING: ${error.message}\\n\\n${fallback}` } }];
}"""

unify_node = find_node('Unify content')
if unify_node:
    unify_node['name'] = 'Smart Parse & Normalize'
    unify_node['parameters']['jsCode'] = SMART_PARSE_CODE
    if 'Unify content' in connections:
        connections['Smart Parse & Normalize'] = connections.pop('Unify content')
    for src_name in list(connections.keys()):
        for output_type in connections[src_name]:
            for output_list in connections[src_name][output_type]:
                for conn in output_list:
                    if conn['node'] == 'Unify content':
                        conn['node'] = 'Smart Parse & Normalize'
    print("  OK: Replaced 'Unify content' with 'Smart Parse & Normalize'")
else:
    print("  WARN: 'Unify content' not found")


# ============================================================
# IMPROVEMENT 2: Telegram Message Batching
# ============================================================
print("\n=== Applying Improvement 2: Telegram Message Batching ===")

BATCHER_CODE = """// Telegram Message Batcher - splits messages exceeding 4096 char Telegram limit
const MAX_CHUNK_SIZE = 4000;
const SECTION_SEPARATORS = ['\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501', '\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501', '\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501', '\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500\\u2500'];

function getUnclosedTags(text) {
  const openTags = [];
  const tagRegex = /<\\/?([a-zA-Z][a-zA-Z0-9]*)\\b[^>]*>/g;
  let match;
  while ((match = tagRegex.exec(text)) !== null) {
    const fullMatch = match[0]; const tagName = match[1].toLowerCase();
    if (fullMatch.endsWith('/>') || ['br','hr','img','input'].includes(tagName)) continue;
    if (fullMatch.startsWith('</')) { const idx = openTags.lastIndexOf(tagName); if (idx !== -1) openTags.splice(idx, 1); }
    else openTags.push(tagName);
  }
  return openTags;
}

function buildClosingTags(tags) { return tags.slice().reverse().map(t => `</${t}>`).join(''); }
function buildReopeningTags(tags) { return tags.filter(t => t !== 'a').map(t => `<${t}>`).join(''); }

function findSplitPoint(text, maxPos) {
  const zone = text.substring(0, maxPos);
  for (const sep of SECTION_SEPARATORS) { const idx = zone.lastIndexOf(sep); if (idx > 0) { const ls = zone.lastIndexOf('\\n', idx - 1); return ls > 0 ? ls : idx; } }
  const dn = zone.lastIndexOf('\\n\\n'); if (dn > 0) return dn;
  const sn = zone.lastIndexOf('\\n'); if (sn > 0) return sn;
  const sp = zone.lastIndexOf(' '); if (sp > 0) return sp;
  return maxPos;
}

function batchMessage(message) {
  if (!message || message.length <= MAX_CHUNK_SIZE) return [message || ''];
  const chunks = []; let remaining = message;
  while (remaining.length > 0) {
    if (remaining.length <= MAX_CHUNK_SIZE) { chunks.push(remaining); break; }
    const unclosed = getUnclosedTags(remaining.substring(0, MAX_CHUNK_SIZE));
    const closingLen = buildClosingTags(unclosed).length;
    const effectiveMax = MAX_CHUNK_SIZE - closingLen - 20;
    const splitAt = findSplitPoint(remaining, effectiveMax);
    let chunk = remaining.substring(0, splitAt);
    const openTags = getUnclosedTags(chunk);
    if (openTags.length > 0) chunk += buildClosingTags(openTags);
    chunks.push(chunk);
    let nextStart = splitAt;
    while (nextStart < remaining.length && (remaining[nextStart] === '\\n' || remaining[nextStart] === '\\r')) nextStart++;
    let nextPrefix = openTags.length > 0 ? buildReopeningTags(openTags) : '';
    remaining = nextPrefix + remaining.substring(nextStart);
  }
  if (chunks.length > 1) { const total = chunks.length; for (let i = 0; i < chunks.length; i++) chunks[i] = chunks[i].trimEnd() + `\\n\\n<i>(${i+1}/${total})</i>`; }
  return chunks;
}

const results = [];
for (const item of $input.all()) {
  const message = item.json.text || item.json.message || '';
  const chatId = item.json.chatId || item.json.chat_id || '';
  const chunks = batchMessage(message);
  for (const chunk of chunks) {
    results.push({ json: { text: chunk, chatId: chatId, ...(item.json.has_duplicates !== undefined && { has_duplicates: item.json.has_duplicates }) } });
  }
}
return results;"""

batching_targets = [
    {
        'batcher_name': 'Batch - Query Result',
        'telegram_node': 'Reply user - query result',
        'source_nodes': ['Formata Resposta para Telegram', 'Format Parcelas Response'],
        'position_offset': [-300, 0]
    },
    {
        'batcher_name': 'Batch - Weekly Summary',
        'telegram_node': 'Send Weekly Summary',
        'source_nodes': ['Format Weekly Summary'],
        'position_offset': [-300, 0]
    },
    {
        'batcher_name': 'Batch - Monthly Summary',
        'telegram_node': 'Send Monthly Summary',
        'source_nodes': ['Format Monthly Summary'],
        'position_offset': [-300, 0]
    },
    {
        'batcher_name': 'Batch - New Expense',
        'telegram_node': 'Reply user - new expense',
        'source_nodes': ['Format Enhanced Response'],
        'position_offset': [-300, 0]
    }
]

for target in batching_targets:
    telegram_node = find_node(target['telegram_node'])
    if not telegram_node:
        print(f"  WARN: '{target['telegram_node']}' not found, skipping")
        continue

    tg_pos = telegram_node.get('position', [0, 0])

    batcher_node = {
        'parameters': {
            'jsCode': BATCHER_CODE,
            'mode': 'runOnceForAllItems'
        },
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [tg_pos[0] + target['position_offset'][0], tg_pos[1] + target['position_offset'][1]],
        'id': None,
        'name': target['batcher_name']
    }
    add_node(batcher_node)

    for src in target['source_nodes']:
        if src in connections:
            main_outputs = connections[src].get('main', [])
            for output_list in main_outputs:
                for conn in output_list:
                    if conn['node'] == target['telegram_node']:
                        conn['node'] = target['batcher_name']

    add_connection(target['batcher_name'], target['telegram_node'])

    # Update Telegram node text field if it references old source directly
    if 'text' in telegram_node.get('parameters', {}):
        current_text = telegram_node['parameters']['text']
        if '$(' in current_text and any(s in current_text for s in target['source_nodes']):
            telegram_node['parameters']['text'] = '={{ $json.text }}'

    print(f"  OK: Added '{target['batcher_name']}' before '{target['telegram_node']}'")


# ============================================================
# IMPROVEMENT 3: Idempotency / Duplicate Detection
# ============================================================
print("\n=== Applying Improvement 3: Idempotency (Duplicate Detection) ===")

split_pos = get_pos('Split Expenses for Creation')
build_payload_pos = get_pos('Build Notion API Payload')
mid_x = (split_pos[0] + build_payload_pos[0]) // 2
mid_y = split_pos[1]

BUILD_DUP_QUERY_CODE = """// Build Duplicate Check Query - prepares Notion API query for each expense
const tenantConfig = $('Resolve Tenant Config').first().json;
const databaseId = tenantConfig.database_id_transacoes;

return items.map(item => {
  const expense = item.json.expense;
  if (!expense || !expense.Valor) {
    return { json: { ...item.json, _skip_duplicate_check: true, duplicates: [], has_duplicates: false } };
  }
  const valor = expense.Valor;
  const dataStr = expense.Data || new Date().toISOString().split('T')[0];
  const baseDate = new Date(dataStr + 'T12:00:00Z');
  const startDate = new Date(baseDate); startDate.setDate(startDate.getDate() - 3);
  const endDate = new Date(baseDate); endDate.setDate(endDate.getDate() + 3);
  const filter = {
    and: [
      { property: 'Valor', number: { equals: valor } },
      { property: 'Data', date: { on_or_after: startDate.toISOString().split('T')[0] } },
      { property: 'Data', date: { on_or_before: endDate.toISOString().split('T')[0] } }
    ]
  };
  return { json: { ...item.json, _duplicate_query: { url: `https://api.notion.com/v1/databases/${databaseId}/query`, body: { filter, page_size: 5 } }, _skip_duplicate_check: false } };
});"""

add_node({
    'parameters': { 'jsCode': BUILD_DUP_QUERY_CODE, 'mode': 'runOnceForAllItems' },
    'type': 'n8n-nodes-base.code',
    'typeVersion': 2,
    'position': [mid_x - 200, mid_y],
    'id': None,
    'name': 'Build Duplicate Check Query'
})

add_node({
    'parameters': {
        'method': 'POST',
        'url': '={{ $json._duplicate_query?.url || "" }}',
        'authentication': 'predefinedCredentialType',
        'nodeCredentialType': 'notionApi',
        'sendHeaders': True,
        'headerParameters': { 'parameters': [{ 'name': 'Notion-Version', 'value': '2022-06-28' }] },
        'sendBody': True,
        'specifyBody': 'json',
        'jsonBody': '={{ JSON.stringify($json._duplicate_query?.body || {}) }}',
        'options': { 'response': { 'response': { 'neverError': True } } }
    },
    'type': 'n8n-nodes-base.httpRequest',
    'typeVersion': 4.2,
    'position': [mid_x, mid_y],
    'id': None,
    'name': 'HTTP Request - Check Duplicates'
})

PROCESS_DUP_CODE = """// Process Duplicate Results - parses Notion query and attaches duplicate info
const prop = $('Resolve Tenant Config').first().json.prop;
const queryItems = $('Build Duplicate Check Query').all();

return items.map((item, index) => {
  const json = item.json;
  const originalData = queryItems[index]?.json || {};
  if (originalData._skip_duplicate_check) {
    return { json: { ...originalData, duplicates: [], has_duplicates: false } };
  }
  const existingPages = json.results || [];
  const duplicates = existingPages.map(page => {
    const ps = page.properties || {};
    const titleProp = ps[prop.title]?.title || [];
    const existingTitle = titleProp[0]?.plain_text || titleProp[0]?.text?.content || '';
    const existingValor = ps['Valor']?.number ?? 0;
    const existingData = ps['Data']?.date?.start || '';
    const existingId = ps['ID_transacao']?.unique_id?.number || 'N/A';
    return { page_id: page.id, titulo: existingTitle, valor: existingValor, data: existingData, id_transacao: existingId };
  });
  return { json: { expense: originalData.expense, original_count: originalData.original_count, item_index: originalData.item_index, duplicates, has_duplicates: duplicates.length > 0 } };
});"""

add_node({
    'parameters': { 'jsCode': PROCESS_DUP_CODE, 'mode': 'runOnceForAllItems' },
    'type': 'n8n-nodes-base.code',
    'typeVersion': 2,
    'position': [mid_x + 200, mid_y],
    'id': None,
    'name': 'Process Duplicate Results'
})

# Rewire connections
rewire_connection('Split Expenses for Creation', 'Build Notion API Payload', 'Build Duplicate Check Query')
add_connection('Build Duplicate Check Query', 'HTTP Request - Check Duplicates')
add_connection('HTTP Request - Check Duplicates', 'Process Duplicate Results')
add_connection('Process Duplicate Results', 'Build Notion API Payload')
print("  OK: Added duplicate check chain between Split and Build Payload")

# Modify Format Enhanced Response
format_node = find_node('Format Enhanced Response')
if format_node:
    # Read the current code and inject duplicate detection
    original_code = format_node['parameters']['jsCode']

    MODIFIED_FORMAT_CODE = """// Format Enhanced Response (MODIFIED - includes duplicate detection alerts)
const prevData = $('Extract Category IDs').first().json;
const createdItems = prevData.created_items || [];
const categoryIds = prevData.category_ids || [];
const totalCount = prevData.total_count || 0;
const allCategories = $('Get Categorias Despesas').all().map(item => item.json);
const prop = $('Resolve Tenant Config').first().json.prop;

if (createdItems.length === 0) return [{ json: { text: '\\u274c Nenhuma transa\\u00e7\\u00e3o foi criada.', has_duplicates: false } }];

const optionsNode = $('Format Dynamic Options').first().json;
const categoriasArray = optionsNode.categorias_array || [];
const contasArray = optionsNode.contas_array || [];
const formasPagamentoArray = optionsNode.formas_pagamento_array || [];
const categoriaById = Object.fromEntries(categoriasArray.filter(x => x?.id && x?.nome).map(x => [x.id, x.nome]));
const contaById = Object.fromEntries(contasArray.filter(x => x?.id && x?.nome).map(x => [x.id, x.nome]));
const formaPagamentoById = Object.fromEntries(formasPagamentoArray.filter(x => x?.id && x?.nome).map(x => [x.id, x.nome]));

const categoryDataById = {};
allCategories.forEach(cat => {
  const id = cat.id; const p = cat.properties || {};
  let nome = ''; for (const [k,v] of Object.entries(p)) { if (v.type === 'title' && v.title?.length > 0) { nome = v.title[0]?.plain_text || ''; break; } }
  const esteMes = p[prop.este_mes]?.rollup?.number ?? 0;
  const orcamento = p[prop.orcamento]?.number ?? 0;
  const uso = p[prop.uso]?.formula?.number ?? 0;
  categoryDataById[id] = { nome, despesasEsteMes: esteMes, orcamentoMensal: orcamento, usoPercent: uso };
});

function formatDate(ds) { if (!ds) return 'N\\u00e3o informada'; const [y,m,d] = ds.split('-'); return `${d}/${m}/${y}`; }
function formatCurrency(v) { return `R$ ${v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; }
function formatPercent(d) { return `${(d * 100).toFixed(0)}%`; }
function escapeHtml(t) { if (!t) return ''; return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function resolveRelationNames(arr, map) { const ids = (arr||[]).map(r => r?.id).filter(Boolean); if (ids.length === 0) return '-'; return ids.map(id => map[id] || `(${id})`).join(', '); }

const _brand = $('Resolve Tenant Config').first().json.brand_name;
const lines = ['\\ud83c\\udff0 <b>' + _brand + '</b> \\ud83c\\udff0', '', `\\u2705 <b>${totalCount} ${prop.label}${totalCount > 1 ? 's' : ''} criada${totalCount > 1 ? 's' : ''} com sucesso!</b>`, '', '\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501', ''];

const allDuplicates = [];
let checkDuplicatesItems = [];
try { checkDuplicatesItems = $('Process Duplicate Results').all(); } catch(_) {}

createdItems.forEach((item, idx) => {
  const ps = item.properties || {};
  const title = escapeHtml((ps[prop.title]?.title?.[0]?.text?.content || ps[prop.title]?.title?.[0]?.plain_text || 'Sem t\\u00edtulo'));
  const date = ps['Data']?.date?.start;
  const valor = ps['Valor']?.number ?? 0;
  const id = ps.ID_transacao?.unique_id?.number || 'N/A';
  const obs = escapeHtml(ps.Obs?.rich_text?.[0]?.text?.content || '');
  const catNome = escapeHtml(resolveRelationNames(ps[prop.categoria]?.relation, categoriaById));
  const contaNome = escapeHtml(resolveRelationNames(ps['Conta']?.relation, contaById));
  const fpNome = escapeHtml(resolveRelationNames(ps[prop.forma_pagamento]?.relation, formaPagamentoById));
  const numParcelas = Math.max(1, Math.floor(Number(ps['# Parcelas Transacao']?.number ?? 1)));

  lines.push(`${idx + 1}. <b>${title}</b>`);
  if (obs) lines.push(`   \\ud83d\\udcdd Obs: <i>${obs}</i>`);
  lines.push('');
  lines.push(`   \\ud83d\\udcc5 Data: ${formatDate(date)}`);
  lines.push(`   \\ud83d\\udcb0 Valor: ${formatCurrency(valor)}`);
  lines.push(`   \\ud83d\\uddc3\\ufe0f Categoria: ${catNome}`);
  lines.push(`   \\ud83c\\udfe6 Conta: ${contaNome}`);
  lines.push(`   \\ud83d\\udcb3 Forma: ${fpNome}`);
  if (numParcelas > 1) lines.push(`   \\ud83d\\udce6 Parcelas: ${numParcelas}x`);
  lines.push(`   \\ud83c\\udd94 ID: ${id}`);
  lines.push('');

  const dupData = checkDuplicatesItems[idx]?.json;
  if (dupData && dupData.has_duplicates && dupData.duplicates?.length > 0) {
    allDuplicates.push({ new_item_title: title, new_item_id: id, existing: dupData.duplicates });
  }
});

lines.push('\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501'); lines.push('');

const categoriesInExpenses = categoryIds.map(id => categoryDataById[id]).filter(Boolean);
if (categoriesInExpenses.length > 0) {
  lines.push(`\\ud83d\\udcca <b>Acumulado no m\\u00eas (${prop.labels}):</b>`); lines.push('');
  categoriesInExpenses.forEach(cat => {
    lines.push(`\\ud83d\\uddc2\\ufe0f <b>${escapeHtml(cat.nome)}:</b>`);
    if (cat.orcamentoMensal > 0) { lines.push(`   ${formatCurrency(cat.despesasEsteMes)} de ${formatCurrency(cat.orcamentoMensal)}`); lines.push(`   <i>(${formatPercent(cat.usoPercent)} do or\\u00e7amento)</i>`); }
    else { lines.push(`   ${formatCurrency(cat.despesasEsteMes)}`); lines.push('   <i>(sem or\\u00e7amento)</i>'); }
    lines.push('');
  });
  let totalMes = 0, totalOrc = 0;
  allCategories.forEach(c => { totalMes += c.properties?.[prop.este_mes]?.rollup?.number ?? 0; totalOrc += c.properties?.[prop.orcamento]?.number ?? 0; });
  const totalUso = totalOrc > 0 ? totalMes / totalOrc : 0;
  lines.push(''); lines.push('\\ud83d\\udcc8 <b>Total Geral:</b>');
  if (totalOrc > 0) { lines.push(`   ${formatCurrency(totalMes)} de ${formatCurrency(totalOrc)}`); lines.push(`   <i>(${formatPercent(totalUso)} do or\\u00e7amento total)</i>`); }
  else { lines.push(`   ${formatCurrency(totalMes)}`); }
  lines.push('');
}

const hasDuplicates = allDuplicates.length > 0;
if (hasDuplicates) {
  lines.push(''); lines.push('\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501\\u2501'); lines.push('');
  lines.push('\\u26a0\\ufe0f <b>POSS\\u00cdVEL DUPLICATA DETECTADA</b>'); lines.push('');
  allDuplicates.forEach(dup => {
    lines.push(`A ${prop.label} "<b>${dup.new_item_title}</b>" (ID: ${dup.new_item_id}) pode ser duplicata de:`); lines.push('');
    dup.existing.forEach(ex => {
      lines.push(`   \\ud83d\\udccb ${escapeHtml(ex.titulo)}`);
      lines.push(`   \\ud83d\\udcb0 ${formatCurrency(ex.valor)}`);
      lines.push(`   \\ud83d\\udcc5 ${formatDate(ex.data)}`);
      lines.push(`   \\ud83c\\udd94 ID: ${ex.id_transacao}`); lines.push('');
    });
  });
  lines.push('A transa\\u00e7\\u00e3o foi criada normalmente.');
  lines.push('Se for duplicata, use o comando de dele\\u00e7\\u00e3o informando o ID.');
}

return [{ json: { text: lines.join('\\n'), has_duplicates: hasDuplicates } }];"""

    format_node['parameters']['jsCode'] = MODIFIED_FORMAT_CODE
    print("  OK: Modified 'Format Enhanced Response' with duplicate alerts")

# ============================================================
# SAVE
# ============================================================
print(f"\n=== Saving modified workflow ===")

output = copy.deepcopy(workflow)
for field in ['id', 'createdAt', 'updatedAt', 'versionId', 'homeProject', 'shared']:
    output.pop(field, None)

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)

print(f"  Saved to: {OUTPUT_FILE}")
print(f"  File size: {os.path.getsize(OUTPUT_FILE)} bytes")
print(f"  Total nodes: {len(output['nodes'])}")
print(f"\nAll 3 improvements applied successfully!")
