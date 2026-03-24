import json, sys, glob, os, uuid
sys.stdout.reconfigure(encoding='utf-8')

files = glob.glob(os.path.expanduser('~') + '/.claude/projects/C--Users-leand/*/tool-results/mcp-31687870*-1774318359626.txt')
filepath = files[0]

with open(filepath, 'r', encoding='utf-8') as f:
    data = json.load(f)

wf = data['workflow']
nodes = wf['nodes']
conns = wf['connections']

# ============================================================
# STEP 1: Add new Notion query nodes
# ============================================================

nodes.append({
    "parameters": {
        "resource": "databasePage", "operation": "getAll",
        "databaseId": {"__rl": True, "value": "={{ $('Set Report Config (Weekly)').first().json.database_id_formas_pagamento }}", "mode": "id"},
        "returnAll": True, "simple": False, "options": {}
    },
    "type": "n8n-nodes-base.notion", "typeVersion": 2.2,
    "position": [76752, 44600], "id": str(uuid.uuid4()),
    "name": "Get Formas Pagamento",
    "credentials": {"notionApi": {"id": "nGmTrik8pKBynxhb", "name": "Notion API - Financial Tracker"}}
})

nodes.append({
    "parameters": {
        "resource": "databasePage", "operation": "getAll",
        "databaseId": {"__rl": True, "value": "={{ $('Set Report Config (Weekly)').first().json.database_id_parcelas }}", "mode": "id"},
        "returnAll": True, "simple": False, "filterType": "json",
        "filterJson": "={{ (() => { const agora = new Date(); const hoje = new Date(agora.toLocaleString('en-US', { timeZone: 'America/Sao_Paulo' })); const primeiroDia = new Date(hoje.getFullYear(), hoje.getMonth(), 1); const fim3Meses = new Date(hoje.getFullYear(), hoje.getMonth() + 4, 0); const fmt = (d) => d.toISOString().split('T')[0]; return JSON.stringify({ and: [{ property: 'Data Cobranca', date: { on_or_after: fmt(primeiroDia) } }, { property: 'Data Cobranca', date: { on_or_before: fmt(fim3Meses) } }] }); })() }}",
        "options": {}
    },
    "type": "n8n-nodes-base.notion", "typeVersion": 2.2,
    "position": [76752, 44400], "id": str(uuid.uuid4()),
    "name": "Get Parcelas Cash Flow",
    "credentials": {"notionApi": {"id": "nGmTrik8pKBynxhb", "name": "Notion API - Financial Tracker"}}
})

nodes.append({
    "parameters": {
        "resource": "databasePage", "operation": "getAll",
        "databaseId": {"__rl": True, "value": "={{ $('Set Report Config (Monthly)').first().json.database_id_formas_pagamento }}", "mode": "id"},
        "returnAll": True, "simple": False, "options": {}
    },
    "type": "n8n-nodes-base.notion", "typeVersion": 2.2,
    "position": [76752, 45848], "id": str(uuid.uuid4()),
    "name": "Get Formas Pagamento1",
    "credentials": {"notionApi": {"id": "nGmTrik8pKBynxhb", "name": "Notion API - Financial Tracker"}}
})

nodes.append({
    "parameters": {
        "resource": "databasePage", "operation": "getAll",
        "databaseId": {"__rl": True, "value": "={{ $('Set Report Config (Monthly)').first().json.database_id_parcelas }}", "mode": "id"},
        "returnAll": True, "simple": False, "filterType": "json",
        "filterJson": "={{ (() => { const agora = new Date(); const hoje = new Date(agora.toLocaleString('en-US', { timeZone: 'America/Sao_Paulo' })); const primeiroDia = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1); const fim3Meses = new Date(hoje.getFullYear(), hoje.getMonth() + 3, 0); const fmt = (d) => d.toISOString().split('T')[0]; return JSON.stringify({ and: [{ property: 'Data Cobranca', date: { on_or_after: fmt(primeiroDia) } }, { property: 'Data Cobranca', date: { on_or_before: fmt(fim3Meses) } }] }); })() }}",
        "options": {}
    },
    "type": "n8n-nodes-base.notion", "typeVersion": 2.2,
    "position": [76752, 45648], "id": str(uuid.uuid4()),
    "name": "Get Parcelas Cash Flow1",
    "credentials": {"notionApi": {"id": "nGmTrik8pKBynxhb", "name": "Notion API - Financial Tracker"}}
})

print(f"Added 4 new nodes. Total: {len(nodes)}")

# ============================================================
# STEP 2: Update Merge nodes
# ============================================================
for n in nodes:
    if n['name'] == 'Merge':
        n['parameters']['numberInputs'] = 8
    elif n['name'] == 'Merge1':
        n['parameters']['numberInputs'] = 8

# ============================================================
# STEP 3: Wire connections
# ============================================================
conns['Set Report Config (Weekly)']['main'][0].append({"node": "Get Formas Pagamento", "type": "main", "index": 0})
conns['Set Report Config (Weekly)']['main'][0].append({"node": "Get Parcelas Cash Flow", "type": "main", "index": 0})
conns['Get Formas Pagamento'] = {"main": [[{"node": "Merge", "type": "main", "index": 6}]]}
conns['Get Parcelas Cash Flow'] = {"main": [[{"node": "Merge", "type": "main", "index": 7}]]}

conns['Set Report Config (Monthly)']['main'][0].append({"node": "Get Formas Pagamento1", "type": "main", "index": 0})
conns['Set Report Config (Monthly)']['main'][0].append({"node": "Get Parcelas Cash Flow1", "type": "main", "index": 0})
conns['Get Formas Pagamento1'] = {"main": [[{"node": "Merge1", "type": "main", "index": 6}]]}
conns['Get Parcelas Cash Flow1'] = {"main": [[{"node": "Merge1", "type": "main", "index": 7}]]}

print("Connections wired")

# ============================================================
# STEP 4: Update Process All Data code
# ============================================================
with open(os.path.expanduser('~') + '/financial-tracker-LMS/process_all_data_new.js', 'r', encoding='utf-8') as f:
    pad_code = f.read()

for n in nodes:
    if n['name'] == 'Process All Data':
        n['parameters']['jsCode'] = pad_code
        print("Updated Process All Data")
        break

# ============================================================
# STEP 5: Update Process Monthly Data code
# ============================================================
with open(os.path.expanduser('~') + '/financial-tracker-LMS/process_monthly_data_new.js', 'r', encoding='utf-8') as f:
    pmd_code = f.read()

for n in nodes:
    if n['name'] == 'Process Monthly Data':
        n['parameters']['jsCode'] = pmd_code
        print("Updated Process Monthly Data")
        break

# ============================================================
# STEP 6: Update Format Weekly Summary
# ============================================================
with open(os.path.expanduser('~') + '/financial-tracker-LMS/cash_flow_weekly_section.js', 'r', encoding='utf-8') as f:
    cf_weekly = f.read()

for n in nodes:
    if n['name'] == 'Format Weekly Summary':
        code = n['parameters']['jsCode']
        # Find the charts line
        import re
        match = re.search(r"lines\.push\(['\"].*[Gg]r.ficos abaixo", code)
        if match:
            insert_pos = code.rfind('\n', 0, match.start()) + 1
            code = code[:insert_pos] + cf_weekly + '\n' + code[insert_pos:]
            n['parameters']['jsCode'] = code
            print("Updated Format Weekly Summary")
        else:
            print("WARNING: Could not find insert point in Format Weekly Summary")
        break

# ============================================================
# STEP 7: Update Format Monthly Summary
# ============================================================
with open(os.path.expanduser('~') + '/financial-tracker-LMS/cash_flow_monthly_section.js', 'r', encoding='utf-8') as f:
    cf_monthly = f.read()

for n in nodes:
    if n['name'] == 'Format Monthly Summary':
        code = n['parameters']['jsCode']
        # Find the return statement
        match = re.search(r"return \[\{", code)
        if match:
            insert_pos = code.rfind('\n', 0, match.start()) + 1
            code = code[:insert_pos] + cf_monthly + '\n' + code[insert_pos:]
            n['parameters']['jsCode'] = code
            print("Updated Format Monthly Summary")
        else:
            print("WARNING: Could not find insert point in Format Monthly Summary")
        break

# Save
outpath = os.path.expanduser('~') + '/financial-tracker-LMS/workflow_v3_final.json'
with open(outpath, 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False)
print(f"Saved. Total nodes: {len(nodes)}")
