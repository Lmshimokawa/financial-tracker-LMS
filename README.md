# Financial Tracker & Report - LMS

Sistema de controle financeiro pessoal e empresarial com frontend no **Telegram**, backend no **Notion** e automação via **n8n** com agentes de IA (OpenAI GPT).

## Arquitetura Atual

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────┐
│  Telegram    │────>│   n8n Workflow (v3)   │────>│   Notion    │
│  (Frontend)  │<────│   + AI Agents (GPT)   │<────│  (Backend)  │
└─────────────┘     └──────────────────────┘     └─────────────┘
                              │
                    ┌─────────┴──────────┐
                    │   QuickChart.io    │
                    │   (Gráficos)       │
                    └────────────────────┘
```

### Inputs Suportados (Telegram)
- **Texto**: Mensagens em linguagem natural (PT-BR)
- **Voz**: Áudios transcritos via OpenAI Whisper
- **Imagem**: Fotos de recibos/notas analisadas via GPT Vision
- **Documento**: PDF, CSV, XLSX, XLS (extração de conteúdo)

### Operações (CRUD + Relatórios)
| Operação | Descrição |
|----------|-----------|
| **Create** | Criar transações (despesa/receita) com parcelas automáticas |
| **Update** | Editar campos de transações existentes por ID |
| **Retrieve** | Consultar, filtrar, agrupar e agregar transações |
| **Delete** | Remover transações (e suas parcelas) por ID |
| **Reports** | Relatórios semanais e mensais automáticos com gráficos |

### Multi-Tenant
O sistema suporta múltiplos tenants (usuários/empresas), cada um com suas próprias databases no Notion e grupos no Telegram. A resolução do tenant é feita pelo `chat_id` do Telegram.

## Stack Tecnológica

| Componente | Tecnologia |
|------------|------------|
| Frontend | Telegram Bot API |
| Backend/DB | Notion API (2022-06-28 / 2025-09-03) |
| Automação | n8n (self-hosted) |
| AI/NLP | OpenAI GPT-4o (classificação, extração, NLU) |
| AI/STT | OpenAI Whisper (transcrição de áudio) |
| AI/Vision | OpenAI GPT-4o Vision (análise de imagens) |
| Gráficos | QuickChart.io |

## Estrutura do Repositório

```
financial-tracker-LMS/
├── README.md
├── docs/
│   ├── architecture.md          # Arquitetura detalhada do sistema
│   ├── notion-schema.md         # Schema das databases do Notion
│   ├── workflow-nodes.md        # Documentação dos nodes do workflow
│   ├── ai-agents.md             # Prompts e comportamento dos agentes IA
│   └── saas-plan.md             # Plano de transformação SaaS
├── workflow/
│   └── financial-tracker-v3.json # Export do workflow n8n
└── improvements/
    ├── document-parsing.md      # Melhoria: parsing inteligente de documentos
    ├── telegram-batching.md     # Melhoria: batching de mensagens longas
    └── idempotency.md           # Melhoria: idempotência com alertas de duplicatas
```

## Documentação

- [Arquitetura Detalhada](docs/architecture.md)
- [Schema Notion](docs/notion-schema.md)
- [Agentes de IA](docs/ai-agents.md)
- [Plano SaaS](docs/saas-plan.md)

## Tenants Atuais

| Tenant | Brand | Tipo |
|--------|-------|------|
| Controle Financeiro - Le | Controle Financeiro - Le | Pessoal |
| Despesas Verde Barro | Verde Barro Cerâmica | Empresa |
| Leca - Controle Financeiro | Lar Leca | Pessoal |
| default | Template Marca | Template |

---

> Projeto em evolução para se tornar um produto SaaS completo de controle financeiro.
