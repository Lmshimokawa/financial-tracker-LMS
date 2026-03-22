# Arquitetura Detalhada - Financial Tracker v3

## Visão Geral do Workflow

O workflow `Financial Tracker & Report Consolidated LMS v3` (ID: `bE7b3g5hVB8VVCCU`) é composto por **190 nodes** organizados em 3 fluxos principais:

1. **Fluxo Interativo (Telegram Trigger)** - CRUD de transações via chat
2. **Fluxo Semanal (Schedule Trigger)** - Relatório semanal automático
3. **Fluxo Mensal (Schedule Trigger)** - Relatório mensal automático

---

## 1. Fluxo Interativo (Telegram → Notion)

### 1.1 Pipeline de Entrada

```
Telegram Trigger
    │
    ├── Resolve Tenant Config     ← Identifica tenant pelo chat_id
    │       │
    │       ├── Get Notion API Version → Extract Notion API Version
    │       │       │
    │       │       ├── Get Data Source ID → Extract Data Source ID
    │       │       │       │
    │       │       │       ├── Fetch Categorias ─┐
    │       │       │       ├── Fetch Contas ──────┤
    │       │       │       ├── Fetch Formas Pag. ─┤
    │       │       │       └── Format Dynamic Options
    │       │
    │       └── Identifica tipo (message_type: text|photo|voice|document)
    │               │
    │               └── Direciona Tipo Msg (Switch)
    │                       │
    │                       ├── text → Normaliza mensagem
    │                       ├── photo → Recebe Imagem → GPT Vision → Normaliza mensagem1
    │                       ├── voice → Get file → Whisper → Normaliza mensagem2
    │                       └── document → Get Document File → Document type (Switch)
    │                               │
    │                               ├── CSV → Extract From File (CSV)
    │                               ├── XLSX → Extract From File (XLSX)
    │                               ├── PDF → Extract From File (PDF)
    │                               ├── XLS → Extract From File (XLS)
    │                               └── Outros → "Tipo não suportado"
    │                               │
    │                               └── Unify content → Normaliza mensagem3
    │
    └── Normalize Input (consolida todos os tipos em { text })
            │
            └── Route After Options (Switch por intent)
                    │
                    └── AI Agent - Intent Classifier
                            │
                            └── Direciona intencao (Switch)
                                    │
                                    ├── smalltalk → AI Agent Smalltalk → Reply
                                    ├── clarify → Pede esclarecimentos
                                    ├── create → [Create Flow]
                                    ├── update → [Update Flow]
                                    ├── retrieve → [Retrieve Flow]
                                    └── delete → [Delete Flow]
```

### 1.2 Create Flow (Criação de Transações)

```
AI Agent - Transaction Creator (extrai dados estruturados)
    │
    └── Split Expenses for Creation (1 item por transação)
            │
            └── Build Notion API Payload (monta payload Notion)
                    │
                    └── HTTP Request - Create Expense
                            │
                            ├── Create Parcelas for New Expense
                            │       └── HTTP Request - Create Parcela (loop)
                            │
                            ├── Aggregate Created Expenses
                            │       └── Extract Category IDs
                            │               └── Get Categorias Despesas
                            │                       └── Format Enhanced Response
                            │                               └── Reply user - new expense (Telegram)
                            │
                            └── [Error] → Informa mensagem do erro
```

### 1.3 Update Flow (Edição de Transações)

```
AI Agent - Transaction Editor (identifica IDs e campos)
    │
    ├── ID explicitado? (Switch)
    │       ├── sim → Split Expenses for Update
    │       └── nao → Confirm expense ID (pede ID ao usuário) → Wait
    │
    └── Split Expenses for Update
            │
            └── Get Expense by ID (Notion)
                    │
                    ├── Get Parcelas by Transaction (Update) → Archive Parcelas existentes
                    │
                    └── Build Update Payload → HTTP Request - Update Expense
                            │
                            ├── Create Parcelas for Updated Expense (recria parcelas)
                            │
                            └── Aggregate Updated Expenses → Format Enhanced Update Response
                                    └── Reply user - updated expense
```

### 1.4 Retrieve Flow (Consultas)

```
AI Agent - Transaction Retriever (interpreta query)
    │
    └── Build Notion Filter (monta filtros)
            │
            ├── Route Retrieve by Data Source (Switch)
            │       ├── transacoes → Get Filtered Expenses
            │       │       └── Aggregate Results → Formata Resposta para Telegram
            │       │               └── Reply user - query result
            │       │
            │       └── parcelas → Get Filtered Parcelas
            │               └── Aggregate Parcelas → Format Parcelas Response
            │                       └── Reply user - query result
            │
            └── [Sem resultados] → No Results Found
```

### 1.5 Delete Flow (Exclusão)

```
AI Agent - Transaction Eraser (identifica IDs)
    │
    ├── ID explicitado?1 (Switch)
    │       ├── sim → Split Expenses for Deletion
    │       └── nao → Confirm expense ID1 → Wait1
    │
    └── Split Expenses for Deletion
            │
            └── Get Expense by ID for Delete
                    │
                    ├── Get Parcelas by Transaction (Delete) → Archive Parcelas
                    │
                    └── HTTP Request - Delete Expense
                            │
                            └── Aggregate Deleted Expenses → Format Deletion Response
                                    └── Reply user - deleted expense
```

---

## 2. Fluxo Semanal (Schedule Trigger)

```
Schedule Trigger - Weekly
    │
    └── Build Tenant List (Weekly) ← gera lista de tenants x flow_types
            │
            └── Loop Reports (Weekly) (splitInBatches)
                    │
                    └── Set Report Config (Weekly)
                            │
                            ├── Get Current Month Data (Notion)
                            ├── Get Month -1, -2, -3 (Notion)
                            ├── Get Categorias (Notion)
                            └── Get Contas (Notion)
                                    │
                                    └── Merge → Process All Data
                                            │
                                            ├── Format Weekly Summary → Send Weekly Summary (Telegram)
                                            │
                                            ├── Prepare Category Chart → Generate → Send Category Chart
                                            ├── Prepare Conta Chart → Generate → Send Conta Chart
                                            └── Prepare Comparison Chart → Generate → Send Comparison Chart
```

---

## 3. Fluxo Mensal (Schedule Trigger)

```
Schedule Trigger - Monthly
    │
    └── Build Tenant List (Monthly)
            │
            └── Loop Reports (Monthly)
                    │
                    └── Set Report Config (Monthly)
                            │
                            ├── Get Month Report (Notion)
                            ├── Get Month M-2, M-3, M-4 (Notion)
                            ├── Get Categorias1, Get Contas1
                            │
                            └── Merge1 → Process Monthly Data
                                    │
                                    ├── Format Monthly Summary → Send Monthly Summary
                                    │
                                    ├── Prepare Evolution Chart → Generate → Send
                                    ├── Prepare Budget Chart → Generate → Send
                                    └── Prepare Category Pie → Generate → Send
```

---

## Multi-Tenancy

### Resolve Tenant Config

O node central `Resolve Tenant Config` determina qual tenant está ativo baseado no `chat_id` do Telegram. Cada tenant possui:

- `brand_name`: Nome exibido nas mensagens
- `timezone`: Fuso horário
- `telegram_chat_id`: Chat do Telegram para despesas
- `telegram_chat_id_receita`: Chat do Telegram para receitas
- **Databases (despesa)**: transacoes, categorias, contas, parcelas, formas_pagamento
- **Databases (receita)**: transacoes, categorias, contas, parcelas, formas_pagamento

O `flow_type` (despesa/receita) é determinado pelo `chat_id` específico, e um objeto `prop` normaliza os nomes das propriedades entre despesas e receitas:

```javascript
prop = {
  title: "Despesa" | "Receita",
  label: "despesa" | "receita",
  labels: "despesas" | "receitas",
  categoria: "Categoria Despesa" | "Categoria Receita",
  forma_pagamento: "Forma de Pagamento" | "Forma de Recebimento",
  parcela_transacao_rel: "Transacao" | "Receitas - Transacoes",
  // ... outros mapeamentos
}
```

---

## Agentes de IA

| Agente | Modelo | Função |
|--------|--------|--------|
| Intent Classifier | GPT-4o | Classifica intenção: create, update, retrieve, delete, smalltalk, clarify |
| Transaction Creator | GPT-4o | Extrai dados estruturados para criação |
| Transaction Editor | GPT-4o | Identifica campos a atualizar |
| Transaction Retriever | GPT-4o | Interpreta queries e monta filtros |
| Transaction Eraser | GPT-4o | Identifica IDs para exclusão |
| Smalltalk & Guidance | GPT-4o | Responde mensagens casuais com orientação |
| Basic LLM Chain (Vision) | GPT-4o | Transcreve/analisa imagens |

---

## Fluxo de Dados Notion

### API Versions
O sistema suporta dois modos da API Notion:
- **Legacy (2022-06-28)**: `parent: { database_id }`
- **New (2025-09-03)**: `parent: { data_source_id }` (obtido via Get Data Source ID)

### Parcelas
Para transações parceladas:
1. **Create**: Cria N parcelas com `Valor / N` e datas incrementais (mês a mês)
2. **Update**: Arquiva parcelas existentes → Recria com novos dados
3. **Delete**: Arquiva parcelas → Deleta transação principal
