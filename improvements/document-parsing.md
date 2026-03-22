# Improvement: Smart Document Parsing for Financial Tracker

## 1. Problem Description

The current document parsing pipeline in the Financial Tracker n8n workflow has significant limitations that reduce the quality and reliability of transaction extraction from uploaded documents.

### Current Issues

1. **PDF extraction produces garbled text**: Bank statements and credit card bills have complex multi-column layouts, headers, footers, and decorative elements. The n8n "Extract From File" node outputs raw text that often has jumbled column alignment, merged lines, and unreadable segments.

2. **No intelligent column mapping for CSV/XLSX**: Different banks and financial institutions use different column names. For example:
   - Nubank CSV: `date`, `title`, `amount`
   - Itau XLSX: `Data`, `Lançamento`, `Valor (R$)`
   - Bradesco: `Data Mov.`, `Histórico`, `Valor`
   - Inter: `Data Lançamento`, `Descrição`, `Valor`
   - Generic exports: `DATE`, `DESCRIPTION`, `DEBIT`, `CREDIT`

   The current code just dumps everything as raw JSON with no normalization.

3. **No pre-processing of financial data**: The raw content goes straight to the AI agent, which must figure out column mapping, filter irrelevant rows (headers, totals, disclaimers), and extract transactions all at once.

4. **Large documents overwhelm context windows**: A 3-month bank statement might have 500+ rows. Dumping all of that as raw JSON consumes the AI agent's context window and degrades response quality.

5. **No error handling for malformed documents**: Corrupt files, password-protected PDFs, or unexpected formats cause silent failures.

---

## 2. Solution Architecture

### Strategy: Smart Pre-Processing Layer

Replace the simple "Unify content" Code node with an intelligent parsing pipeline that normalizes document content before it reaches the AI agent.

```
Document type (Switch)
    │
    ├── CSV  → Extract From File (CSV)  ─┐
    ├── XLSX → Extract From File (XLSX) ─┤
    ├── XLS  → Extract From File (XLS)  ─┤
    └── PDF  → Extract From File (PDF)  ─┘
                                          │
                                    [Smart Parse & Normalize]  ← NEW (replaces "Unify content")
                                          │
                                    Normaliza mensagem3
                                          │
                                    Normalize Input → AI Agent
```

### Parsing Strategies by Document Type

| Document Type | Strategy |
|---------------|----------|
| CSV / XLSX / XLS | Column header analysis → fuzzy match to standard fields → row normalization → output structured transactions |
| PDF | Pattern-based extraction (dates, currency amounts, descriptions) → line-by-line transaction assembly → fallback to raw text |

### Standardized Output Format

All documents are normalized to this structure before reaching the AI agent:

```json
{
  "content": "DOCUMENTO FINANCEIRO PROCESSADO\nTipo: extrato_bancario\nArquivo: extrato_nubank_mar2026.csv\nTransações encontradas: 47\nPeríodo: 01/03/2026 a 22/03/2026\n\n--- TRANSAÇÕES ---\n1. 01/03/2026 | Uber *Trip | -R$ 23,50\n2. 01/03/2026 | Pag*JoseDaSilva | -R$ 15,00\n...\n\n--- RESUMO ---\nTotal entradas: R$ 3.200,00\nTotal saídas: R$ 2.847,30\n\n[Mostrando 47 de 47 transações]"
}
```

This format:
- Gives the AI agent structured context about what the document is
- Presents transactions in a consistent, readable format
- Includes summary statistics for validation
- Chunks large documents to stay within context limits

---

## 3. Complete Improved Code for "Smart Parse & Normalize" Node

This replaces the current "Unify content" Code node. In n8n, create a **Code** node with **JavaScript** language and paste the following:

```javascript
// ============================================================
// SMART PARSE & NORMALIZE - Financial Document Parser
// Replaces the old "Unify content" node
// ============================================================
// This node receives extracted file content from n8n's
// "Extract From File" nodes and applies intelligent parsing
// to produce a standardized output for the AI agent.
// ============================================================

const items = $input.all();
const MAX_TRANSACTIONS = 150; // Max transactions to send to AI (chunking threshold)
const MAX_CONTENT_LENGTH = 12000; // Max characters for content field

// -------------------------------------------------------
// UTILITY FUNCTIONS
// -------------------------------------------------------

/**
 * Normalize a string for comparison: lowercase, trim, remove accents and special chars
 */
function norm(s) {
  if (typeof s !== 'string') return '';
  return s.toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]/g, '')
    .trim();
}

/**
 * Parse a Brazilian-format number string to a float.
 * Handles: "1.234,56" → 1234.56, "-R$ 1.234,56" → -1234.56, "(1234.56)" → -1234.56
 */
function parseAmount(raw) {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === 'number') return raw;
  let s = String(raw).trim();
  if (!s) return null;

  // Check for parentheses notation (negative)
  const isParenNeg = /^\(.*\)$/.test(s);
  if (isParenNeg) s = s.replace(/[()]/g, '');

  // Check for explicit negative sign or D/C indicators
  const hasNegSign = /^-/.test(s) || /\bD\b/i.test(s) || /débito/i.test(s);

  // Remove currency symbols and whitespace
  s = s.replace(/[R$\s]/g, '').replace(/[a-zA-Záéíóúãõç]/gi, '');

  // Determine decimal format
  // Brazilian: 1.234,56 → commas are decimal
  // US: 1,234.56 → dots are decimal
  const lastComma = s.lastIndexOf(',');
  const lastDot = s.lastIndexOf('.');

  let cleaned;
  if (lastComma > lastDot) {
    // Brazilian format: dots are thousands, comma is decimal
    cleaned = s.replace(/\./g, '').replace(',', '.');
  } else if (lastDot > lastComma) {
    // US format: commas are thousands, dot is decimal
    cleaned = s.replace(/,/g, '');
  } else if (lastComma >= 0 && lastDot < 0) {
    // Only commas present - treat as decimal
    cleaned = s.replace(',', '.');
  } else {
    cleaned = s.replace(/,/g, '');
  }

  cleaned = cleaned.replace(/[^0-9.\-]/g, '');
  const val = parseFloat(cleaned);
  if (isNaN(val)) return null;
  return (isParenNeg || hasNegSign) ? -Math.abs(val) : val;
}

/**
 * Parse a date string in various formats to ISO (YYYY-MM-DD).
 * Handles: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, DD/MM/YY, MM/DD/YYYY (US).
 * Assumes Brazilian DD/MM/YYYY by default.
 */
function parseDate(raw) {
  if (!raw) return null;
  let s = String(raw).trim();

  // Already ISO format
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) {
    return s.substring(0, 10);
  }

  // DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
  let m = s.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})$/);
  if (m) {
    let day = parseInt(m[1], 10);
    let month = parseInt(m[2], 10);
    let year = parseInt(m[3], 10);
    if (year < 100) year += 2000;

    // Heuristic: if day > 12, it's definitely DD/MM/YYYY
    // if month > 12, it's MM/DD/YYYY
    // default to DD/MM/YYYY (Brazilian)
    if (month > 12 && day <= 12) {
      [day, month] = [month, day];
    }

    if (day >= 1 && day <= 31 && month >= 1 && month <= 12) {
      return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    }
  }

  // Try native Date parse as fallback
  const d = new Date(s);
  if (!isNaN(d.getTime())) {
    return d.toISOString().substring(0, 10);
  }

  return null;
}

/**
 * Format amount as Brazilian Real
 */
function formatBRL(amount) {
  if (amount === null || amount === undefined) return 'N/A';
  const abs = Math.abs(amount);
  const formatted = abs.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return (amount < 0 ? '-' : '') + 'R$ ' + formatted;
}

/**
 * Format ISO date as DD/MM/YYYY
 */
function formatDateBR(isoDate) {
  if (!isoDate) return 'N/A';
  const [y, m, d] = isoDate.split('-');
  return `${d}/${m}/${y}`;
}

// -------------------------------------------------------
// COLUMN DETECTION FOR TABULAR DATA (CSV / XLSX / XLS)
// -------------------------------------------------------

/**
 * Known column name patterns mapped to standard fields.
 * Each entry: [standardField, ...patterns]
 */
const COLUMN_PATTERNS = {
  date: [
    'data', 'date', 'dt', 'data_mov', 'data_movimentacao', 'data_lancamento',
    'data_transacao', 'data_compra', 'data_pagamento', 'transaction_date',
    'posting_date', 'datamov', 'datalancamento', 'datatransacao',
    'datacompra', 'datapagamento', 'dtmov', 'dtlancamento', 'vencimento',
    'data_vencimento'
  ],
  description: [
    'descricao', 'description', 'desc', 'titulo', 'title', 'historico',
    'lancamento', 'estabelecimento', 'merchant', 'nome', 'name',
    'memo', 'detail', 'detalhe', 'detalhes', 'observacao', 'obs',
    'descricaolancamento', 'historicolancamento', 'transaction'
  ],
  amount: [
    'valor', 'amount', 'value', 'vlr', 'montante', 'total',
    'valortransacao', 'valorlancamento', 'transactionamount',
    'valorrs', 'valorreais', 'price', 'preco'
  ],
  debit: [
    'debito', 'debit', 'saida', 'saidas', 'deb', 'despesa',
    'valordebitors', 'valordebito'
  ],
  credit: [
    'credito', 'credit', 'entrada', 'entradas', 'cred', 'receita',
    'valorcreditors', 'valorcredito'
  ],
  category: [
    'categoria', 'category', 'cat', 'tipo', 'type', 'classificacao',
    'grupo', 'group'
  ],
  balance: [
    'saldo', 'balance', 'saldofinal', 'saldoapos', 'saldodisponivel',
    'runningbalance'
  ]
};

/**
 * Match a column header to a standard field name.
 * Returns the standard field name or null.
 */
function matchColumn(header) {
  const normalized = norm(header);
  if (!normalized) return null;

  for (const [field, patterns] of Object.entries(COLUMN_PATTERNS)) {
    for (const pattern of patterns) {
      if (normalized === pattern || normalized.includes(pattern) || pattern.includes(normalized)) {
        return field;
      }
    }
  }
  return null;
}

/**
 * Detect columns by examining headers and optionally sample data.
 * Returns a mapping: { date: 'originalColName', description: '...', amount: '...', ... }
 */
function detectColumns(headers) {
  const mapping = {};
  const usedHeaders = new Set();

  // First pass: exact/pattern match
  for (const header of headers) {
    const field = matchColumn(header);
    if (field && !mapping[field]) {
      mapping[field] = header;
      usedHeaders.add(header);
    }
  }

  // If we have debit/credit but no amount, that's fine - we'll combine them later
  // If we have amount but no debit/credit, also fine

  return mapping;
}

/**
 * Extract a transaction from a row using the detected column mapping.
 */
function extractTransaction(row, mapping) {
  const tx = {
    date: null,
    description: null,
    amount: null,
    category: null,
    raw: {}
  };

  // Date
  if (mapping.date && row[mapping.date] !== undefined) {
    tx.date = parseDate(row[mapping.date]);
  }

  // Description
  if (mapping.description && row[mapping.description] !== undefined) {
    tx.description = String(row[mapping.description]).trim();
  }

  // Amount - prefer single amount column, otherwise combine debit/credit
  if (mapping.amount && row[mapping.amount] !== undefined) {
    tx.amount = parseAmount(row[mapping.amount]);
  } else {
    const debit = mapping.debit ? parseAmount(row[mapping.debit]) : null;
    const credit = mapping.credit ? parseAmount(row[mapping.credit]) : null;
    if (debit !== null && debit !== 0) {
      tx.amount = -Math.abs(debit);
    } else if (credit !== null && credit !== 0) {
      tx.amount = Math.abs(credit);
    }
  }

  // Category
  if (mapping.category && row[mapping.category] !== undefined) {
    tx.category = String(row[mapping.category]).trim();
  }

  // Preserve raw data for fallback
  tx.raw = row;

  return tx;
}

// -------------------------------------------------------
// PDF PATTERN-BASED EXTRACTION
// -------------------------------------------------------

/**
 * Extract transactions from PDF text content using regex patterns.
 * Looks for lines containing date + description + amount patterns.
 */
function extractFromPDF(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
  const transactions = [];

  // Pattern: date at start of line, then description, then amount
  // Brazilian date: DD/MM/YYYY or DD/MM/YY
  const datePattern = /(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)/;
  // Amount pattern: optional negative, optional R$, digits with separators
  const amountPattern = /(-?\s*R?\$?\s*[\d.,]+[\d])/;

  // Common patterns in Brazilian bank statements:
  // Pattern 1: DD/MM  Description  -1.234,56
  // Pattern 2: DD/MM/YYYY  Description  R$ 1.234,56
  // Pattern 3: DD/MM  DD/MM  Description  1.234,56 (date + posting date)

  const lineRegex = /^(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)\s+(?:(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)\s+)?(.+?)\s+(-?\s*R?\$?\s*[\d]+[.,\d]*[\d])\s*$/;

  // Also try a more relaxed pattern
  const relaxedRegex = /(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)\s+(.+?)\s{2,}(-?\s*R?\$?\s*[\d]+[.,\d]*[\d])/;

  for (const line of lines) {
    let match = line.match(lineRegex);
    if (!match) {
      match = line.match(relaxedRegex);
      if (match) {
        // Adjust capture groups for relaxed pattern (no second date group)
        match = [match[0], match[1], null, match[2], match[3]];
      }
    }
    if (match) {
      const dateStr = match[1];
      const description = (match[3] || '').trim();
      const amountStr = match[4];

      // Skip summary/total lines
      const descLower = description.toLowerCase();
      if (descLower.includes('saldo') && (descLower.includes('anterior') || descLower.includes('final'))) continue;
      if (descLower.includes('total') && descLower.includes('período')) continue;
      if (descLower === 'total' || descLower === 'subtotal') continue;

      const date = parseDate(dateStr);
      const amount = parseAmount(amountStr);

      if (description && description.length > 1) {
        transactions.push({
          date,
          description: description.replace(/\s+/g, ' '),
          amount,
          category: null,
          raw: { line }
        });
      }
    }
  }

  return transactions;
}

// -------------------------------------------------------
// DOCUMENT TYPE DETECTION
// -------------------------------------------------------

/**
 * Try to identify the type of financial document.
 */
function detectDocumentType(transactions, rawContent) {
  const contentLower = (rawContent || '').toLowerCase();

  if (contentLower.includes('fatura') || contentLower.includes('cartão') || contentLower.includes('cartao')) {
    return 'fatura_cartao';
  }
  if (contentLower.includes('extrato') || contentLower.includes('movimentação') || contentLower.includes('movimentacao')) {
    return 'extrato_bancario';
  }
  if (contentLower.includes('nota fiscal') || contentLower.includes('nf-e') || contentLower.includes('cupom fiscal')) {
    return 'nota_fiscal';
  }
  if (contentLower.includes('recibo')) {
    return 'recibo';
  }

  // Heuristic: if most amounts are negative, likely a statement
  if (transactions.length > 5) {
    const negCount = transactions.filter(t => t.amount !== null && t.amount < 0).length;
    if (negCount / transactions.length > 0.6) return 'extrato_bancario';
  }

  return 'documento_financeiro';
}

const DOC_TYPE_LABELS = {
  fatura_cartao: 'Fatura de Cartão de Crédito',
  extrato_bancario: 'Extrato Bancário',
  nota_fiscal: 'Nota Fiscal',
  recibo: 'Recibo',
  documento_financeiro: 'Documento Financeiro'
};

// -------------------------------------------------------
// MAIN PROCESSING LOGIC
// -------------------------------------------------------

function processTabularData(items) {
  // Items from CSV/XLSX/XLS extraction come as array of {json: {row: {...}}} or {json: {...}}
  const rows = items.map(item => item.json.row || item.json);

  if (rows.length === 0) return { transactions: [], rawContent: '', headers: [] };

  // Detect headers from first row keys
  const headers = Object.keys(rows[0]);
  const mapping = detectColumns(headers);

  // Extract transactions
  const transactions = [];
  for (const row of rows) {
    const tx = extractTransaction(row, mapping);

    // Skip rows that have no useful data (empty description AND no amount)
    if (!tx.description && tx.amount === null) continue;
    // Skip header-like rows that might have been included as data
    if (tx.description && /^(data|date|descri|valor|amount|total)/i.test(tx.description)) continue;

    transactions.push(tx);
  }

  return {
    transactions,
    rawContent: JSON.stringify(rows.slice(0, 3), null, 2),
    headers,
    mapping
  };
}

function processPDFData(items) {
  // PDF extraction typically returns a single item with text content
  let rawText = '';
  if (items.length === 1) {
    const j = items[0].json;
    rawText = j.content || j.text || JSON.stringify(j);
  } else {
    rawText = items.map(i => i.json.content || i.json.text || JSON.stringify(i.json)).join('\n');
  }

  const transactions = extractFromPDF(rawText);
  return { transactions, rawContent: rawText };
}

function formatOutput(transactions, rawContent, fileName, fileType) {
  const docType = detectDocumentType(transactions, rawContent);
  const docTypeLabel = DOC_TYPE_LABELS[docType] || docType;

  // If no transactions were extracted, fall back to raw content
  if (transactions.length === 0) {
    const truncated = rawContent.length > MAX_CONTENT_LENGTH
      ? rawContent.substring(0, MAX_CONTENT_LENGTH) + '\n\n[... conteúdo truncado, documento muito grande ...]'
      : rawContent;
    return {
      content: `DOCUMENTO RECEBIDO (parsing automático não encontrou transações estruturadas)\n`
        + `Tipo detectado: ${docTypeLabel}\n`
        + `Arquivo: ${fileName || 'N/A'}\n\n`
        + `--- CONTEÚDO BRUTO ---\n${truncated}\n\n`
        + `INSTRUÇÕES: Analise o conteúdo acima e extraia as transações financeiras manualmente. `
        + `Para cada transação, identifique: data, descrição, valor e categoria (se disponível).`
    };
  }

  // Calculate summary
  let totalIn = 0, totalOut = 0;
  let minDate = null, maxDate = null;

  for (const tx of transactions) {
    if (tx.amount !== null) {
      if (tx.amount >= 0) totalIn += tx.amount;
      else totalOut += tx.amount;
    }
    if (tx.date) {
      if (!minDate || tx.date < minDate) minDate = tx.date;
      if (!maxDate || tx.date > maxDate) maxDate = tx.date;
    }
  }

  // Chunk if too many transactions
  const displayTxs = transactions.slice(0, MAX_TRANSACTIONS);
  const wasChunked = transactions.length > MAX_TRANSACTIONS;

  // Build output
  let output = `DOCUMENTO FINANCEIRO PROCESSADO\n`;
  output += `Tipo: ${docTypeLabel}\n`;
  output += `Arquivo: ${fileName || 'N/A'}\n`;
  output += `Transações encontradas: ${transactions.length}\n`;
  if (minDate && maxDate) {
    output += `Período: ${formatDateBR(minDate)} a ${formatDateBR(maxDate)}\n`;
  }
  output += `\n--- TRANSAÇÕES ---\n`;

  for (let i = 0; i < displayTxs.length; i++) {
    const tx = displayTxs[i];
    const date = tx.date ? formatDateBR(tx.date) : '??/??/????';
    const desc = tx.description || '(sem descrição)';
    const amount = tx.amount !== null ? formatBRL(tx.amount) : '?';
    const cat = tx.category ? ` [${tx.category}]` : '';
    output += `${i + 1}. ${date} | ${desc} | ${amount}${cat}\n`;
  }

  if (wasChunked) {
    output += `\n[... mostrando ${MAX_TRANSACTIONS} de ${transactions.length} transações. `
      + `As demais foram omitidas para não sobrecarregar o contexto. `
      + `Processe as transações exibidas e informe o usuário sobre o total.]\n`;
  }

  output += `\n--- RESUMO ---\n`;
  if (totalIn > 0) output += `Total entradas: ${formatBRL(totalIn)}\n`;
  if (totalOut < 0) output += `Total saídas: ${formatBRL(totalOut)}\n`;
  output += `Saldo líquido: ${formatBRL(totalIn + totalOut)}\n`;

  // Safety truncation
  if (output.length > MAX_CONTENT_LENGTH) {
    output = output.substring(0, MAX_CONTENT_LENGTH) + '\n\n[... conteúdo truncado ...]';
  }

  return { content: output };
}

// -------------------------------------------------------
// ENTRY POINT
// -------------------------------------------------------

try {
  if (items.length === 0) {
    return [{ json: { content: '(Nenhum conteúdo extraído do documento.)' } }];
  }

  // Detect if this is tabular data (CSV/XLSX/XLS) or text (PDF)
  // Heuristic: tabular data has .row objects or multiple items with consistent keys
  const firstJson = items[0].json;
  const isPDF = (typeof firstJson.content === 'string' || typeof firstJson.text === 'string')
    && !firstJson.row
    && items.length <= 2;
  const isTabular = firstJson.row || (items.length > 1 && typeof firstJson === 'object' && !firstJson.content);

  // Try to get filename from previous nodes
  const fileName = items[0].json.fileName
    || items[0].json.file_name
    || $('Get Document File')?.first()?.json?.file_name
    || $('Get Document File')?.first()?.json?.document?.file_name
    || 'documento';

  let result;

  if (isTabular || (!isPDF && items.length > 2)) {
    // Tabular data path (CSV, XLSX, XLS)
    const { transactions, rawContent, headers, mapping } = processTabularData(items);
    result = formatOutput(transactions, rawContent, fileName, 'tabular');

    // Add mapping info for debugging
    if (mapping && Object.keys(mapping).length > 0) {
      result.content += `\n\n--- MAPEAMENTO DE COLUNAS DETECTADO ---\n`;
      for (const [field, col] of Object.entries(mapping)) {
        result.content += `${field} → "${col}"\n`;
      }
    }
  } else if (isPDF) {
    // PDF text path
    const { transactions, rawContent } = processPDFData(items);
    result = formatOutput(transactions, rawContent, fileName, 'pdf');
  } else {
    // Fallback: try tabular first, then PDF, then raw
    try {
      const { transactions, rawContent } = processTabularData(items);
      if (transactions.length > 0) {
        result = formatOutput(transactions, rawContent, fileName, 'tabular');
      } else {
        const pdfResult = processPDFData(items);
        if (pdfResult.transactions.length > 0) {
          result = formatOutput(pdfResult.transactions, pdfResult.rawContent, fileName, 'pdf');
        } else {
          // Raw fallback
          let rawContent = '';
          if (items.length === 1) {
            const j = items[0].json;
            if (typeof j.content === 'string') rawContent = j.content;
            else if (typeof j.text === 'string') rawContent = j.text;
            else if (j.data && Array.isArray(j.data)) rawContent = JSON.stringify(j.data, null, 2);
            else rawContent = JSON.stringify(j, null, 2);
          } else {
            const rows = items.map(i => i.json.row || i.json);
            rawContent = JSON.stringify(rows, null, 2);
          }
          result = formatOutput([], rawContent, fileName, 'unknown');
        }
      }
    } catch (e) {
      // Ultimate fallback
      const raw = JSON.stringify(items.map(i => i.json), null, 2);
      result = formatOutput([], raw, fileName, 'unknown');
    }
  }

  return [{ json: result }];

} catch (error) {
  // Global error handler - never let the node fail silently
  let fallbackContent = '';
  try {
    if (items.length === 1) {
      const j = items[0].json;
      fallbackContent = j.content || j.text || JSON.stringify(j, null, 2);
    } else {
      fallbackContent = JSON.stringify(items.map(i => i.json), null, 2);
    }
  } catch (e2) {
    fallbackContent = '(Erro ao processar documento)';
  }

  // Truncate if needed
  if (fallbackContent.length > MAX_CONTENT_LENGTH) {
    fallbackContent = fallbackContent.substring(0, MAX_CONTENT_LENGTH) + '\n[... truncado ...]';
  }

  return [{
    json: {
      content: `ERRO NO PARSING DO DOCUMENTO\n`
        + `Erro: ${error.message}\n\n`
        + `--- CONTEÚDO BRUTO (FALLBACK) ---\n${fallbackContent}\n\n`
        + `INSTRUÇÕES: O parsing automático falhou. Analise o conteúdo bruto acima e extraia as transações manualmente.`
    }
  }];
}
```

---

## 4. Additional Nodes / Changes

### 4.1 Update "Normaliza mensagem3" Context Prompt

The "Normaliza mensagem3" node (Set/Code node that adds context before the AI agent) should be updated to include parsing-aware instructions. Update its template to:

```javascript
// In "Normaliza mensagem3" - update the system context that wraps document content
const content = $json.content || '(sem conteúdo)';

const contextMessage = `O usuário enviou um documento financeiro via Telegram. `
  + `O conteúdo foi pré-processado e normalizado automaticamente. `
  + `Abaixo está o resultado do parsing:\n\n`
  + `${content}\n\n`
  + `INSTRUÇÕES PARA O AGENTE:\n`
  + `- Cada linha na seção TRANSAÇÕES representa uma transação individual.\n`
  + `- O formato é: DATA | DESCRIÇÃO | VALOR [CATEGORIA]\n`
  + `- Valores negativos são saídas/despesas, positivos são entradas/receitas.\n`
  + `- Pergunte ao usuário qual conta e forma de pagamento usar, a menos que seja óbvio pelo contexto.\n`
  + `- Se o documento contém muitas transações, confirme com o usuário antes de criar todas.\n`
  + `- Agrupe transações similares se possível e pergunte se o usuário quer criar todas ou apenas algumas.`;

return [{ json: { text: contextMessage } }];
```

### 4.2 Optional: Add a "Document Preview" Reply Node

For better UX, add an optional Telegram reply **before** the AI agent processes the document. This gives the user immediate feedback while the AI processes.

Place this between "Smart Parse & Normalize" and "Normaliza mensagem3":

**Node type**: Telegram > Send Message
**Node name**: `Document Receipt Confirmation`
**Message text** (Expression):

```
📄 Documento recebido e processado!

{{ $json.content.includes('Transações encontradas:')
   ? $json.content.match(/Transações encontradas: (\d+)/)?.[1] + ' transações detectadas.'
   : 'Analisando conteúdo...' }}

Processando com IA, aguarde...
```

**Important**: This node is optional. If you don't want the extra message, skip it.

### 4.3 No Other Node Changes Required

The rest of the pipeline remains unchanged:
- "Extract From File" nodes continue working as before (they feed into the new parser)
- "Normalize Input" continues consolidating all message types into `{ text }`
- The AI Agent receives better-structured input but doesn't need prompt changes beyond what "Normaliza mensagem3" provides

---

## 5. Implementation Instructions

### Step-by-Step in n8n

1. **Open the workflow** `Financial Tracker & Report Consolidated LMS v3` in the n8n editor.

2. **Locate the "Unify content" node**. It's connected after all four "Extract From File" nodes (CSV, XLSX, PDF, XLS) and before "Normaliza mensagem3".

3. **Replace the code**:
   - Double-click the "Unify content" node.
   - Select all existing code and delete it.
   - Paste the complete code from Section 3 above.
   - Rename the node to `Smart Parse & Normalize` (optional but recommended).
   - Click "Execute Node" with test data to verify.

4. **Update "Normaliza mensagem3"**:
   - Double-click the "Normaliza mensagem3" node.
   - Update the code/template with the content from Section 4.1.
   - Ensure the output still produces `{ text: '...' }` as the downstream "Normalize Input" node expects.

5. **Test with sample documents**:

   | Test Case | What to Verify |
   |-----------|----------------|
   | Nubank CSV export | Columns auto-detected, amounts parsed correctly with Brazilian format |
   | Itau XLSX statement | Different column names mapped correctly |
   | Bank PDF statement | Date-description-amount lines extracted via regex |
   | Garbled PDF | Fallback to raw content with instructions for AI |
   | Empty file | Graceful "no content" message |
   | 500+ row CSV | Chunking kicks in, shows first 150 rows with summary |
   | Mixed debit/credit columns (no single amount column) | Debit/credit combined correctly |

6. **Optional - Add Document Receipt Confirmation** (Section 4.2):
   - Add a new Telegram "Send Message" node.
   - Connect it between "Smart Parse & Normalize" and "Normaliza mensagem3" (as a branch, not blocking).
   - Configure it to send to the same chat_id.

7. **Save and activate** the workflow.

### Rollback Plan

If issues arise, revert the "Smart Parse & Normalize" node to the original "Unify content" code (saved below for reference):

```javascript
// ORIGINAL CODE - keep as backup
const items = $input.all();
let content = '';
if (items.length === 0) {
  content = '(Nenhum conteúdo extraído.)';
} else if (items.length === 1) {
  const j = items[0].json;
  if (typeof j.content === 'string') content = j.content;
  else if (typeof j.text === 'string') content = j.text;
  else if (j.data && Array.isArray(j.data)) content = JSON.stringify(j.data, null, 2);
  else if (j.row && typeof j.row === 'object') content = JSON.stringify([j.row], null, 2);
  else content = JSON.stringify(j, null, 2);
} else {
  const rows = items.map(i => i.json.row || i.json);
  content = JSON.stringify(rows, null, 2);
}
return [{ json: { content } }];
```

### Future Enhancements

1. **OCR for scanned PDFs**: Integrate an OCR service (Google Vision API, AWS Textract) as a pre-step for PDFs that return empty text from the basic extractor.
2. **Bank-specific parsers**: Add dedicated parsers for the most common Brazilian banks (Nubank, Itau, Bradesco, BB, Inter, C6) with known CSV/PDF formats.
3. **Learning from corrections**: Store column mappings per bank/format so repeated imports auto-detect faster.
4. **Duplicate detection**: Compare extracted transactions against existing Notion records to flag potential duplicates before creation.
