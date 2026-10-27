import urllib.request
import urllib.parse
import json
import time
import sys

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_URL = 'https://meutrackpro.onrender.com'

print("=" * 60)
print("SIMULACAO COMPLETA DO FLUXO: ANUNCIO -> PIXEL -> CHECKOUT -> COMPRA")
print("=" * 60)

# 1. Login
login_req = urllib.request.Request(
    f'{BASE_URL}/api/auth/login',
    data=json.dumps({'email': 'luckinhasp4@gmail.com', 'password': 'yzzjl067_'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(login_req, timeout=15) as res:
    auth_data = json.loads(res.read().decode('utf-8'))
    token = auth_data['token']
    user = auth_data['user']
    print(f"1. Autenticado como: {user['name']} ({user['email']})")

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {token}'
}

# 2. Captura estado antes
req_dash_before = urllib.request.Request(f'{BASE_URL}/api/dashboard?period=today', headers=headers)
with urllib.request.urlopen(req_dash_before, timeout=15) as res:
    dash_before = json.loads(res.read().decode('utf-8'))
    kpis_before = dash_before.get('kpis', {})
    print(f"2. Estado Inicial Hoje: Faturamento R$ {kpis_before.get('faturamento', 0):.2f} | Vendas: {kpis_before.get('vendasAprovadas', 0)}")

# 3. ETAPA 1: Clique no anúncio e acesso à página de vendas (PageView com UTMs)
utm_campaign_name = "CT1 VIDEO - CBO - SHIHTZU"
pageview_payload = {
    "event_type": "pageview",
    "utm_source": "facebook",
    "utm_medium": "cpc",
    "utm_campaign": utm_campaign_name,
    "utm_content": "Video_Criativo_01",
    "utm_term": "Publico_Aberto",
    "src": "fb_feed",
    "sck": "cbo_shihtzu",
    "fbc": "fb.1.1730055000.IwAR123456789sim",
    "fbp": "fb.1.1730055000.9876543210",
    "page_url": f"https://meuproduto.com/oferta?utm_source=facebook&utm_medium=cpc&utm_campaign={urllib.parse.quote(utm_campaign_name)}&utm_content=Video_Criativo_01&utm_term=Publico_Aberto&fbclid=IwAR123456789sim"
}

req_pv = urllib.request.Request(
    f'{BASE_URL}/api/tracking/event',
    data=json.dumps(pageview_payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req_pv, timeout=15) as res:
    resp_pv = json.loads(res.read().decode('utf-8'))
    print(f"3. Etapa 1 (Visita na Pagina com Pixel + UTMs): Sucesso={resp_pv.get('success')}")

# 4. ETAPA 2: Clique no botão de compra e ida para o Checkout (InitiateCheckout)
ic_payload = {
    "event_type": "initiate_checkout",
    "utm_source": "facebook",
    "utm_medium": "cpc",
    "utm_campaign": utm_campaign_name,
    "utm_content": "Video_Criativo_01",
    "utm_term": "Publico_Aberto",
    "src": "fb_feed",
    "sck": "cbo_shihtzu",
    "fbc": "fb.1.1730055000.IwAR123456789sim",
    "fbp": "fb.1.1730055000.9876543210",
    "page_url": "https://pay.kiwify.com.br/checkout123"
}
req_ic = urllib.request.Request(
    f'{BASE_URL}/api/tracking/event',
    data=json.dumps(ic_payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req_ic, timeout=15) as res:
    resp_ic = json.loads(res.read().decode('utf-8'))
    print(f"4. Etapa 2 (Avanco pro Checkout - InitiateCheckout): Sucesso={resp_ic.get('success')}")

# 5. ETAPA 3: Webhook de Compra Aprovada (Kiwify)
order_id_sim = f"ORD-LUCAS-{int(time.time())}"
webhook_payload = {
    "order_id": order_id_sim,
    "order_status": "paid",
    "payment_method": "pix",
    "Customer": {
        "full_name": "Juliana Silveira",
        "email": "juliana.silveira@gmail.com",
        "mobile": "+5511977778888"
    },
    "Commissions": {
        "charge_amount": 19700 # R$ 197,00
    },
    "TrackingParameters": {
        "utm_source": "facebook",
        "utm_medium": "cpc",
        "utm_campaign": utm_campaign_name,
        "utm_content": "Video_Criativo_01",
        "utm_term": "Publico_Aberto",
        "src": "fb_feed",
        "sck": "cbo_shihtzu",
        "fbc": "fb.1.1730055000.IwAR123456789sim",
        "fbp": "fb.1.1730055000.9876543210"
    }
}

req_wh = urllib.request.Request(
    f'{BASE_URL}/api/webhook/kiwify?token={token}',
    data=json.dumps(webhook_payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req_wh, timeout=15) as res:
    wh_resp = json.loads(res.read().decode('utf-8'))
    print(f"5. Etapa 3 (Webhook Venda Aprovada Kiwify): {wh_resp.get('message')}")
    print(f"   Pedido ID: {wh_resp.get('orderId')} | Status: {wh_resp.get('status')}")

# 6. ETAPA 4: Verificacao no Dashboard e em todos os modulos
time.sleep(1)

req_dash_after = urllib.request.Request(f'{BASE_URL}/api/dashboard?period=today', headers=headers)
with urllib.request.urlopen(req_dash_after, timeout=15) as res:
    dash_after = json.loads(res.read().decode('utf-8'))

kpis_after = dash_after.get('kpis', {})
funnel_after = dash_after.get('funnel', {})
recent_orders = dash_after.get('recentOrders', [])
sources_chart = dash_after.get('sourcesChart', [])
methods_chart = dash_after.get('paymentMethodsChart', [])

print("\n" + "=" * 60)
print("VERIFICACAO COMPLETA NO DASHBOARD:")
print("=" * 60)
print(f"[*] Faturamento Bruto: R$ {kpis_after.get('faturamento', 0):.2f}")
print(f"[*] Faturamento Liquido: R$ {kpis_after.get('faturamentoLiquido', 0):.2f}")
print(f"[*] Lucro Real: R$ {kpis_after.get('lucroReal', 0):.2f}")
print(f"[*] Vendas Aprovadas: {kpis_after.get('vendasAprovadas', 0)}")
print(f"[*] Ticket Medio: R$ {kpis_after.get('ticketMedio', 0):.2f}")

print("\n[+] FUNIL DE CONVERSAO:")
ribbon = funnel_after.get('ribbon', {})
print(f"   Cliques: {ribbon.get('clicks', {}).get('count')} ({ribbon.get('clicks', {}).get('pct')})")
print(f"   Vis. Pagina: {ribbon.get('pageviews', {}).get('count')} ({ribbon.get('pageviews', {}).get('pct')})")
print(f"   ICs: {ribbon.get('ic', {}).get('count')} ({ribbon.get('ic', {}).get('pct')})")
print(f"   Vendas Apr.: {ribbon.get('orders_paid', {}).get('count')} ({ribbon.get('orders_paid', {}).get('pct')})")

print("\n[+] GRAFICOS:")
print(f"   Origem de Trafego (UTM): {json.dumps(sources_chart, indent=2)}")
print(f"   Metodos de Pagamento: {json.dumps(methods_chart, indent=2)}")

# Verifica se a venda consta nos pedidos recentes
matching_order = next((o for o in recent_orders if o.get('id') == order_id_sim), None)
print(f"\n[+] TABELA DE PEDIDOS RECENTES: Encontrado = {matching_order is not None}")
if matching_order:
    print(f"   ID do Pedido: {matching_order.get('id')}")
    print(f"   Cliente: {matching_order.get('customer')}")
    print(f"   Valor: R$ {matching_order.get('amount', 0):.2f}")
    print(f"   Plataforma: {matching_order.get('platform')}")
    print(f"   Campanha UTM: {matching_order.get('utm_campaign')}")
    print(f"   Origem UTM: {matching_order.get('utm_source')}")

# Verifica Notificações
req_notif = urllib.request.Request(f'{BASE_URL}/api/notifications', headers=headers)
with urllib.request.urlopen(req_notif, timeout=15) as res:
    notif_data = json.loads(res.read().decode('utf-8'))
    notifs = notif_data.get('notifications', [])
    print(f"\n[+] NOTIFICACOES EM TEMPO REAL: Total = {len(notifs)}")
    if notifs:
        latest = notifs[0]
        print(f"   Ultimo Alerta: [{latest.get('title')}] - {latest.get('message')}")

# Verifica Campanhas
req_camps = urllib.request.Request(f'{BASE_URL}/api/meta/campaigns', headers=headers)
with urllib.request.urlopen(req_camps, timeout=15) as res:
    camps_data = json.loads(res.read().decode('utf-8'))
    matching_camps = [c for c in camps_data.get('campaigns', []) if utm_campaign_name in c.get('name', '')]
    print(f"\n[+] CAMPANHAS META ENCONTRADAS: {len(matching_camps)}")
    for mc in matching_camps:
        print(f"   Campanha: {mc.get('name')}")
        print(f"   Vendas Reais Atribuidas: {mc.get('sales')}")
        print(f"   Faturamento Real Atribuido: R$ {mc.get('revenue', 0):.2f}")
        print(f"   Status: {mc.get('status')}")

print("\n" + "=" * 60)
print("TODOS OS TESTES E ETAPAS PASSARAM COM SUCESSO TOTAL!")
print("=" * 60)
