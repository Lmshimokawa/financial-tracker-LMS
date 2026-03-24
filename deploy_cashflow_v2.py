import json, sys, re, uuid, os, copy
sys.stdout.reconfigure(encoding='utf-8')

N8N_URL = "https://n8n.srv939759.hstgr.cloud"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Mjc0Nzg2Yi00NDVjLTRiNDctYWQwYS1kZWExMDY3YjE0MGMiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjU0MjVjYTUtYWZmZS00MDYzLTk1ZGUtNjc2ZDVkMGMxMzZlIiwiaWF0IjoxNzc0MjA3NTQ2fQ.utFwMa8f_u2Es5ZzfbkXrZnf4ODt_O3bp1FZBRvHnKI"

HOME = os.path.expanduser('~')
BASE = os.path.join(HOME, 'financial-tracker-LMS')

# ============================================================
# Load credential map from execution
# ============================================================
with open(os.path.join(BASE, 'cred_map.json'), 'r') as f:
    cred_map = json.load(f)

NOTION_CRED = {"notionApi": {"id": "uVaidIKSIwzbFrJb", "name": "Notion - n8n_pessoal"}}
TELEGRAM_CRED = {"telegramApi": {"id": "CCXLbVfovSxCD6sx", "name": "caderneta_lms_bot"}}

# ============================================================
# Fetch current production workflow
# ============================================================
import subprocess
result = subprocess.run([
    'curl', '-s', f'{N8N_URL}/api/v1/workflows/bE7b3g5hVB8VVCCU',
    '-H', f'X-N8N-API-KEY: {N8N_API_KEY}'
], capture_output=True, text=True, encoding='utf-8')
wf = json.loads(result.stdout)
nodes = wf['nodes']
conns = wf['connections']
print(f"Fetched workflow: {len(nodes)} nodes, active={wf['active']}")

# ============================================================
# STEP 1: Update Process All Data & Monthly Data code
# ============================================================
with open(os.path.join(BASE, 'process_all_data_v2.js'), 'r', encoding='utf-8') as f:
    pad_code = f.read()
with open(os.path.join(BASE, 'process_monthly_data_v2.js'), 'r', encoding='utf-8') as f:
    pmd_code = f.read()

for n in nodes:
    if n['name'] == 'Process All Data':
        n['parameters']['jsCode'] = pad_code
        print("Updated Process All Data")
    elif n['name'] == 'Process Monthly Data':
        n['parameters']['jsCode'] = pmd_code
        print("Updated Process Monthly Data")

# ============================================================
# STEP 2: Remove cash flow sections from Format nodes
# ============================================================
for n in nodes:
    if n['name'] in ('Format Weekly Summary', 'Format Monthly Summary'):
        code = n['parameters']['jsCode']
        # Remove everything between "// === FLUXO DE CAIXA" and the next section or return
        pattern = r'// === FLUXO DE CAIXA \(PARCELAS\) ===.*?(?=\nlines\.push|return \[)'
        code = re.sub(pattern, '', code, flags=re.DOTALL)
        n['parameters']['jsCode'] = code
        print(f"Cleaned cash flow from {n['name']}")

# ============================================================
# STEP 3: Update parcelas query to broader range (2 months back)
# ============================================================
for n in nodes:
    if n['name'] == 'Get Parcelas Cash Flow':
        n['parameters']['filterJson'] = "={{ (() => { const agora = new Date(); const hoje = new Date(agora.toLocaleString('en-US', { timeZone: 'America/Sao_Paulo' })); const inicio = new Date(hoje.getFullYear(), hoje.getMonth() - 2, 1); const fim = new Date(hoje.getFullYear(), hoje.getMonth() + 5, 0); const fmt = (d) => d.toISOString().split('T')[0]; return JSON.stringify({ and: [{ property: 'Data Cobranca', date: { on_or_after: fmt(inicio) } }, { property: 'Data Cobranca', date: { on_or_before: fmt(fim) } }] }); })() }}"
        print("Updated Get Parcelas Cash Flow filter (broader range)")
    elif n['name'] == 'Get Parcelas Cash Flow1':
        n['parameters']['filterJson'] = "={{ (() => { const agora = new Date(); const hoje = new Date(agora.toLocaleString('en-US', { timeZone: 'America/Sao_Paulo' })); const inicio = new Date(hoje.getFullYear(), hoje.getMonth() - 3, 1); const fim = new Date(hoje.getFullYear(), hoje.getMonth() + 4, 0); const fmt = (d) => d.toISOString().split('T')[0]; return JSON.stringify({ and: [{ property: 'Data Cobranca', date: { on_or_after: fmt(inicio) } }, { property: 'Data Cobranca', date: { on_or_before: fmt(fim) } }] }); })() }}"
        print("Updated Get Parcelas Cash Flow1 filter (broader range)")

# ============================================================
# STEP 4: Add new nodes for cash flow messages
# ============================================================

# --- FORMAT CASH FLOW (WEEKLY) ---
FORMAT_CF_WEEKLY_CODE = r"""const data = $('Process All Data').first().json;
const _brand = $('Set Report Config (Weekly)').first().json.brand_name;
const fmtBRL = (n) => `R$ ${Math.round(Number(n || 0)).toLocaleString('pt-BR')}`;
const fmtPct = (n) => `${Number(n || 0).toFixed(0)}%`;
const labels = data.mesesLabels;
const fr = data.fluxoRealizado;
const fc = data.fluxoComprometido;

const lines = [
  '\ud83c\udfe6 *' + _brand + '* \ud83c\udfe6',
  '',
  '\ud83d\udcb5 *FLUXO DE CAIXA*',
  '\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501',
  ''
];

// --- REALIZADO ---
lines.push('\ud83d\udcca *FLUXO REALIZADO (Vencimentos no m\u00eas)*');
lines.push(`   Total ${labels.mes0}: ${fmtBRL(fr.totalMesAtual)} (${fr.qtdMesAtual} parcelas)`);
lines.push('');

const difRealizado = fr.totalMesAtual - fr.totalMesAnteriorAteDia;
const pctDifRealizado = fr.totalMesAnteriorAteDia > 0 ? ((difRealizado / fr.totalMesAnteriorAteDia) * 100) : 0;

lines.push(`\ud83d\udcc5 *Comparativo vs ${labels.mes1}*`);
lines.push(`   (Acumulado at\u00e9 dia ${data.diaDoMes})`);
lines.push('');
lines.push(`   ${labels.mes0}: ${fmtBRL(fr.totalMesAtual)}`);
lines.push(`   ${labels.mes1} (at\u00e9 dia ${data.diaDoMes}): ${fmtBRL(fr.totalMesAnteriorAteDia)}`);
lines.push(`   ${labels.mes1} (total): ${fmtBRL(fr.totalMesAnteriorCompleto)}`);
lines.push('');

if (difRealizado < 0) {
  lines.push(`\u2705 *${fmtBRL(Math.abs(difRealizado))} abaixo do m\u00eas anterior*`);
  lines.push(`   \ud83d\udcc9 ${fmtPct(Math.abs(pctDifRealizado))} menor que ${labels.mes1}`);
} else if (difRealizado > 0) {
  lines.push(`\u26a0\ufe0f *${fmtBRL(difRealizado)} acima do m\u00eas anterior*`);
  lines.push(`   \ud83d\udcc8 ${fmtPct(pctDifRealizado)} maior que ${labels.mes1}`);
} else {
  lines.push(`\u27a1\ufe0f *Mesmo valor que ${labels.mes1}*`);
}

if (Object.keys(fr.porCategoria || {}).length > 0) {
  lines.push('');
  lines.push('   *Top categorias:*');
  Object.entries(fr.porCategoria)
    .sort((a, b) => b[1].total - a[1].total)
    .slice(0, 5)
    .forEach(([cat, info]) => {
      lines.push(`   \u2022 ${cat}: ${fmtBRL(info.total)} (${info.count} parc.)`);
    });
}

// --- COMPROMETIDO ---
if (fc && Object.keys(fc.meses || {}).length > 0) {
  lines.push('');
  lines.push('\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501');
  lines.push('');
  lines.push('\ud83d\udcb3 *FLUXO COMPROMETIDO NO CR\u00c9DITO*');
  lines.push(`   Total pr\u00f3ximos 4 meses: ${fmtBRL(fc.totalGeral)}`);
  lines.push('');

  Object.entries(fc.meses).forEach(([mes, info]) => {
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

lines.push('');
lines.push('\ud83d\udcf8 _Gr\u00e1fico abaixo..._');

return [{ json: { ...data, text: lines.join('\n') } }];
"""

# --- FORMAT CASH FLOW (MONTHLY) ---
FORMAT_CF_MONTHLY_CODE = r"""const data = $('Process Monthly Data').first().json;
const _brand = $('Set Report Config (Monthly)').first().json.brand_name;
const fmtBRL = (n) => `R$ ${Math.round(Number(n || 0)).toLocaleString('pt-BR')}`;
const fmtPct = (n) => `${Number(n || 0).toFixed(0)}%`;
const fr = data.fluxoRealizado;
const fc = data.fluxoComprometido;
const mesLabel = data.mesRelatorioCurto;
const mesAnteriorIdx = (new Date().getMonth() - 2 + 12) % 12;
const nomesMesesCurto = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
const mesAnteriorLabel = nomesMesesCurto[mesAnteriorIdx];

const lines = [
  '\ud83c\udfe6 *' + _brand + '* \ud83c\udfe6',
  '',
  '\ud83d\udcb5 *FLUXO DE CAIXA - ' + data.mesRelatorio.toUpperCase() + ' ' + data.anoRelatorio + '*',
  '\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501',
  ''
];

lines.push('\ud83d\udcca *FLUXO REALIZADO (Vencimentos no m\u00eas)*');
lines.push(`   Total ${mesLabel}: ${fmtBRL(fr.totalMesReport)} (${fr.qtdMesReport} parcelas)`);
lines.push(`   Total ${mesAnteriorLabel}: ${fmtBRL(fr.totalMesAnterior)} (${fr.qtdMesAnterior} parcelas)`);
lines.push('');

const difRealizado = fr.totalMesReport - fr.totalMesAnterior;
const pctDifRealizado = fr.totalMesAnterior > 0 ? ((difRealizado / fr.totalMesAnterior) * 100) : 0;

if (difRealizado < 0) {
  lines.push(`\u2705 *${fmtBRL(Math.abs(difRealizado))} abaixo do m\u00eas anterior*`);
  lines.push(`   \ud83d\udcc9 ${fmtPct(Math.abs(pctDifRealizado))} menor`);
} else if (difRealizado > 0) {
  lines.push(`\u26a0\ufe0f *${fmtBRL(difRealizado)} acima do m\u00eas anterior*`);
  lines.push(`   \ud83d\udcc8 ${fmtPct(pctDifRealizado)} maior`);
} else {
  lines.push(`\u27a1\ufe0f *Mesmo valor que ${mesAnteriorLabel}*`);
}

if (Object.keys(fr.porCategoria || {}).length > 0) {
  lines.push('');
  lines.push('   *Top categorias:*');
  Object.entries(fr.porCategoria)
    .sort((a, b) => b[1].total - a[1].total)
    .slice(0, 7)
    .forEach(([cat, info]) => {
      lines.push(`   \u2022 ${cat}: ${fmtBRL(info.total)} (${info.count} parc.)`);
    });
}

if (fc && Object.keys(fc.meses || {}).length > 0) {
  lines.push('');
  lines.push('\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501');
  lines.push('');
  lines.push('\ud83d\udcb3 *FLUXO COMPROMETIDO NO CR\u00c9DITO*');
  lines.push(`   Total: ${fmtBRL(fc.totalGeral)}`);
  lines.push('');

  Object.entries(fc.meses).forEach(([mes, info]) => {
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

lines.push('');
lines.push('\ud83d\udcf8 _Gr\u00e1fico abaixo..._');

return [{ json: { ...data, text: lines.join('\n') } }];
"""

# --- PREPARE CASH FLOW CHART (shared logic, reads from Format Cash Flow node) ---
PREPARE_CF_CHART_WEEKLY_CODE = r"""const data = $('Format Cash Flow (Weekly)').first().json;
const fc = data.fluxoComprometido;

const datasets = [];
Object.entries(fc.chartDatasets || {}).forEach(([cartao, info]) => {
  datasets.push({
    label: cartao.replace('Cartao Credito ', ''),
    data: info.data,
    backgroundColor: info.color + 'CC',
    borderColor: info.color,
    borderWidth: 1
  });
});

const chartConfig = {
  type: 'bar',
  data: {
    labels: fc.chartLabels || [],
    datasets
  },
  options: {
    responsive: true,
    plugins: {
      title: {
        display: true,
        text: 'Fluxo Comprometido - Credito (Proximos 4 Meses)',
        font: { size: 14, weight: 'bold' }
      },
      legend: { position: 'top', labels: { usePointStyle: true, padding: 10, font: { size: 10 } } }
    },
    scales: {
      x: { stacked: true, grid: { display: false } },
      y: { stacked: true, beginAtZero: true, title: { display: true, text: 'R$', font: { size: 10 } }, grid: { color: 'rgba(0,0,0,0.05)' } }
    }
  }
};

const chartJson = encodeURIComponent(JSON.stringify(chartConfig));
const chartUrl = `https://quickchart.io/chart?c=${chartJson}&w=750&h=420&bkg=white`;

return [{ json: { chartUrl, chartConfig } }];
"""

PREPARE_CF_CHART_MONTHLY_CODE = PREPARE_CF_CHART_WEEKLY_CODE.replace(
    "Format Cash Flow (Weekly)", "Format Cash Flow (Monthly)"
)

# Batch code (reuse the same batcher)
BATCH_CODE = None
for n in nodes:
    if n['name'] == 'Batch - Weekly Summary':
        BATCH_CODE = n['parameters']['jsCode']
        break

# ---- Create node definitions ----
# Position: after Send Comparison Chart [78080, 45104] for weekly
# Position: after Send Category Pie [78080, 46672] for monthly

new_nodes = [
    # WEEKLY CHAIN
    {"name": "Format Cash Flow (Weekly)", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [78320, 44880],
     "parameters": {"jsCode": FORMAT_CF_WEEKLY_CODE, "mode": "runOnceForAllItems"}},

    {"name": "Batch Cash Flow (Weekly)", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [78560, 44880],
     "parameters": {"jsCode": BATCH_CODE, "mode": "runOnceForAllItems"}},

    {"name": "Send Cash Flow (Weekly)", "type": "n8n-nodes-base.telegram", "typeVersion": 1.2, "position": [78800, 44880],
     "credentials": TELEGRAM_CRED,
     "parameters": {"chatId": "={{ $('Set Report Config (Weekly)').first().json.telegram_chat_id }}", "text": "={{ $json.text }}", "additionalFields": {"appendAttribution": False, "parse_mode": "Markdown"}}},

    {"name": "Prepare CF Chart (Weekly)", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [79040, 44880],
     "parameters": {"jsCode": PREPARE_CF_CHART_WEEKLY_CODE, "mode": "runOnceForAllItems"}},

    {"name": "Generate CF Chart (Weekly)", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [79280, 44880],
     "parameters": {"url": "={{ $json.chartUrl }}", "options": {"response": {"response": {"responseFormat": "file"}}}}},

    {"name": "Send CF Chart (Weekly)", "type": "n8n-nodes-base.telegram", "typeVersion": 1.2, "position": [79520, 44880],
     "credentials": TELEGRAM_CRED,
     "parameters": {"operation": "sendPhoto", "chatId": "={{ $('Set Report Config (Weekly)').first().json.telegram_chat_id }}", "additionalFields": {"fileName": "Fluxo Comprometido Credito"}}},

    # MONTHLY CHAIN
    {"name": "Format Cash Flow (Monthly)", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [78320, 46448],
     "parameters": {"jsCode": FORMAT_CF_MONTHLY_CODE, "mode": "runOnceForAllItems"}},

    {"name": "Batch Cash Flow (Monthly)", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [78560, 46448],
     "parameters": {"jsCode": BATCH_CODE, "mode": "runOnceForAllItems"}},

    {"name": "Send Cash Flow (Monthly)", "type": "n8n-nodes-base.telegram", "typeVersion": 1.2, "position": [78800, 46448],
     "credentials": TELEGRAM_CRED,
     "parameters": {"chatId": "={{ $('Set Report Config (Monthly)').first().json.telegram_chat_id }}", "text": "={{ $json.text }}", "additionalFields": {"appendAttribution": False, "parse_mode": "Markdown"}}},

    {"name": "Prepare CF Chart (Monthly)", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [79040, 46448],
     "parameters": {"jsCode": PREPARE_CF_CHART_MONTHLY_CODE, "mode": "runOnceForAllItems"}},

    {"name": "Generate CF Chart (Monthly)", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [79280, 46448],
     "parameters": {"url": "={{ $json.chartUrl }}", "options": {"response": {"response": {"responseFormat": "file"}}}}},

    {"name": "Send CF Chart (Monthly)", "type": "n8n-nodes-base.telegram", "typeVersion": 1.2, "position": [79520, 46448],
     "credentials": TELEGRAM_CRED,
     "parameters": {"operation": "sendPhoto", "chatId": "={{ $('Set Report Config (Monthly)').first().json.telegram_chat_id }}", "additionalFields": {"fileName": "Fluxo Comprometido Credito"}}},
]

# Check for duplicates and add
existing_names = {n['name'] for n in nodes}
added = 0
for nn in new_nodes:
    if nn['name'] not in existing_names:
        nn['id'] = str(uuid.uuid4())
        nodes.append(nn)
        added += 1
    else:
        # Update existing node
        for n in nodes:
            if n['name'] == nn['name']:
                n['parameters'] = nn['parameters']
                if nn.get('credentials'):
                    n['credentials'] = nn['credentials']
                break
        print(f"Updated existing node: {nn['name']}")

print(f"Added {added} new nodes. Total: {len(nodes)}")

# ============================================================
# STEP 5: Rewire connections
# ============================================================

# WEEKLY: Send Comparison Chart -> Format Cash Flow (Weekly) [instead of -> Loop Reports (Weekly)]
conns['Send Comparison Chart'] = {"main": [[{"node": "Format Cash Flow (Weekly)", "type": "main", "index": 0}]]}
conns['Format Cash Flow (Weekly)'] = {"main": [[{"node": "Batch Cash Flow (Weekly)", "type": "main", "index": 0}]]}
conns['Batch Cash Flow (Weekly)'] = {"main": [[{"node": "Send Cash Flow (Weekly)", "type": "main", "index": 0}]]}
conns['Send Cash Flow (Weekly)'] = {"main": [[{"node": "Prepare CF Chart (Weekly)", "type": "main", "index": 0}]]}
conns['Prepare CF Chart (Weekly)'] = {"main": [[{"node": "Generate CF Chart (Weekly)", "type": "main", "index": 0}]]}
conns['Generate CF Chart (Weekly)'] = {"main": [[{"node": "Send CF Chart (Weekly)", "type": "main", "index": 0}]]}
conns['Send CF Chart (Weekly)'] = {"main": [[{"node": "Loop Reports (Weekly)", "type": "main", "index": 0}]]}

# MONTHLY: Send Category Pie -> Format Cash Flow (Monthly) [instead of -> Loop Reports (Monthly)]
conns['Send Category Pie'] = {"main": [[{"node": "Format Cash Flow (Monthly)", "type": "main", "index": 0}]]}
conns['Format Cash Flow (Monthly)'] = {"main": [[{"node": "Batch Cash Flow (Monthly)", "type": "main", "index": 0}]]}
conns['Batch Cash Flow (Monthly)'] = {"main": [[{"node": "Send Cash Flow (Monthly)", "type": "main", "index": 0}]]}
conns['Send Cash Flow (Monthly)'] = {"main": [[{"node": "Prepare CF Chart (Monthly)", "type": "main", "index": 0}]]}
conns['Prepare CF Chart (Monthly)'] = {"main": [[{"node": "Generate CF Chart (Monthly)", "type": "main", "index": 0}]]}
conns['Generate CF Chart (Monthly)'] = {"main": [[{"node": "Send CF Chart (Monthly)", "type": "main", "index": 0}]]}
conns['Send CF Chart (Monthly)'] = {"main": [[{"node": "Loop Reports (Monthly)", "type": "main", "index": 0}]]}

print("Connections wired")

# ============================================================
# STEP 6: Apply credentials
# ============================================================
for n in nodes:
    name = n['name']
    if name in cred_map:
        n['credentials'] = cred_map[name]
    # New nodes already have credentials set above
    # Nodes without credentials don't need them (code, merge, etc.)

print("Credentials applied")

# ============================================================
# STEP 7: Clean and save
# ============================================================
valid_settings = ['executionOrder', 'timezone', 'saveExecutionProgress', 'callerPolicy', 'executionTimeout']
clean_settings = {k: v for k, v in wf.get('settings', {}).items() if k in valid_settings}

deploy = {
    'name': wf['name'],
    'nodes': nodes,
    'connections': conns,
    'settings': clean_settings
}

deploy_path = os.path.join(BASE, 'workflow_v3_deploy_cf.json')
with open(deploy_path, 'w', encoding='utf-8') as f:
    json.dump(deploy, f, ensure_ascii=False)

print(f"Saved deploy file: {len(nodes)} nodes")

# ============================================================
# STEP 8: Deploy
# ============================================================
result = subprocess.run([
    'curl', '-s', '-o', os.path.join(BASE, 'put_cf_result.json'), '-w', '%{http_code}',
    '-X', 'PUT',
    f'{N8N_URL}/api/v1/workflows/bE7b3g5hVB8VVCCU',
    '-H', f'X-N8N-API-KEY: {N8N_API_KEY}',
    '-H', 'Content-Type: application/json',
    '-d', f'@{deploy_path}'
], capture_output=True, text=True, encoding='utf-8')
http_code = result.stdout.strip()
print(f"PUT Status: {http_code}")

with open(os.path.join(BASE, 'put_cf_result.json'), 'r', encoding='utf-8') as f:
    put_result = json.load(f)

if 'nodes' in put_result:
    print(f"OK: {put_result['name']} | {len(put_result['nodes'])} nodes | active={put_result['active']}")
else:
    print(f"Error: {json.dumps(put_result, indent=2)[:500]}")
    sys.exit(1)

# ============================================================
# STEP 9: Activate
# ============================================================
result = subprocess.run([
    'curl', '-s', '-o', os.path.join(BASE, 'activate_cf_result.json'), '-w', '%{http_code}',
    '-X', 'POST',
    f'{N8N_URL}/api/v1/workflows/bE7b3g5hVB8VVCCU/activate',
    '-H', f'X-N8N-API-KEY: {N8N_API_KEY}'
], capture_output=True, text=True, encoding='utf-8')
http_code = result.stdout.strip()
print(f"Activate Status: {http_code}")

with open(os.path.join(BASE, 'activate_cf_result.json'), 'r', encoding='utf-8') as f:
    act_result = json.load(f)

if act_result.get('active'):
    print(f"SUCCESS! Workflow active={act_result['active']} | {len(act_result.get('nodes', []))} nodes")
else:
    print(f"Activation result: {json.dumps(act_result, indent=2)[:500]}")
