import urllib.request
import json

BASE = 'https://meutrackpro.onrender.com'

# 1. Dashboard today
with urllib.request.urlopen(f'{BASE}/api/dashboard/overview?period=today', timeout=25) as resp:
    d_today = json.loads(resp.read().decode())
    k = d_today['kpis']
    gasto = k.get('gastoAds', 0)
    lucro = k.get('lucroReal', 0)
    vendas = k.get('vendasAprovadas', 0)
    print(f"Dashboard TODAY: Gasto Ads = R$ {gasto:.2f} | Lucro Real = R$ {lucro:.2f} | Vendas = {vendas}")
    assert gasto == 0.0, f"Expected 0.0 spend today, got {gasto}"
    assert lucro == 0.0, f"Expected 0.0 profit today, got {lucro}"

# 2. Dashboard all
with urllib.request.urlopen(f'{BASE}/api/dashboard/overview?period=all', timeout=25) as resp:
    d_all = json.loads(resp.read().decode())
    k_all = d_all['kpis']
    print(f"Dashboard ALL: Gasto Ads = R$ {k_all.get('gastoAds', 0):.2f} | Cliques = {k_all.get('cliques', 0)} | Impressoes = {k_all.get('impressoes', 0)}")
    print(f"Payment Methods Chart: {d_all.get('paymentMethodsChart', [])}")

# 3. Campaigns today
with urllib.request.urlopen(f'{BASE}/api/campaigns?period=today', timeout=25) as resp:
    c_today = json.loads(resp.read().decode())
    camps_today = c_today.get('campaigns', [])
    print(f"Campaigns TODAY count: {len(camps_today)}")
    assert len(camps_today) == 0, f"Expected 0 campaigns today, got {len(camps_today)}"

# 4. Campaigns all
with urllib.request.urlopen(f'{BASE}/api/campaigns?period=all', timeout=25) as resp:
    c_all = json.loads(resp.read().decode())
    camps = c_all.get('campaigns', [])
    print(f"Campaigns ALL count: {len(camps)}")
    total_sales = sum(c['sales'] for c in camps)
    total_ic = sum(c['initiate_checkouts'] for c in camps)
    print(f"Total Sales (Purchases): {total_sales} | Total ICs: {total_ic}")
    assert total_sales == 0, f"Expected 0 sales, got {total_sales}"
    assert total_ic > 0, f"Expected > 0 ICs, got {total_ic}"
    first_c = camps[0]
    print("Sample Campaign metrics:")
    print(f"  Name: {first_c['name']}")
    print(f"  Daily Budget: R$ {first_c['daily_budget']:.2f}")
    print(f"  Spent: R$ {first_c['spent']:.2f}")
    print(f"  Sales (Purchases): {first_c['sales']}")
    print(f"  Initiate Checkouts (IC): {first_c['initiate_checkouts']}")
    print(f"  Cost per IC (CPA IC): R$ {first_c['cost_per_ic']:.2f}")
    print(f"  Impressions: {first_c['impressions']}")
    print(f"  Clicks: {first_c['clicks']}")
    print(f"  CTR: {first_c['ctr']:.2f}%")
    print(f"  CPC: R$ {first_c['cpc']:.2f}")
    print(f"  CPM: R$ {first_c['cpm']:.2f}")

# 5. Adsets and Ads
with urllib.request.urlopen(f'{BASE}/api/facebook/adsets', timeout=25) as resp:
    adsets = json.loads(resp.read().decode()).get('adsets', [])
    print(f"Adsets count (across account): {len(adsets)}")
    assert len(adsets) == 14, f"Expected 14 adsets, got {len(adsets)}"

with urllib.request.urlopen(f'{BASE}/api/facebook/ads', timeout=25) as resp:
    ads = json.loads(resp.read().decode()).get('ads', [])
    print(f"Ads count (across account): {len(ads)}")
    assert len(ads) == 14, f"Expected 14 ads, got {len(ads)}"

print("ALL LIVE PRODUCTION CHECKS PASSED PERFECTLY!")
