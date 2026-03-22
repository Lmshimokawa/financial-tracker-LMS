# Schema das Databases Notion

O sistema utiliza **5 databases por flow_type** (despesa/receita) **por tenant**, totalizando 10 databases por tenant.

## Databases de Despesas

### 1. Despesas - Transacoes
> Database principal de transações de despesa.

| Propriedade | Tipo | Descrição |
|-------------|------|-----------|
| **Despesa** | `title` | Nome/descrição da transação |
| **Valor** | `number` (R$) | Valor total da transação |
| **Data** | `date` | Data da transação |
| **ID_transacao** | `unique_id` | ID único auto-gerado |
| **Obs** | `rich_text` | Observações opcionais |
| **# Parcelas Transacao** | `number` | Número de parcelas (1 = à vista) |
| **Categoria Despesa** | `relation` → Categorias | Categoria da despesa |
| **Conta** | `relation` → Contas | Conta que pagou |
| **Forma de Pagamento** | `relation` → Formas de Pagamento | Meio de pagamento |
| **Despesas - Parcelas** | `relation` → Parcelas | Parcelas associadas |
| Despesa Este Mês | `formula` | Valor se transação é do mês atual, 0 caso contrário |
| Dia de Fechamento Fatura | `formula` (via rollup) | Dia de fechamento do cartão |
| Dia de Vencimento Fatura | `formula` (via rollup) | Dia de vencimento da fatura |
| Tipo Forma de Pagamento | `formula` (via rollup) | Tipo do meio de pagamento |
| Intervalo entre Fechamento e Vencimento | `formula` (via rollup) | Dias entre fechamento e vencimento |

### 2. Categorias Despesas
> Categorias para classificar despesas.

| Propriedade | Tipo | Descrição |
|-------------|------|-----------|
| **Categoria Despesa** | `title` | Nome da categoria |
| **Tipo Despesa** | `select` | Classificação do tipo |
| **Orçamento Mensal** | `number` | Budget mensal da categoria |
| Despesas | `relation` → Transacoes | Transações nesta categoria |
| Despesas Este Mês | `rollup` | Soma das despesas do mês atual |
| Uso | `formula` | Percentual de uso do orçamento |

### 3. Contas
> Contas bancárias / carteiras.

| Propriedade | Tipo | Descrição |
|-------------|------|-----------|
| **Conta** | `title` | Nome da conta |
| **Valor Inicial** | `number` | Saldo inicial |
| Despesas | `relation` → Transacoes Despesa | Despesas desta conta |
| Receitas | `relation` → Transacoes Receita | Receitas desta conta |
| TransferToAccount | `relation` → Contas | Transferências recebidas |
| TransferOut | `relation` → Contas | Transferências enviadas |
| Total Despesas | `rollup` | Soma das despesas |
| Total Receitas | `rollup` | Soma das receitas |
| Total TransferIn | `rollup` | Soma transferências recebidas |
| Total TransferOut | `rollup` | Soma transferências enviadas |
| Saldo | `formula` | Valor Inicial + Receitas - Despesas + TransferIn - TransferOut |
| Texto Saldo | `formula` | Saldo formatado para exibição |

### 4. Despesas - Parcelas
> Parcelas individuais de transações parceladas.

| Propriedade | Tipo | Descrição |
|-------------|------|-----------|
| **Despesa** | `title` | Título da parcela (ex: "Compra X (2/3)") |
| **Valor** | `number` | Valor da parcela individual |
| **Data Cobranca** | `date` | Data de cobrança da parcela |
| **Obs** | `rich_text` | Observações |
| **Transacao** | `relation` → Transacoes | Transação pai |
| ID_transacao | `rollup` | ID da transação pai |
| Categoria Despesa | `rollup` | Categoria (via transação) |
| Conta | `rollup` | Conta (via transação) |
| Forma de Pagamento | `rollup` | Forma de pagamento (via transação) |
| Tipo Forma de Pagamento | `rollup` | Tipo (via transação) |
| Dia de Fechamento Fatura | `rollup` | Dia fechamento (via forma de pagamento) |
| Dia de Vencimento Fatura | `rollup` | Dia vencimento (via forma de pagamento) |
| Data Vencimento | `formula` | Data de vencimento calculada |
| Intervalo entre Fechamento e Vencimento | `rollup` | Intervalo (via forma de pagamento) |

### 5. Despesas - Formas de Pagamento
> Meios de pagamento disponíveis.

| Propriedade | Tipo | Descrição |
|-------------|------|-----------|
| **Nome** | `title` | Nome do meio (ex: "Cartão Nubank", "PIX") |
| **Tipo Forma de Pagamento** | `select` | Tipo (Crédito, Débito, PIX, etc.) |
| **ID** | `unique_id` | ID único |
| **Dia de Fechamento Fatura** | `number` | Dia do mês para fechamento |
| **Dia de Vencimento Fatura** | `number` | Dia do mês para vencimento |
| Intervalo entre Fechamento e Vencimento | `formula` | Dias entre fechamento e vencimento |

---

## Databases de Receitas

Estrutura espelhada das despesas, com nomenclatura adaptada:

### 1. Receitas - Transacoes
> Mesma estrutura de Despesas-Transacoes, com:
- `Receita` (title) em vez de `Despesa`
- `Categoria Receita` em vez de `Categoria Despesa`
- `Forma de Recebimento` em vez de `Forma de Pagamento`
- `Receitas - Parcelas` em vez de `Despesas - Parcelas`
- `Receita Este Mês` em vez de `Despesa Este Mês`

### 2. Categorias Receitas
> Mesma estrutura, com `Meta Mensal` em vez de `Orçamento Mensal` e `Atingimento` em vez de `Uso`.

| Propriedade | Tipo |
|-------------|------|
| Categoria Receita | `title` |
| Tipo Receita | `select` |
| Meta Mensal | `number` |
| Receitas Este Mês | `rollup` |
| Atingimento | `formula` |
| Receitas | `relation` |

### 3. Contas
> **Compartilhada** entre despesas e receitas (mesma database).

### 4. Receitas - Parcelas
> Mesma estrutura de Despesas-Parcelas, com relações adaptadas.

### 5. Receitas - Formas de Recebimento
> Mesma estrutura de Formas de Pagamento, com `Tipo Forma de Recebimento`.

---

## IDs das Databases por Tenant

### Controle Financeiro - Le (Pessoal)

| Database | Despesa | Receita |
|----------|---------|---------|
| Transacoes | `3089266e-edba-8188-b017-d54e1db2e290` | `3089266e-edba-8123-8339-e3a0e6dcdad8` |
| Categorias | `3089266e-edba-81b3-875f-c2b906f0c638` | `3089266e-edba-81ed-9d6a-e2b752d4d0ff` |
| Contas | `3089266e-edba-8112-ae5d-e2e206e46399` | (compartilhada) |
| Parcelas | `3089266e-edba-81aa-b579-f6309ca7f9a5` | `3089266e-edba-81be-a245-ddf475fe9569` |
| Formas Pgto | `3089266e-edba-81ab-a996-d804e166d85a` | `3089266e-edba-81e7-81e5-d88d0e752e02` |

### Verde Barro Cerâmica

| Database | Despesa | Receita |
|----------|---------|---------|
| Transacoes | `3099266e-edba-81f6-9811-c0a5ea87333f` | `3099266e-edba-8194-a520-d70f8fa7fd8e` |
| Categorias | `3099266e-edba-81f1-9cf5-c33a690514f0` | `3099266e-edba-81fc-a873-f72d30cb204b` |
| Contas | `3099266e-edba-813a-82d9-d4503ce55503` | (compartilhada) |
| Parcelas | `3099266e-edba-8185-8f61-e4d39bca874e` | `3099266e-edba-81ae-b1df-cf55427925d1` |
| Formas Pgto | `3099266e-edba-819d-b788-cd9f19881bb4` | `3099266e-edba-81e2-aaa6-d096da5edc84` |

### Leca - Controle Financeiro

| Database | Despesa | Receita |
|----------|---------|---------|
| Transacoes | `3099266e-edba-81d3-9d02-d12fff659519` | `3099266e-edba-81b8-9988-ca88e9474505` |
| Categorias | `3099266e-edba-8159-86b8-e4c7e97ad45b` | `3099266e-edba-81d9-9d8d-e684a937e345` |
| Contas | `3099266e-edba-8195-a75c-f418fac5176f` | (compartilhada) |
| Parcelas | `3099266e-edba-81d0-9018-f5f6aa8b1e85` | `3099266e-edba-81a2-88c6-ebd55d2a46a0` |
| Formas Pgto | `3099266e-edba-8122-969e-e8d1d5b4f098` | (ver workflow) |

---

## Relações entre Databases

```
┌─────────────────────┐
│    Transacoes        │
│  (Despesas/Receitas) │
├──────────────────────┤
│ Categoria ──────────── Categorias
│ Conta ──────────────── Contas
│ Forma Pagamento ────── Formas de Pagamento
│ Parcelas ───────────── Parcelas
└──────────────────────┘

┌─────────────────────┐         ┌──────────────────┐
│     Parcelas        │─────────│   Transacoes     │
├─────────────────────┤ relation├──────────────────┤
│ Transacao (rel)     │         │ Parcelas (rel)   │
│ Valor (parcela)     │         │ Valor (total)    │
│ Data Cobranca       │         │ Data             │
│ [rollups from parent]│        │ # Parcelas       │
└─────────────────────┘         └──────────────────┘
```
