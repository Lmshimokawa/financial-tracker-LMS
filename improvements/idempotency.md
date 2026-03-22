# Idempotency - Duplicate Transaction Alerts

## 1. Problem Description

The Financial Tracker workflow creates transactions in Notion databases via Telegram commands. Currently, when a user sends a message like "Almoco 35 reais" twice (accidentally or due to a network retry), two identical transactions are created in Notion with no warning. There is no mechanism to detect that a transaction with the same amount, date, and description already exists.

**Key constraint**: We must NOT block duplicate transactions. Users may legitimately have two identical purchases (e.g., the same coffee every day, two identical uber rides). The system must **alert** the user about the potential duplicate and let them decide whether to keep or remove it.

**Current create flow (no duplicate detection)**:
```
AI Agent - Transaction Creator
    -> Split Expenses for Creation
        -> Build Notion API Payload
            -> HTTP Request - Create Expense
                -> Create Parcelas for New Expense
                -> Aggregate Created Expenses
                    -> Extract Category IDs
                        -> Get Categorias Despesas
                            -> Format Enhanced Response
                                -> Reply user - new expense
```

---

## 2. Solution Architecture

### 2.1 Overview

Insert a duplicate detection step **after** the AI Agent extracts structured data and **before** the transaction is created in Notion. The transaction is **always created** regardless of duplicates. If a potential duplicate is found, the response message includes an alert with an inline keyboard button allowing the user to delete the newly created transaction.

### 2.2 Modified Create Flow

```
AI Agent - Transaction Creator
    -> Split Expenses for Creation
        -> Check Duplicates (NEW - queries Notion)
            -> Build Notion API Payload (unchanged)
                -> HTTP Request - Create Expense (unchanged)
                    -> Create Parcelas for New Expense (unchanged)
                    -> Aggregate Created Expenses (unchanged)
                        -> Extract Category IDs (unchanged)
                            -> Get Categorias Despesas (unchanged)
                                -> Format Enhanced Response (MODIFIED - includes duplicate alert)
                                    -> IF has duplicates?
                                        -> true:  Reply with Inline Keyboard (NEW)
                                        -> false: Reply user - new expense (unchanged)
```

### 2.3 Detection Criteria

A transaction is flagged as a **potential duplicate** if any existing transaction in the same Notion database matches **either** of:

| Rule | Fields Compared | Window |
|------|----------------|--------|
| **Exact match** | Same `Valor` AND same `Data` | Last 7 days from transaction date |
| **Fuzzy match** | Same `Valor` AND similar `Titulo` (contains/starts_with) | Last 7 days from transaction date |

The 7-day window is centered on the new transaction's date: `[Data - 3 days, Data + 3 days]`. This catches both past and future-dated duplicates.

### 2.4 User Experience

When a duplicate is detected, the confirmation message includes an additional section:

```
[normal creation confirmation message]

---
⚠️ POSSIVEL DUPLICATA DETECTADA

Transacao existente encontrada:
  📋 Titulo: Almoco
  💰 Valor: R$ 35,00
  📅 Data: 22/03/2026
  🆔 ID: 142

A transacao foi criada normalmente.
Deseja manter ou remover a nova transacao?

[Manter ✅]  [Remover ❌]
```

---

## 3. Complete Node Code

### 3a. "Check Duplicates" Node (Code Node)

**Type**: `n8n-nodes-base.code` (v2)
**Position**: Between `Split Expenses for Creation` and `Build Notion API Payload`
**Purpose**: For each transaction item, query Notion for potential duplicates and attach the results to the item.

```javascript
// Node: Check Duplicates
// Type: n8n-nodes-base.code v2
// Runs once per item from "Split Expenses for Creation"

const tenantConfig = $('Resolve Tenant Config').first().json;
const databaseId = tenantConfig.database_id_transacoes;
const prop = tenantConfig.prop;
const apiVersion = $('Extract Data Source ID').first().json.api_version || 'legacy_fallback';
const notionVersion = apiVersion === 'legacy_fallback' ? '2022-06-28' : '2025-09-03';

const results = [];

for (const item of items) {
  const expense = item.json.expense;
  if (!expense || !expense.Valor) {
    results.push({ json: { ...item.json, duplicates: [], has_duplicates: false } });
    continue;
  }

  const valor = expense.Valor;
  const titulo = expense.Titulo || '';
  const dataStr = expense.Data || $now.setZone('America/Sao_Paulo').toISODate();

  // Build date window: transaction date +/- 3 days
  const baseDate = new Date(dataStr + 'T12:00:00Z');
  const startDate = new Date(baseDate);
  startDate.setDate(startDate.getDate() - 3);
  const endDate = new Date(baseDate);
  endDate.setDate(endDate.getDate() + 3);

  const startISO = startDate.toISOString().split('T')[0];
  const endISO = endDate.toISOString().split('T')[0];

  // Notion API filter: same Valor AND Data within window
  const filter = {
    and: [
      {
        property: 'Valor',
        number: { equals: valor }
      },
      {
        property: 'Data',
        date: { on_or_after: startISO }
      },
      {
        property: 'Data',
        date: { on_or_before: endISO }
      }
    ]
  };

  try {
    const response = await fetch(
      `https://api.notion.com/v1/databases/${databaseId}/query`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${$credentials.notionApi.apiKey}`,
          'Notion-Version': notionVersion,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          filter: filter,
          page_size: 5
        })
      }
    );

    const data = await response.json();
    const existingPages = data.results || [];

    // Extract readable info from each potential duplicate
    const duplicates = existingPages.map(page => {
      const ps = page.properties || {};
      const titleProp = ps[prop.title]?.title || [];
      const existingTitle = titleProp[0]?.plain_text || titleProp[0]?.text?.content || '';
      const existingValor = ps['Valor']?.number ?? 0;
      const existingData = ps['Data']?.date?.start || '';
      const existingId = ps['ID_transacao']?.unique_id?.number || 'N/A';

      return {
        page_id: page.id,
        titulo: existingTitle,
        valor: existingValor,
        data: existingData,
        id_transacao: existingId
      };
    });

    results.push({
      json: {
        ...item.json,
        duplicates: duplicates,
        has_duplicates: duplicates.length > 0
      }
    });
  } catch (error) {
    // On error, proceed without blocking - just flag no duplicates
    results.push({
      json: {
        ...item.json,
        duplicates: [],
        has_duplicates: false,
        duplicate_check_error: error.message
      }
    });
  }
}

return results;
```

> **Important note on credentials**: n8n Code nodes cannot directly access `$credentials` via `fetch`. The recommended approach is to use an **HTTP Request node** instead of `fetch` inside the Code node. See Section 3c for the alternative architecture using an HTTP Request node for the Notion query.

### 3a (Alternative). HTTP Request Node Approach

Since n8n Code nodes do not expose credentials for use with `fetch`, the cleaner implementation splits the duplicate check into two nodes:

#### Node: "Build Duplicate Check Query" (Code Node)

```javascript
// Node: Build Duplicate Check Query
// Type: n8n-nodes-base.code v2
// Prepares the Notion API query payload for each expense item

const tenantConfig = $('Resolve Tenant Config').first().json;
const databaseId = tenantConfig.database_id_transacoes;

return items.map(item => {
  const expense = item.json.expense;
  if (!expense || !expense.Valor) {
    return { json: { ...item.json, _skip_duplicate_check: true } };
  }

  const valor = expense.Valor;
  const dataStr = expense.Data || $now.setZone('America/Sao_Paulo').toISODate();

  // Build date window: transaction date +/- 3 days
  const baseDate = new Date(dataStr + 'T12:00:00Z');
  const startDate = new Date(baseDate);
  startDate.setDate(startDate.getDate() - 3);
  const endDate = new Date(baseDate);
  endDate.setDate(endDate.getDate() + 3);

  const startISO = startDate.toISOString().split('T')[0];
  const endISO = endDate.toISOString().split('T')[0];

  const filter = {
    and: [
      {
        property: 'Valor',
        number: { equals: valor }
      },
      {
        property: 'Data',
        date: { on_or_after: startISO }
      },
      {
        property: 'Data',
        date: { on_or_before: endISO }
      }
    ]
  };

  return {
    json: {
      ...item.json,
      _duplicate_query: {
        url: `https://api.notion.com/v1/databases/${databaseId}/query`,
        body: { filter, page_size: 5 }
      },
      _skip_duplicate_check: false
    }
  };
});
```

#### Node: "HTTP Request - Check Duplicates" (HTTP Request Node)

```json
{
  "parameters": {
    "method": "POST",
    "url": "={{ $json._duplicate_query.url }}",
    "authentication": "predefinedCredentialType",
    "nodeCredentialType": "notionApi",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        {
          "name": "Notion-Version",
          "value": "={{ $('Extract Data Source ID').first().json.api_version === 'legacy_fallback' ? '2022-06-28' : '2025-09-03' }}"
        }
      ]
    },
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={{ JSON.stringify($json._duplicate_query.body) }}",
    "options": {
      "response": {
        "response": {
          "neverError": true
        }
      }
    }
  },
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "name": "HTTP Request - Check Duplicates"
}
```

#### Node: "Process Duplicate Results" (Code Node)

```javascript
// Node: Process Duplicate Results
// Type: n8n-nodes-base.code v2
// Parses the Notion query response and attaches duplicate info to each item

const prop = $('Resolve Tenant Config').first().json.prop;

return items.map((item, index) => {
  const json = item.json;

  // Get the original expense data from Build Duplicate Check Query
  const queryNode = $('Build Duplicate Check Query').all();
  const originalData = queryNode[index]?.json || {};
  const expense = originalData.expense;

  // Parse Notion response
  const existingPages = json.results || [];

  const duplicates = existingPages.map(page => {
    const ps = page.properties || {};
    const titleProp = ps[prop.title]?.title || [];
    const existingTitle = titleProp[0]?.plain_text || titleProp[0]?.text?.content || '';
    const existingValor = ps['Valor']?.number ?? 0;
    const existingData = ps['Data']?.date?.start || '';
    const existingId = ps['ID_transacao']?.unique_id?.number || 'N/A';

    return {
      page_id: page.id,
      titulo: existingTitle,
      valor: existingValor,
      data: existingData,
      id_transacao: existingId
    };
  });

  return {
    json: {
      expense: expense,
      original_count: originalData.original_count,
      item_index: originalData.item_index,
      duplicates: duplicates,
      has_duplicates: duplicates.length > 0
    }
  };
});
```

### 3b. "Format Duplicate Alert" Section in Format Enhanced Response (Modified)

The existing `Format Enhanced Response` node is modified to include duplicate alert information. The key additions are marked with `// NEW - duplicate detection` comments.

```javascript
// Node: Format Enhanced Response (MODIFIED)
// Type: n8n-nodes-base.code v2
// Changes: reads duplicate info from Check Duplicates node and appends alert section

const prevData = $('Extract Category IDs').first().json;
const createdItems = prevData.created_items || [];
const categoryIds = prevData.category_ids || [];
const totalCount = prevData.total_count || 0;
const allCategories = $('Get Categorias Despesas').all().map(item => item.json);
const prop = $('Resolve Tenant Config').first().json.prop;

if (createdItems.length === 0) return [{ json: { text: '❌ Nenhuma transação foi criada.', has_duplicates: false } }];

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

function formatDate(ds) { if (!ds) return 'Não informada'; const [y,m,d] = ds.split('-'); return `${d}/${m}/${y}`; }
function formatCurrency(v) { return `R$ ${v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; }
function formatPercent(d) { return `${(d * 100).toFixed(0)}%`; }
function escapeHtml(t) { if (!t) return ''; return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function resolveRelationNames(arr, map) { const ids = (arr||[]).map(r => r?.id).filter(Boolean); if (ids.length === 0) return '-'; return ids.map(id => map[id] || `(${id})`).join(', '); }

const _brand = $('Resolve Tenant Config').first().json.brand_name;
const lines = ['🏺 <b>' + _brand + '</b> 🏺', '', `✅ <b>${totalCount} ${prop.label}${totalCount > 1 ? 's' : ''} criada${totalCount > 1 ? 's' : ''} com sucesso!</b>`, '', '━━━━━━━━━━━━━━━', ''];

// NEW - collect duplicate info and page IDs for inline keyboard
const allDuplicates = [];
const newPageIds = [];

createdItems.forEach((item, idx) => {
  const ps = item.properties || {};
  const title = escapeHtml((ps[prop.title]?.title?.[0]?.text?.content || ps[prop.title]?.title?.[0]?.plain_text || 'Sem título'));
  const date = ps['Data']?.date?.start;
  const valor = ps['Valor']?.number ?? 0;
  const id = ps.ID_transacao?.unique_id?.number || 'N/A';
  const obs = escapeHtml(ps.Obs?.rich_text?.[0]?.text?.content || '');
  const catNome = escapeHtml(resolveRelationNames(ps[prop.categoria]?.relation, categoriaById));
  const contaNome = escapeHtml(resolveRelationNames(ps['Conta']?.relation, contaById));
  const fpNome = escapeHtml(resolveRelationNames(ps[prop.forma_pagamento]?.relation, formaPagamentoById));
  const numParcelas = Math.max(1, Math.floor(Number(ps['# Parcelas Transacao']?.number ?? 1)));

  lines.push(`${idx + 1}. <b>${title}</b>`);
  if (obs) lines.push(`   📝 Obs: <i>${obs}</i>`);
  lines.push('');
  lines.push(`   📅 Data: ${formatDate(date)}`);
  lines.push(`   💰 Valor: ${formatCurrency(valor)}`);
  lines.push(`   🗃️ Categoria: ${catNome}`);
  lines.push(`   🏦 Conta: ${contaNome}`);
  lines.push(`   💳 Forma: ${fpNome}`);
  if (numParcelas > 1) lines.push(`   📦 Parcelas: ${numParcelas}x`);
  lines.push(`   🆔 ID: ${id}`);
  lines.push('');

  // NEW - collect duplicate info from Check Duplicates node
  const checkDuplicatesItems = $('Process Duplicate Results').all();
  const dupData = checkDuplicatesItems[idx]?.json;
  if (dupData && dupData.has_duplicates && dupData.duplicates?.length > 0) {
    allDuplicates.push({
      new_item_index: idx,
      new_item_page_id: item.id,
      new_item_title: title,
      new_item_id: id,
      existing: dupData.duplicates
    });
    newPageIds.push(item.id);
  }
});

lines.push('━━━━━━━━━━━━━━━'); lines.push('');

// Category budget section (unchanged)
const categoriesInExpenses = categoryIds.map(id => categoryDataById[id]).filter(Boolean);
if (categoriesInExpenses.length > 0) {
  lines.push(`📊 <b>Acumulado no mês (${prop.labels}):</b>`); lines.push('');
  categoriesInExpenses.forEach(cat => {
    lines.push(`🗂️ <b>${escapeHtml(cat.nome)}:</b>`);
    if (cat.orcamentoMensal > 0) { lines.push(`   ${formatCurrency(cat.despesasEsteMes)} de ${formatCurrency(cat.orcamentoMensal)}`); lines.push(`   <i>(${formatPercent(cat.usoPercent)} do orçamento)</i>`); }
    else { lines.push(`   ${formatCurrency(cat.despesasEsteMes)}`); lines.push('   <i>(sem orçamento)</i>'); }
    lines.push('');
  });
  let totalMes = 0, totalOrc = 0;
  allCategories.forEach(c => { totalMes += c.properties?.[prop.este_mes]?.rollup?.number ?? 0; totalOrc += c.properties?.[prop.orcamento]?.number ?? 0; });
  const totalUso = totalOrc > 0 ? totalMes / totalOrc : 0;
  lines.push(''); lines.push('📈 <b>Total Geral:</b>');
  if (totalOrc > 0) { lines.push(`   ${formatCurrency(totalMes)} de ${formatCurrency(totalOrc)}`); lines.push(`   <i>(${formatPercent(totalUso)} do orçamento total)</i>`); }
  else { lines.push(`   ${formatCurrency(totalMes)}`); }
  lines.push('');
}

// NEW - Append duplicate alert section
const hasDuplicates = allDuplicates.length > 0;
if (hasDuplicates) {
  lines.push('');
  lines.push('━━━━━━━━━━━━━━━');
  lines.push('');
  lines.push('⚠️ <b>POSSIVEL DUPLICATA DETECTADA</b>');
  lines.push('');

  allDuplicates.forEach(dup => {
    lines.push(`A ${prop.label} "<b>${dup.new_item_title}</b>" (ID: ${dup.new_item_id}) pode ser duplicata de:`);
    lines.push('');
    dup.existing.forEach(existing => {
      lines.push(`   📋 ${escapeHtml(existing.titulo)}`);
      lines.push(`   💰 ${formatCurrency(existing.valor)}`);
      lines.push(`   📅 ${formatDate(existing.data)}`);
      lines.push(`   🆔 ID: ${existing.id_transacao}`);
      lines.push('');
    });
  });

  lines.push('A transação foi criada normalmente.');
  lines.push('Deseja <b>manter</b> ou <b>remover</b> a nova transação?');
}

return [{
  json: {
    text: lines.join('\n'),
    has_duplicates: hasDuplicates,
    // NEW - pass page IDs for inline keyboard callback
    duplicate_new_page_ids: newPageIds,
    duplicate_details: allDuplicates
  }
}];
```

### 3c. Modified Create Flow - Connection Changes

The create flow connections must be updated. Below is the complete modified connection map:

```
BEFORE (current):
  Split Expenses for Creation -> Build Notion API Payload -> HTTP Request - Create Expense -> ...

AFTER (new):
  Split Expenses for Creation
      -> Build Duplicate Check Query (NEW)
          -> HTTP Request - Check Duplicates (NEW)
              -> Process Duplicate Results (NEW)
                  -> Build Notion API Payload (MODIFIED to read from Process Duplicate Results)
                      -> HTTP Request - Create Expense
                          -> Create Parcelas for New Expense (unchanged)
                          -> Aggregate Created Expenses (unchanged)
                              -> Extract Category IDs (unchanged)
                                  -> Get Categorias Despesas (unchanged)
                                      -> Format Enhanced Response (MODIFIED)
                                          -> IF Has Duplicates? (NEW)
                                              -> true:  Reply with Inline Keyboard (NEW)
                                              -> false: Reply user - new expense (unchanged)
```

#### Node: "IF Has Duplicates?" (IF Node)

```json
{
  "parameters": {
    "conditions": {
      "options": { "caseSensitive": true, "leftValue": "" },
      "conditions": [
        {
          "leftValue": "={{ $json.has_duplicates }}",
          "rightValue": true,
          "operator": {
            "type": "boolean",
            "operation": "equals",
            "name": "filter.operator.equals"
          }
        }
      ],
      "combinator": "and"
    }
  },
  "type": "n8n-nodes-base.if",
  "typeVersion": 2,
  "name": "IF Has Duplicates?"
}
```

#### Node: "Reply with Inline Keyboard" (HTTP Request Node)

Since n8n's built-in Telegram node does not natively support `reply_markup` with inline keyboards, we use an HTTP Request node to call the Telegram Bot API directly:

```javascript
// Node: Reply with Inline Keyboard
// Type: n8n-nodes-base.code v2
// Builds the Telegram sendMessage payload with inline keyboard

const chatId = $('Resolve Tenant Config').first().json.message.chat.id;
const text = $json.text;
const pageIds = $json.duplicate_new_page_ids || [];
const prop = $('Resolve Tenant Config').first().json.prop;
const tenantConfig = $('Resolve Tenant Config').first().json;
const databaseId = tenantConfig.database_id_transacoes;
const parcelasDbId = tenantConfig.database_id_parcelas;

// Build inline keyboard - one row per duplicated transaction
const inlineKeyboard = pageIds.map((pageId, idx) => {
  // Callback data format: action:page_id:parcelas_db_id
  // Max 64 bytes per callback_data - use compact format
  return [
    {
      text: `Manter ✅ (#${idx + 1})`,
      callback_data: `dup_keep:${pageId.slice(0, 24)}`
    },
    {
      text: `Remover ❌ (#${idx + 1})`,
      callback_data: `dup_del:${pageId.slice(0, 24)}`
    }
  ];
});

return [{
  json: {
    chat_id: chatId,
    text: text,
    parse_mode: 'HTML',
    reply_markup: {
      inline_keyboard: inlineKeyboard
    }
  }
}];
```

#### Node: "HTTP Request - Send Duplicate Alert" (HTTP Request Node)

```json
{
  "parameters": {
    "method": "POST",
    "url": "=https://api.telegram.org/bot{{ $credentials.telegramApi.accessToken }}/sendMessage",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={{ JSON.stringify($json) }}",
    "options": {}
  },
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "name": "HTTP Request - Send Duplicate Alert"
}
```

> **Credential access note**: Similar to the Notion credential limitation, `$credentials.telegramApi.accessToken` may not be available in expressions depending on the n8n version. See Section 4 for the recommended workaround using the Telegram bot token stored in the tenant config or as a workflow-level static variable.

#### "Build Notion API Payload" Modification

The existing `Build Notion API Payload` node must be updated to read `expense` from `Process Duplicate Results` instead of `Split Expenses for Creation`. The only change needed is replacing:

```javascript
// BEFORE (line 1 of the existing code):
// return items.map(item => {
//   const expense = item.json.expense;

// No change needed - the Process Duplicate Results node passes through
// the expense object in the same json.expense structure.
// The Build Notion API Payload reads from the current item's json,
// which comes from Process Duplicate Results (the upstream node).
```

No code change is required in Build Notion API Payload since `Process Duplicate Results` outputs `{ expense, ... }` in the same shape as `Split Expenses for Creation`.

---

## 4. Callback Handling for Telegram Inline Keyboards in n8n

### 4.1 The Challenge

Telegram inline keyboard buttons send a `callback_query` to the bot when pressed. n8n's Telegram Trigger node can receive these callbacks, but you need to:

1. Detect that the incoming update is a `callback_query` (not a regular message)
2. Parse the `callback_data` to determine the action
3. Execute the action (delete or keep the transaction)
4. Answer the callback query (required by Telegram API to remove the loading state)
5. Update the original message to reflect the action taken

### 4.2 Architecture

```
Telegram Trigger (existing - already receives all updates)
    -> Detect Callback Query (NEW - Switch node)
        -> callback_query path:
            -> Parse Duplicate Callback (Code node)
                -> Switch: Keep or Delete?
                    -> dup_keep:
                        -> Answer Callback Query ("Mantida!")
                        -> Edit Original Message (remove buttons)
                    -> dup_del:
                        -> Get Parcelas by Transaction (Delete)
                            -> Archive Parcelas
                        -> HTTP Request - Archive Transaction
                        -> Answer Callback Query ("Removida!")
                        -> Edit Original Message (update text + remove buttons)
        -> regular message path:
            -> [existing flow continues unchanged]
```

### 4.3 Detecting Callback Queries

The Telegram Trigger in n8n receives all update types. A `callback_query` update has the structure:

```json
{
  "update_id": 123456,
  "callback_query": {
    "id": "unique_callback_id",
    "from": { "id": 12345, "first_name": "User" },
    "message": {
      "message_id": 789,
      "chat": { "id": -100123456 }
    },
    "data": "dup_del:abc123pageId"
  }
}
```

#### Node: "Is Callback Query?" (Switch Node)

Add this as the **first** node after Telegram Trigger (before `Resolve Tenant Config`), or integrate into the existing routing logic:

```json
{
  "parameters": {
    "rules": {
      "values": [
        {
          "conditions": {
            "conditions": [
              {
                "leftValue": "={{ $json.callback_query?.data }}",
                "rightValue": "dup_",
                "operator": {
                  "type": "string",
                  "operation": "startsWith"
                }
              }
            ]
          },
          "renameOutput": "duplicate_callback"
        },
        {
          "conditions": {
            "conditions": [
              {
                "leftValue": "={{ $json.message || $json.callback_query === undefined }}",
                "rightValue": true,
                "operator": {
                  "type": "boolean",
                  "operation": "equals"
                }
              }
            ]
          },
          "renameOutput": "regular_message"
        }
      ]
    }
  },
  "type": "n8n-nodes-base.switch",
  "typeVersion": 3,
  "name": "Is Callback Query?"
}
```

### 4.4 Parse and Execute Callback

#### Node: "Parse Duplicate Callback" (Code Node)

```javascript
// Node: Parse Duplicate Callback
// Type: n8n-nodes-base.code v2

const callbackQuery = $json.callback_query;
const callbackData = callbackQuery.data; // e.g., "dup_del:abc123pageIdPrefix"
const callbackId = callbackQuery.id;
const chatId = callbackQuery.message.chat.id;
const messageId = callbackQuery.message.message_id;
const originalText = callbackQuery.message.text || '';

const [action, pageIdPrefix] = callbackData.split(':');

return [{
  json: {
    action: action,           // "dup_keep" or "dup_del"
    page_id_prefix: pageIdPrefix,
    callback_id: callbackId,
    chat_id: chatId,
    message_id: messageId,
    original_text: originalText
  }
}];
```

#### Node: "Switch: Keep or Delete" (Switch Node)

Routes based on `$json.action`:
- `dup_keep` -> Answer callback + edit message (remove buttons, append "Mantida")
- `dup_del` -> Delete transaction + answer callback + edit message

#### Node: "Find Full Page ID" (Code Node - for dup_del path)

Since we truncated the page ID to fit Telegram's 64-byte callback_data limit, we need to find the full page ID. The recommended approach is to query Notion or store the mapping in a workflow static data:

```javascript
// Node: Find Full Page ID
// Type: n8n-nodes-base.code v2
// Uses workflow static data to look up the full page ID from the prefix

const staticData = $getWorkflowStaticData('global');
const prefix = $json.page_id_prefix;

// Look up full page ID from stored mapping
const fullPageId = staticData[`dup_page_${prefix}`] || null;

if (!fullPageId) {
  // Fallback: query Notion to find the page
  // This should rarely happen if we store the mapping at creation time
  return [{ json: { ...$json, error: 'Page ID not found in static data', full_page_id: null } }];
}

return [{ json: { ...$json, full_page_id: fullPageId } }];
```

> **Important**: To make this work, the `Reply with Inline Keyboard` node must store the mapping in workflow static data:
>
> ```javascript
> // Add to "Reply with Inline Keyboard" node:
> const staticData = $getWorkflowStaticData('global');
> pageIds.forEach(pageId => {
>   staticData[`dup_page_${pageId.slice(0, 24)}`] = pageId;
> });
> ```

#### Node: "HTTP Request - Archive Duplicate Transaction" (HTTP Request Node)

```json
{
  "parameters": {
    "method": "PATCH",
    "url": "=https://api.notion.com/v1/pages/{{ $json.full_page_id }}",
    "authentication": "predefinedCredentialType",
    "nodeCredentialType": "notionApi",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "Notion-Version", "value": "2025-09-03" }
      ]
    },
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "{ \"archived\": true }",
    "options": {}
  },
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "name": "HTTP Request - Archive Duplicate Transaction"
}
```

#### Node: "HTTP Request - Answer Callback Query" (HTTP Request Node)

Required by Telegram to acknowledge the button press and remove the loading spinner:

```json
{
  "parameters": {
    "method": "POST",
    "url": "=https://api.telegram.org/bot{{ $json.telegram_bot_token }}/answerCallbackQuery",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={{ JSON.stringify({ callback_query_id: $json.callback_id, text: $json.action === 'dup_keep' ? 'Transação mantida!' : 'Transação removida!' }) }}",
    "options": {}
  },
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "name": "HTTP Request - Answer Callback Query"
}
```

#### Node: "HTTP Request - Edit Message (Remove Buttons)" (HTTP Request Node)

After the user presses a button, update the original message to show the outcome and remove the inline keyboard:

```json
{
  "parameters": {
    "method": "POST",
    "url": "=https://api.telegram.org/bot{{ $json.telegram_bot_token }}/editMessageReplyMarkup",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={{ JSON.stringify({ chat_id: $json.chat_id, message_id: $json.message_id, reply_markup: { inline_keyboard: [] } }) }}",
    "options": {}
  },
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "name": "HTTP Request - Edit Message (Remove Buttons)"
}
```

### 4.5 Telegram Bot Token Access

Since HTTP Request nodes calling the Telegram API directly need the bot token, there are two approaches:

**Option A (Recommended)**: Store the bot token in the `Resolve Tenant Config` node as `telegram_bot_token` and reference it via `$('Resolve Tenant Config').first().json.telegram_bot_token`.

**Option B**: Create a workflow-level Code node that reads the token from an environment variable:
```javascript
const token = $env.TELEGRAM_BOT_TOKEN;
```

### 4.6 Parcelas Cleanup on Delete

When the user chooses to remove a duplicate, the associated parcelas must also be archived. Reuse the existing delete flow logic:

1. Query parcelas database filtering by the transaction relation
2. Archive each parcela
3. Archive the main transaction

This can be implemented as a sub-workflow call or by duplicating the relevant nodes from the existing Delete Flow.

```javascript
// Node: Get Parcelas for Duplicate Delete
// Reuses the same pattern as "Get Parcelas by Transaction (Delete)"
// Query: filter by Transacao relation containing the page_id

const tenantConfig = $('Resolve Tenant Config').first().json;
// Note: In the callback path, Resolve Tenant Config may not be available.
// Store tenant info (parcelas_db_id, flow_type) in workflow static data
// alongside the page ID mapping.

const staticData = $getWorkflowStaticData('global');
const pageId = $json.full_page_id;
const prefix = $json.page_id_prefix;
const tenantInfo = staticData[`dup_tenant_${prefix}`] || {};

return [{
  json: {
    page_id: pageId,
    parcelas_db_id: tenantInfo.parcelas_db_id,
    parcela_rel_prop: tenantInfo.parcela_rel_prop,
    notion_version: tenantInfo.notion_version || '2025-09-03'
  }
}];
```

---

## 5. Implementation Instructions

### Step 1: Backup the Workflow

Export the current `financial-tracker-v3.json` before making any changes.

### Step 2: Add Duplicate Check Nodes (3 nodes)

1. **Create** `Build Duplicate Check Query` (Code node)
   - Position: between `Split Expenses for Creation` and `Build Notion API Payload`
   - Paste the code from Section 3a (Alternative)

2. **Create** `HTTP Request - Check Duplicates` (HTTP Request node)
   - Connect: `Build Duplicate Check Query` -> `HTTP Request - Check Duplicates`
   - Configure as shown in Section 3a (Alternative)

3. **Create** `Process Duplicate Results` (Code node)
   - Connect: `HTTP Request - Check Duplicates` -> `Process Duplicate Results`
   - Paste the code from Section 3a (Alternative)

4. **Rewire**: `Process Duplicate Results` -> `Build Notion API Payload` (remove the old connection from `Split Expenses for Creation` to `Build Notion API Payload`)

### Step 3: Modify Format Enhanced Response

Replace the code in `Format Enhanced Response` with the modified version from Section 3b. The node reads duplicate data from `Process Duplicate Results` and appends the alert section.

### Step 4: Add Conditional Reply Routing (2 nodes)

1. **Create** `IF Has Duplicates?` (IF node)
   - Connect: `Format Enhanced Response` -> `IF Has Duplicates?`
   - Remove the old connection from `Format Enhanced Response` -> `Reply user - new expense`

2. **Rewire**:
   - `IF Has Duplicates?` (false/output 1) -> `Reply user - new expense` (existing)
   - `IF Has Duplicates?` (true/output 0) -> `Reply with Inline Keyboard` (new)

3. **Create** `Reply with Inline Keyboard` (Code node) + `HTTP Request - Send Duplicate Alert` (HTTP Request node)
   - Paste code from Section 3c
   - Connect: `Reply with Inline Keyboard` -> `HTTP Request - Send Duplicate Alert`

### Step 5: Add Callback Handler (6 nodes)

1. **Create** `Is Callback Query?` (Switch node)
   - Insert as the first routing node after Telegram Trigger
   - Route `duplicate_callback` output to `Parse Duplicate Callback`
   - Route `regular_message` output to the existing `Resolve Tenant Config`

2. **Create** these nodes in sequence:
   - `Parse Duplicate Callback` (Code)
   - `Switch: Keep or Delete` (Switch)
   - `Find Full Page ID` (Code) - on the `dup_del` path
   - `HTTP Request - Archive Duplicate Transaction` (HTTP Request)
   - `HTTP Request - Answer Callback Query` (HTTP Request) - on both paths
   - `HTTP Request - Edit Message (Remove Buttons)` (HTTP Request) - on both paths

### Step 6: Store Context in Workflow Static Data

In the `Reply with Inline Keyboard` node, ensure you store:
- Page ID mapping: `dup_page_{prefix}` -> full page ID
- Tenant info: `dup_tenant_{prefix}` -> `{ parcelas_db_id, parcela_rel_prop, notion_version }`

Add a TTL cleanup mechanism to prevent static data from growing indefinitely:

```javascript
// Add to Reply with Inline Keyboard node:
const staticData = $getWorkflowStaticData('global');
const now = Date.now();

// Clean up entries older than 24 hours
for (const key of Object.keys(staticData)) {
  if (key.startsWith('dup_') && staticData[`${key}_ts`] && (now - staticData[`${key}_ts`]) > 86400000) {
    delete staticData[key];
    delete staticData[`${key}_ts`];
  }
}

// Store new entries with timestamp
pageIds.forEach(pageId => {
  const prefix = pageId.slice(0, 24);
  staticData[`dup_page_${prefix}`] = pageId;
  staticData[`dup_page_${prefix}_ts`] = now;
  staticData[`dup_tenant_${prefix}`] = {
    parcelas_db_id: tenantConfig.database_id_parcelas,
    parcela_rel_prop: prop.parcela_transacao_rel,
    notion_version: notionVersion
  };
  staticData[`dup_tenant_${prefix}_ts`] = now;
});
```

### Step 7: Test Scenarios

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | Create a unique transaction | Normal flow, no alert |
| 2 | Create the same transaction again (same valor + date) | Transaction created + duplicate alert with inline keyboard |
| 3 | Press "Manter" button | Buttons removed, transaction kept |
| 4 | Press "Remover" button | Transaction + parcelas archived, buttons removed, confirmation |
| 5 | Two different transactions, same amount, different dates (>7 days apart) | No alert |
| 6 | Two transactions, same amount, dates 2 days apart | Alert shown |
| 7 | Multiple transactions in one message (batch) | Each checked independently |
| 8 | Network error during duplicate check | Transaction created normally, no alert (graceful degradation) |

### Step 8: Verify Node Connections

After implementing, verify the connection map in the n8n editor:

```
Split Expenses for Creation
  -> Build Duplicate Check Query
    -> HTTP Request - Check Duplicates
      -> Process Duplicate Results
        -> Build Notion API Payload
          -> HTTP Request - Create Expense
            -> Create Parcelas for New Expense
            -> Aggregate Created Expenses
              -> Extract Category IDs
                -> Get Categorias Despesas
                  -> Format Enhanced Response (modified)
                    -> IF Has Duplicates?
                      -> [true]  Reply with Inline Keyboard -> HTTP Request - Send Duplicate Alert
                      -> [false] Reply user - new expense (unchanged)
```

---

## Summary of New Nodes

| # | Node Name | Type | Purpose |
|---|-----------|------|---------|
| 1 | Build Duplicate Check Query | Code | Prepares Notion filter query |
| 2 | HTTP Request - Check Duplicates | HTTP Request | Queries Notion for similar transactions |
| 3 | Process Duplicate Results | Code | Parses results, attaches duplicate info |
| 4 | IF Has Duplicates? | IF | Routes to appropriate reply node |
| 5 | Reply with Inline Keyboard | Code | Builds Telegram inline keyboard payload |
| 6 | HTTP Request - Send Duplicate Alert | HTTP Request | Sends message with buttons via Telegram API |
| 7 | Is Callback Query? | Switch | Detects callback from inline keyboard |
| 8 | Parse Duplicate Callback | Code | Extracts action and page ID from callback |
| 9 | Switch: Keep or Delete | Switch | Routes keep vs delete actions |
| 10 | Find Full Page ID | Code | Resolves truncated page ID from static data |
| 11 | HTTP Request - Archive Duplicate Transaction | HTTP Request | Archives the duplicate in Notion |
| 12 | HTTP Request - Answer Callback Query | HTTP Request | Acknowledges button press to Telegram |
| 13 | HTTP Request - Edit Message (Remove Buttons) | HTTP Request | Removes inline keyboard after action |

**Modified Nodes**: `Format Enhanced Response` (1 node)

**Total**: 13 new nodes + 1 modified node
