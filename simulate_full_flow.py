import urllib.request
import json
import time

BASE_URL = 'https://meutrackpro.onrender.com'

print("=" * 60)
print("INICIANDO SIMULAÇÃO COMPLETA DE TRÁFEGO E VENDA TRACKPRO")
print("=" * 60)

# 1. Login com credenciais do Lucas
login_req = urllib.request.Request(
    f'{BASE_URL}/api/auth/login',
    data=json.dumps({'email': 'luckinhasp4@gmail.com', 'password': 'yzzjl067_'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(login_req, timeout=15) as res:
    auth_data = json.loads(res.read().decode('utf-8'))
    token = auth_data['token']
    user = auth_data['user']
    print(f"1. Autenticação: OK! Logado como {user['name']} ({user['email']})")

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {token}'
}

# 2. Captura estado ANTES da simulação
req_dash_before = urllib.request.Request(f'{BASE_URL}/api/dashboard?period=today', headers=headers)
with urllib.request.urlopen(req_dash_before, timeout=15) as res:
    dash_before = json.loads(res.read().decode('utf-8'))
    kpis_before = dash_before.get('kpis', {})
    print(f"2. Estado Inicial: Faturamento R$ {kpis_before.get('faturamento', 0):.2f} | Vendas: {kpis_before.get('vendasAprovadas', 0)}")

# 3. ETAPA 1: Usuário clica no anúncio do Facebook e entra na Landing Page com Pixel e UTMs
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
    print(f"3. Etapa 1 (Visita na Página com Pixel + UTMs): Sucesso={resp_pv.get('success')}")

# 4. ETAPA 2: Usuário clica para comprar e vai para o Checkout (InitiateCheckout)
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
    print(f"4. Etapa 2 (Avanço pro Checkout - InitiateCheckout): Sucesso={resp_ic.get('success')}")

# 5. ETAPA 3: Webhook de Compra Aprovada (Kiwify / Gateway)
order_id_sim = f"ORD-SIM-{int(time.time())}"
webhook_payload = {
    "order_id": order_id_sim,
    "order_status": "paid",
    "payment_method": "pix",
    "Customer": {
        "full_name": "Marcos Vinicius de Souza",
        "email": "marcos.vinicius@gmail.com",
        "mobile": "+5511987654321"
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
    print(f"   Status: {wh_resp.get('status')} | Pedido: {wh_resp.get('orderId')}")

# 6. ETAPA 4: Verificação de Todos os Dados no Dashboard, Alertas, Gráficos e Campanhas
time.sleep(1)

req_dash_after = urllib.request.Request(f'{BASE_URL}/api/dashboard?period=today', headers=headers)
with urllib.request.urlopen(req_dash_after, timeout=15) as res:
    dash_after = json.loads(res.read().decode('utf-8'))

kpis_after = dash_after.get('kpis', {})
funnel_after = dash_after.get('funnel', {})
recent_orders = dash_after.get('recentOrders', [])
revenue_chart = dash_after.get('revenueChart', [])
sources_chart = dash_after.get('sourcesChart', [])
methods_chart = dash_after.get('paymentMethodsChart', [])

print("\n" + "=" * 60)
print("RESULTADOS DA VERIFICAÇÃO NO DASHBOARD:")
print("=" * 60)
print(f"📊 Faturamento Bruto: R$ {kpis_after.get('faturamento', 0):.2f} (Antes: R$ {kpis_before.get('faturamento', 0):.2f})")
print(f"💵 Faturamento Líquido: R$ {kpis_after.get('faturamentoLiquido', 0):.2f}")
print(f"📈 Lucro Real: R$ {kpis_after.get('lucroReal', 0):.2f}")
print(f"🎯 Vendas Aprovadas: {kpis_after.get('vendasAprovadas', 0)} (Antes: {kpis_before.get('vendasAprovadas', 0)})")
print(f"🏷️ Ticket Médio: R$ {kpis_after.get('ticketMedio', 0):.2f}")

print("\n🔽 FUNIL DE CONVERSÃO:")
ribbon = funnel_after.get('ribbon', {})
print(f"   Cliques: {ribbon.get('clicks', {}).get('count')} ({ribbon.get('clicks', {}).get('pct')})")
print(f"   Vis. Página: {ribbon.get('pageviews', {}).get('count')} ({ribbon.get('pageviews', {}).get('pct')})")
print(f"   ICs: {ribbon.get('ic', {}).get('count')} ({ribbon.get('ic', {}).get('pct')})")
print(f"   Vendas Apr.: {ribbon.get('orders_paid', {}).get('count')} ({ribbon.get('orders_paid', {}).get('pct')})")

print("\n📊 GRÁFICOS:")
print(f"   Fontes (UTM): {sources_chart}")
print(f"   Métodos de Pagamento: {methods_chart}")

# Verifica se a venda consta nos pedidos recentes
matching_order = next((o for o in recent_orders if o.get('externalId') == order_id_sim), None)
print(f"\n📦 PEDIDOS RECENTES: Encontrado = {matching_order is not None}")
if matching_order:
    print(f"   Cliente: {matching_order.get('customerName')} | Valor: R$ {matching_order.get('price', 0):.2f}")
    print(f"   Plataforma: {matching_order.get('platform')} | Método: {matching_order.get('paymentMethod')}")
    print(f"   UTM Campaign: {matching_order.get('utmCampaign')} | UTM Source: {matching_order.get('utmSource')}")

# Verifica Notificações
req_notif = urllib.request.Request(f'{BASE_URL}/api/notifications', headers=headers)
with urllib.request.urlopen(req_notif, timeout=15) as res:
    notif_data = json.loads(res.read().decode('utf-8'))
    notifs = notif_data.get('notifications', [])
    print(f"\n🔔 NOTIFICAÇÕES: Total = {len(notifs)}")
    if notifs:
        latest = notifs[0]
        print(f"   Último Alerta: [{latest.get('title')}] - {latest.get('message')}")

# Verifica Campanhas
req_camps = urllib.request.Request(f'{BASE_URL}/api/meta/campaigns', headers=headers)
with urllib.request.urlopen(req_camps, timeout=15) as res:
    camps_data = json.loads(res.read().decode('utf-8'))
    matching_camp = next((c for c in camps_data.get('campaigns', []) if c.get('name') == utm_campaign_name), None)
    print(f"\n🎯 CAMPANHAS META: '{utm_campaign_name}'")
    if matching_camp:
        print(f"   Vendas Reais Atribuídas: {matching_camp.get('real_sales')}")
        print(f"   Faturamento Real Atribuído: R$ {matching_camp.get('real_revenue', 0):.2f}")
        print(f"   Status: {matching_camp.get('status')}")

print("\n" + "=" * 60)
print("SIMULAÇÃO FINALIZADA COM SUCESSO!")
print("=" * 60)
