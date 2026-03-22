# Plano de Transformação SaaS - Financial Tracker LMS

## Sumário Executivo

Transformar o workflow pessoal de controle financeiro (Telegram + Notion + n8n) em um produto SaaS completo, escalável e comercializável. O produto permite que qualquer pessoa ou empresa gerencie suas finanças pessoais/empresariais conversando em linguagem natural via Telegram, com dados armazenados no Notion e relatórios automáticos.

---

## Fase 0: Fundação (Pré-SaaS)

### 0.1 Melhorias no Workflow Atual (Sprint Atual)
- [x] Documentação completa da arquitetura
- [ ] Smart Document Parsing (PDF, CSV, XLSX, XLS)
- [ ] Telegram Message Batching (respeitar limite 4096 chars)
- [ ] Idempotência com alertas de duplicatas

### 0.2 Estabilização Técnica
- [ ] **Testes end-to-end automatizados**: Criar suite de testes que simula mensagens Telegram e valida respostas/criações no Notion
- [ ] **Monitoramento de erros**: Integrar Sentry ou similar para capturar falhas nos nodes
- [ ] **Logging estruturado**: Adicionar logs em cada etapa crítica do workflow
- [ ] **Rate limiting**: Proteger contra flood de mensagens no Telegram
- [ ] **Backup de dados**: Rotina de export das databases Notion

---

## Fase 1: Produto Mínimo Viável (MVP SaaS)

### 1.1 Infraestrutura Multi-Tenant Robusta

**Problema atual**: Tenants são hardcoded no código JavaScript dos nodes `Resolve Tenant Config` e `Build Tenant List`. Cada novo tenant exige edição manual do workflow.

**Solução**:
| Componente | Atual | SaaS |
|------------|-------|------|
| Registro de tenants | Hardcoded em JS | Database dedicada (Supabase/PostgreSQL) |
| Onboarding | Manual | Self-service via Telegram bot |
| Config de databases | Copy-paste de IDs | Automático via Notion API (template duplication) |
| Gestão de assinaturas | Inexistente | Stripe Billing |

**Ações**:
- [ ] Criar database `tenants` no Supabase com campos: id, brand_name, timezone, telegram_chat_ids, notion_database_ids, stripe_customer_id, plan, status, created_at
- [ ] Criar database `tenant_databases` para mapear database_ids do Notion por tenant e flow_type
- [ ] Refatorar `Resolve Tenant Config` para consultar Supabase em vez de JSON hardcoded
- [ ] Criar workflow de onboarding automatizado

### 1.2 Onboarding Self-Service

**Fluxo proposto**:
```
1. Usuário acessa landing page → Clica "Começar Grátis"
2. Redirect para Telegram → Inicia conversa com o bot
3. Bot pede:
   a. Nome do espaço (brand_name)
   b. Timezone
   c. Autorização Notion (OAuth2) → Bot cria databases automaticamente
4. Bot cria:
   - Template das 10 databases no Notion do usuário
   - Grupo Telegram para despesas
   - Grupo Telegram para receitas
   - Registro no Supabase
5. Mensagem de boas-vindas com tutorial interativo
```

**Ações**:
- [ ] Implementar Notion OAuth2 flow (em vez de API key fixa)
- [ ] Criar template duplicator: endpoint que copia as 10 databases template para o workspace do novo usuário
- [ ] Criar workflow n8n de onboarding
- [ ] Desenvolver tutorial interativo no Telegram (walkthrough guiado)

### 1.3 Sistema de Planos e Billing

**Planos propostos**:

| Feature | Free | Pro (R$29/mês) | Business (R$79/mês) |
|---------|------|----------------|---------------------|
| Transações/mês | 50 | Ilimitado | Ilimitado |
| Categorias | 5 | Ilimitado | Ilimitado |
| Contas | 2 | 10 | Ilimitado |
| Relatório semanal | Texto simples | Com gráficos | Com gráficos |
| Relatório mensal | - | Com gráficos | Com gráficos + comparativo |
| Documentos (PDF/XLSX) | - | 10/mês | Ilimitado |
| Parcelas | Até 3x | Ilimitado | Ilimitado |
| Múltiplos flow_types | Só despesas | Despesas + Receitas | Despesas + Receitas |
| Suporte | Community | Email | Prioritário |
| API access | - | - | REST API |
| Multi-usuário | - | - | Até 5 usuários |

**Ações**:
- [ ] Configurar Stripe Products/Prices para cada plano
- [ ] Criar workflow n8n para checkout via Telegram (Payment Link do Stripe)
- [ ] Implementar middleware de verificação de limites (antes de cada operação)
- [ ] Webhook Stripe → n8n para atualizar status de assinatura no Supabase
- [ ] Implementar grace period (3 dias) e downgrade automático

### 1.4 Landing Page e Funil de Venda

**Stack sugerida**: Next.js + Vercel (ou Astro para performance)

**Estrutura da landing page**:
```
├── Hero: "Controle suas finanças conversando no Telegram"
│   └── CTA: "Comece grátis" → Link Telegram
├── Demo: GIF/vídeo mostrando conversa no Telegram
├── Features: Cards com cada funcionalidade
├── Pricing: Tabela de planos
├── Testimonials: Depoimentos (iniciar com beta testers)
├── FAQ: Perguntas frequentes
└── Footer: Links, termos, privacidade
```

**Funil**:
```
Awareness → Landing Page (SEO, ads, content marketing)
    │
Interest → Demo interativa / Vídeo tutorial
    │
Decision → Planos e preços / Free tier
    │
Action → "Comece grátis" → Telegram Bot → Onboarding
    │
Retention → Relatórios automáticos / Insights / Notificações
    │
Expansion → Upgrade para Pro/Business
    │
Referral → "Convide um amigo" (desconto mútuo)
```

**Ações**:
- [ ] Desenvolver landing page responsiva
- [ ] Configurar domínio e SSL
- [ ] Implementar analytics (Plausible ou GA4)
- [ ] Criar sequência de emails de onboarding (se coletar email)
- [ ] Configurar Google Ads / Meta Ads para teste inicial

---

## Fase 2: Crescimento e Retenção

### 2.1 Features Adicionais para Retenção

| Feature | Prioridade | Complexidade | Descrição |
|---------|-----------|-------------|-----------|
| **Metas financeiras** | Alta | Média | Definir metas de economia/receita com tracking visual |
| **Alertas inteligentes** | Alta | Baixa | "Você já gastou 80% do orçamento de Alimentação" |
| **Recorrências** | Alta | Média | Transações automáticas (aluguel, salário, assinaturas) |
| **Dashboard web** | Média | Alta | Visualização web com gráficos interativos (além do Telegram) |
| **Export de dados** | Média | Baixa | Export CSV/PDF dos relatórios |
| **Compartilhamento** | Média | Média | Compartilhar acesso com cônjuge/sócio |
| **Integração bancária** | Alta | Alta | Open Finance para importação automática |
| **Categorização automática** | Alta | Média | AI aprende padrões do usuário |
| **Previsão de gastos** | Média | Alta | ML para prever gastos futuros |
| **Notas fiscais** | Baixa | Alta | OCR de notas fiscais / cupons |

### 2.2 Métricas e Analytics do Produto

**KPIs principais**:
- **MRR** (Monthly Recurring Revenue)
- **Churn rate** (mensal e anual)
- **CAC** (Customer Acquisition Cost)
- **LTV** (Lifetime Value)
- **DAU/MAU** (usuários ativos)
- **Transações/usuário/mês** (engajamento)
- **Conversion rate** (Free → Pro)
- **NPS** (Net Promoter Score)

**Ações**:
- [ ] Implementar event tracking no workflow (transação criada, relatório enviado, etc.)
- [ ] Dashboard de métricas do produto (Metabase ou Supabase Dashboard)
- [ ] Alertas de churn risk (usuário inativo por >7 dias)
- [ ] Pesquisa NPS mensal via Telegram

### 2.3 Content Marketing e SEO

**Estratégia de conteúdo**:
- Blog com artigos sobre finanças pessoais e organização financeira
- Tutoriais de uso do produto
- Templates Notion compartilháveis (lead magnet)
- Presença em comunidades Notion, Telegram e finanças pessoais
- YouTube: "Como organizei minhas finanças em 5 minutos por dia"

---

## Fase 3: Escalabilidade Técnica

### 3.1 Migração de Infraestrutura

**Problema**: n8n self-hosted + Notion como banco de dados não escala para milhares de usuários.

**Plano de migração progressiva**:

| Componente | Fase 1 (0-500 users) | Fase 2 (500-5K) | Fase 3 (5K+) |
|------------|----------------------|-----------------|--------------|
| **Automação** | n8n Cloud (Pro) | n8n Enterprise / Custom workers | Microservices (Node.js/Python) |
| **Database** | Notion API | Supabase (PostgreSQL) + Notion sync | Supabase full (Notion optional) |
| **AI/NLP** | OpenAI API | OpenAI + cache de intents | Fine-tuned model + OpenAI fallback |
| **Hosting** | Vercel (landing) | Vercel + Railway/Fly.io | AWS/GCP (ECS/Cloud Run) |
| **Queue** | n8n built-in | Redis + BullMQ | SQS/Cloud Tasks |
| **Cache** | Nenhum | Redis (categorias, contas) | Redis Cluster |
| **Monitoring** | Basic (n8n logs) | Sentry + Grafana | Full observability stack |

### 3.2 Performance e Otimização

**Gargalos atuais e soluções**:

| Gargalo | Impacto | Solução |
|---------|---------|---------|
| Notion API latency (~300ms/req) | Lentidão em queries complexas | Cache Redis de categorias/contas (TTL 5min) |
| OpenAI API latency (~2-5s) | Tempo de resposta ao usuário | Classificação local para intents simples |
| n8n single-threaded | Limite de concorrência | Workers paralelos / queue system |
| Notion 3 req/s rate limit | Bottleneck em bulk operations | Request batching + retry with backoff |
| Workflow complexity (190 nodes) | Manutenção difícil | Modularizar em sub-workflows |

### 3.3 Segurança e Compliance

- [ ] **LGPD Compliance**: Política de privacidade, consent management, data deletion workflow
- [ ] **Criptografia**: Dados sensíveis criptografados at-rest no Supabase
- [ ] **Audit log**: Registro de todas as operações por tenant
- [ ] **Token rotation**: Notion API tokens com rotação automática
- [ ] **2FA**: Autenticação de dois fatores para acesso administrativo
- [ ] **Penetration testing**: Teste de segurança antes do lançamento público
- [ ] **Backup automatizado**: Backup diário das databases com retenção de 30 dias
- [ ] **DPA** (Data Processing Agreement): Para clientes business

---

## Fase 4: Expansão e Monetização Avançada

### 4.1 Marketplace de Integrações

| Integração | Tipo | Prioridade |
|------------|------|-----------|
| **Open Finance (Brasil)** | Import automático de extrato | Alta |
| **Nubank / Inter / C6** | Integração direta via API | Alta |
| **Google Sheets** | Export/sync bidirecional | Média |
| **WhatsApp** | Frontend alternativo (além do Telegram) | Alta |
| **Slack** | Para times/empresas | Média |
| **Contabilidade** | Export para ContaAzul, Omie, etc. | Baixa |
| **Pix automático** | Detecção de Pix recebidos | Média |

### 4.2 API Pública (Plano Business)

```
REST API:
  POST /api/v1/transactions      → Criar transação
  GET  /api/v1/transactions      → Listar/filtrar transações
  PUT  /api/v1/transactions/:id  → Atualizar transação
  DELETE /api/v1/transactions/:id → Deletar transação
  GET  /api/v1/reports/weekly    → Relatório semanal
  GET  /api/v1/reports/monthly   → Relatório mensal
  GET  /api/v1/categories        → Listar categorias
  GET  /api/v1/accounts          → Listar contas
```

### 4.3 White-Label

Oferecer o produto como white-label para:
- Escritórios de contabilidade
- Consultores financeiros
- Fintechs que querem adicionar controle financeiro

---

## Roadmap de Implementação

### Q2 2026 (Abr-Jun): MVP

| Semana | Entrega |
|--------|---------|
| S1-S2 | Melhorias no workflow (document parsing, batching, idempotência) |
| S3-S4 | Supabase setup + migração de tenant config |
| S5-S6 | Onboarding self-service via Telegram |
| S7-S8 | Stripe integration (billing) |
| S9-S10 | Landing page + funil básico |
| S11-S12 | Beta fechado (10-20 usuários) + ajustes |

### Q3 2026 (Jul-Set): Lançamento

| Semana | Entrega |
|--------|---------|
| S1-S2 | Correções do beta + polimento UX |
| S3-S4 | Lançamento público (free tier) |
| S5-S6 | Content marketing + SEO inicial |
| S7-S8 | Features de retenção (metas, alertas, recorrências) |
| S9-S10 | Dashboard web (MVP) |
| S11-S12 | Métricas e analytics do produto |

### Q4 2026 (Out-Dez): Crescimento

| Semana | Entrega |
|--------|---------|
| S1-S4 | Integração Open Finance / Nubank |
| S5-S8 | Escalabilidade (cache, workers, monitoring) |
| S9-S12 | API pública + plano Business |

### Q1 2027: Expansão

- WhatsApp como frontend alternativo
- White-label para contadores/fintechs
- Internacionalização (ES, EN)
- Aplicativo mobile companion

---

## Estimativa de Custos Operacionais (por mês)

### Fase MVP (0-100 users)

| Serviço | Custo Estimado |
|---------|---------------|
| n8n Cloud (Pro) | $50/mês |
| OpenAI API | ~$30/mês (gpt-4o-mini para classificação) |
| Supabase (Free/Pro) | $0-25/mês |
| Vercel (Hobby/Pro) | $0-20/mês |
| Domínio + SSL | ~$15/ano |
| Stripe (fees) | 3.49% + R$0.39 por transação |
| **Total** | **~$100-125/mês** |

### Fase Crescimento (100-1000 users)

| Serviço | Custo Estimado |
|---------|---------------|
| n8n Cloud (Enterprise) ou self-hosted | $100-300/mês |
| OpenAI API | ~$150-400/mês |
| Supabase (Pro) | $25-75/mês |
| Redis (Upstash) | $10-30/mês |
| Vercel (Pro) | $20/mês |
| Monitoring (Sentry) | $26/mês |
| **Total** | **~$350-850/mês** |

### Break-even Analysis

| Cenário | Usuários pagantes | MRR | Custos | Lucro |
|---------|-------------------|-----|--------|-------|
| Conservador | 50 Pro | R$1.450 | R$700 | R$750 |
| Moderado | 100 Pro + 10 Business | R$3.690 | R$1.500 | R$2.190 |
| Otimista | 300 Pro + 30 Business | R$11.070 | R$3.500 | R$7.570 |

**Break-even estimado**: ~25 assinantes Pro (com custos de Fase MVP).

---

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Notion API rate limits | Alta | Alto | Cache agressivo + migração gradual para Supabase |
| OpenAI custos escalando | Média | Médio | Fine-tuning, cache de intents, modelos menores para tarefas simples |
| Telegram policy changes | Baixa | Alto | Preparar WhatsApp como fallback |
| Churn alto | Média | Alto | Onboarding robusto, notificações de engajamento, features de retenção |
| Concorrência (Organizze, Mobills) | Alta | Médio | Diferencial: NLP conversacional via Telegram (sem app para instalar) |
| LGPD compliance | Média | Alto | Consultoria jurídica, DPO, privacy by design |
| Dependência de terceiros (Notion, OpenAI) | Média | Alto | Abstrações que permitem trocar providers |

---

## Diferencial Competitivo

1. **Zero fricção**: Não precisa instalar app. Usa o Telegram que o usuário já tem.
2. **Linguagem natural**: Não precisa preencher formulários. Fala como falaria com um amigo.
3. **Multi-input**: Texto, voz, foto de recibo, documento - tudo funciona.
4. **Notion como backend**: Usuário pode visualizar/editar dados diretamente no Notion.
5. **Relatórios proativos**: Não precisa pedir - recebe resumos automáticos.
6. **Multi-tenant nativo**: Controle pessoal e empresarial no mesmo produto.
7. **AI-first**: Cada interação é processada por IA, melhorando com o tempo.

---

## Próximos Passos Imediatos

1. **Completar melhorias atuais** (document parsing, batching, idempotência)
2. **Configurar Supabase** (database de tenants)
3. **Refatorar Resolve Tenant Config** para consultar Supabase
4. **Criar workflow de onboarding** (Telegram → Notion template → Supabase)
5. **Configurar Stripe** (produtos, preços, checkout flow)
6. **Desenvolver landing page** (Next.js + Vercel)
7. **Recrutar 10-20 beta testers** (amigos, comunidades de finanças pessoais)
