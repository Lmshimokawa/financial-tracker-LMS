# Agentes de IA - Financial Tracker v3

## Visão Geral

O workflow utiliza 7 agentes de IA baseados em OpenAI GPT-4o, cada um especializado em uma tarefa:

```
Mensagem do Usuário
    │
    └── Intent Classifier ─── Classifica a intenção
            │
            ├── create → Transaction Creator ─── Extrai dados para criação
            ├── update → Transaction Editor ─── Identifica campos para edição
            ├── retrieve → Transaction Retriever ─── Interpreta queries
            ├── delete → Transaction Eraser ─── Identifica IDs para exclusão
            ├── smalltalk → Smalltalk & Guidance ─── Responde casualmente
            └── clarify → Pede esclarecimentos ao usuário
```

---

## 1. Intent Classifier

**Tipo n8n**: `@n8n/n8n-nodes-langchain.agent`
**Modelo**: GPT-4o
**Output Parser**: Structured Output (JSON)

**Missão**: Classificar a intenção do usuário em uma das 6 categorias.

**Input**: Texto normalizado da mensagem do usuário.

**Output**: JSON com `action_type`:
```json
{ "action_type": "create | update | retrieve | delete | smalltalk | clarify" }
```

**Heurísticas de classificação**:
- `create`: Mensagens com valor monetário + descrição ("compra de esmaltes 200 reais")
- `update`: Referência a correção com ID ("corrigir valor da transação 12")
- `retrieve`: Queries sobre dados ("total do mês", "quanto gastei", "listar transações")
- `delete`: Remoção explícita ("apagar transação 123", "deletar ID 500")
- `smalltalk`: Saudações, despedidas, conversa casual
- `clarify`: Intenção ambígua ou insuficiente

---

## 2. Transaction Creator

**Tipo n8n**: `@n8n/n8n-nodes-langchain.agent`
**Modelo**: GPT-4o
**Output Parser**: Structured Output (JSON)

**Missão**: Extrair dados estruturados de transações a partir de mensagens em linguagem natural.

**Contexto dinâmico injetado**:
- `brand_name`: Nome do tenant
- `flow_type`: despesa ou receita
- `categorias_list`: Lista de categorias disponíveis
- `contas_list`: Lista de contas disponíveis
- `formas_pagamento_list`: Lista de formas de pagamento disponíveis

**Output**: Array de transações:
```json
{
  "items": [
    {
      "Titulo": "Esmaltes Mayco",
      "Obs": null,
      "Data": "2026-03-20",
      "Valor": 200.00,
      "Forma de Pagamento": "Cartão Nubank",
      "Categoria": "Material",
      "Conta": "Le",
      "# Parcelas Transacao": 1
    }
  ]
}
```

**Regras de normalização**:
- Valores em formato BR → float (`"R$ 45,90"` → `45.90`)
- Datas em PT-BR → ISO (`"20/03/2026"` → `"2026-03-20"`)
- Categoria, Conta e Forma de Pagamento devem corresponder **exatamente** às opções disponíveis
- Se dados não especificados: inferir defaults inteligentes (ex: data = hoje, conta = conta principal do usuário)
- Suporta **múltiplas transações** em uma única mensagem

---

## 3. Transaction Editor

**Tipo n8n**: `@n8n/n8n-nodes-langchain.agent`
**Modelo**: GPT-4o

**Missão**: Identificar transações existentes e campos a modificar.

**Output**:
```json
{
  "expenses": [
    {
      "ID_transacao": 123,
      "ID_explicito": "sim",
      "new_data": {
        "Titulo": null,
        "Obs": null,
        "Data": null,
        "Valor": 56.10,
        "Forma de Pagamento": "PIX",
        "Categoria": null,
        "Conta": null,
        "# Parcelas Transacao": null
      }
    }
  ]
}
```

**Regras**:
- Campos `null` = não alterar
- `ID_explicito = "sim"` se o usuário mencionou o ID explicitamente
- `ID_explicito = "nao"` se precisa perguntar qual transação editar
- Chave `"Forma de Pagamento"` é usada sempre (mesmo para receitas)

---

## 4. Transaction Retriever

**Tipo n8n**: `@n8n/n8n-nodes-langchain.agent`
**Modelo**: GPT-4o

**Missão**: Interpretar queries e gerar parâmetros de filtro/agregação.

**Output**:
```json
{
  "query_params": {
    "date_start": "2026-03-01",
    "date_end": "2026-03-31",
    "aggregation": "sum",
    "group_by": "categoria",
    "date_granularity": null,
    "data_source": "transacoes",
    "filters": {
      "categoria": null,
      "conta": null,
      "payment_method": null
    }
  }
}
```

**Tipos de agregação**: `sum`, `average`, `list`, `count`, `max`, `min`, `consolidado`
**Group by**: `date`, `categoria`, `conta`, `payment_method`, `null`
**Data source**: `transacoes` (dados originais) ou `parcelas` (fluxo de caixa)
**Date granularity** (quando group_by=date): `day`, `week`, `month`, `year`

---

## 5. Transaction Eraser

**Tipo n8n**: `@n8n/n8n-nodes-langchain.agent`
**Modelo**: GPT-4o

**Missão**: Identificar IDs de transações para exclusão.

**Output**:
```json
{
  "expenses": [
    { "ID_transacao": 123, "ID_explicito": "sim" },
    { "ID_transacao": 456, "ID_explicito": "sim" }
  ]
}
```

**Suporta exclusão em batch** ("deletar transações 100, 101 e 102").

---

## 6. Smalltalk & Guidance

**Tipo n8n**: `@n8n/n8n-nodes-langchain.agent`
**Modelo**: GPT-4o

**Missão**: Responder mensagens casuais e orientar o usuário sobre funcionalidades.

**Regras**:
- Sempre em PT-BR
- Tom leve e amigável
- 1-3 parágrafos curtos
- Mencionar naturalmente o que o bot pode fazer
- Não responder nada fora do domínio financeiro
- Se a mensagem mencionar gasto/receita, sugerir registrar

---

## 7. Vision (Basic LLM Chain)

**Tipo n8n**: `@n8n/n8n-nodes-langchain.chainLlm`
**Modelo**: GPT-4o (com visão)

**Missão**: Analisar imagens (fotos de recibos, screenshots de extrato, etc.).

**Prompt**:
```
Analyze this image with the message received above (if applicable).
1. Transcribe any text visible.
2. Describe the context (e.g., is it a screenshot of a calendar, a photo of a sticky note, a document?).
3. Output everything as a single string, in PT-BR.
```

**O output** é processado como texto normal pelo Intent Classifier → fluxo padrão.

---

## Fluxo de Dados dos Agentes

```
Mensagem (qualquer tipo)
    │
    ├── Normalização (text unificado)
    │
    ├── Fetch opções dinâmicas (categorias, contas, formas pgto)
    │
    └── Intent Classifier
            │
            ├─[create]──→ Transaction Creator
            │                   │
            │                   └── items[] → Split → Build Payload → Create → Parcelas → Response
            │
            ├─[update]──→ Transaction Editor
            │                   │
            │                   └── expenses[] → ID check → Get → Build Update → Update → Parcelas → Response
            │
            ├─[retrieve]─→ Transaction Retriever
            │                   │
            │                   └── query_params → Build Filter → Query Notion → Aggregate → Format → Response
            │
            ├─[delete]──→ Transaction Eraser
            │                   │
            │                   └── expenses[] → ID check → Get → Archive Parcelas → Delete → Response
            │
            ├─[smalltalk]→ Smalltalk Agent → Direct reply
            │
            └─[clarify]──→ "Pode dar mais detalhes?" → Wait for response
```
