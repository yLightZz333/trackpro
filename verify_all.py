# -*- coding: utf-8 -*-
import urllib.request
import json

# 1. Overview metrics
with urllib.request.urlopen('http://localhost:3001/api/dashboard/overview') as resp:
    data = json.loads(resp.read().decode('utf-8'))
    print('All 20+ KPIs:', list(data['kpis'].keys()))

# 2. Financial settings
with urllib.request.urlopen('http://localhost:3001/api/settings/financial') as resp:
    fin = json.loads(resp.read().decode('utf-8'))
    print('Financial settings:', fin)

# 3. Facebook fetch accounts
req = urllib.request.Request('http://localhost:3001/api/facebook/fetch_accounts', data=json.dumps({'access_token':'EAABtest'}).encode(), headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req) as resp:
    fb = json.loads(resp.read().decode('utf-8'))
    print('Facebook accounts fetched:', fb['success'], len(fb.get('accounts', [])))
