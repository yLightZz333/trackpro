#!/usr/bin/env python3
"""
TrackPro - Servidor Backend & Motor de Atribuição Server-Side (Clone UTMify)
- Webhooks Nativos: Greenn, Hotmart, Cakto, Kiwify, Wiapy e Universal
- Disparo Server-Side Meta Ads CAPI (Conversions API) com hash SHA-256
- PWA (Progressive Web App) para acesso mobile como App nativo
- Rastreamento First-Party com Preservação de Links de Checkout (Link Forwarder)
"""

import sys
import os
import json
import sqlite3
import uuid
import datetime
import hashlib
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trackpro.db')
DEMO_TOKEN = 'a8b3c4d5-e6f7-4a1b-9c8d-123456789abc'

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout = 30000')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        company TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS api_credentials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        token TEXT NOT NULL UNIQUE,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        platform TEXT,
        cost_in_cents INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        order_external_id TEXT,
        product_id INTEGER,
        platform TEXT,
        payment_method TEXT,
        status TEXT NOT NULL DEFAULT 'waiting_payment',
        customer_name TEXT,
        customer_email TEXT,
        customer_phone TEXT,
        customer_document TEXT,
        customer_ip TEXT,
        price_in_cents INTEGER NOT NULL DEFAULT 0,
        gateway_fee_in_cents INTEGER NOT NULL DEFAULT 0,
        net_amount_in_cents INTEGER NOT NULL DEFAULT 0,
        currency TEXT NOT NULL DEFAULT 'BRL',
        is_test INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        approved_at TEXT,
        refunded_at TEXT
    );

    CREATE TABLE IF NOT EXISTS tracking_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        order_id INTEGER,
        session_id TEXT,
        event_type TEXT NOT NULL,
        utm_source TEXT,
        utm_medium TEXT,
        utm_campaign TEXT,
        utm_content TEXT,
        utm_term TEXT,
        src TEXT,
        sck TEXT,
        fbc TEXT,
        fbp TEXT,
        page_url TEXT,
        referrer TEXT,
        user_agent TEXT,
        ip_address TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        platform TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        daily_budget_in_cents INTEGER NOT NULL DEFAULT 0,
        total_spent_in_cents INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS automated_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        condition_metric TEXT NOT NULL,
        condition_operator TEXT NOT NULL,
        condition_value REAL NOT NULL,
        action_type TEXT NOT NULL,
        target_type TEXT NOT NULL,
        check_interval_minutes INTEGER DEFAULT 60,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS meta_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        pixel_id TEXT,
        access_token TEXT,
        test_event_code TEXT,
        active INTEGER DEFAULT 1,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS capi_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        order_id TEXT,
        event_name TEXT NOT NULL,
        pixel_id TEXT,
        status TEXT NOT NULL,
        response_code INTEGER,
        response_body TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    # Migration de colunas existentes se necessário
    for col in ['fbc', 'fbp']:
        try:
            cursor.execute(f"ALTER TABLE tracking_events ADD COLUMN {col} TEXT")
        except Exception:
            pass

    # Seed User se não existir (Início 100% Limpo, sem vendas ou saldo falso)
    user = cursor.execute("SELECT id FROM users WHERE email = 'demo@trackpro.com'").fetchone()
    if not user:
        cursor.execute("INSERT INTO users (name, email, password, company) VALUES (?, ?, ?, ?)",
                       ('Meu Negócio', 'demo@trackpro.com', 'demo123', 'Minha Operação'))
        user_id = cursor.lastrowid

        cursor.execute("INSERT INTO api_credentials (user_id, name, token, active) VALUES (?, ?, ?, ?)",
                       (user_id, 'Token Universal (Greenn, Hotmart, Kiwify, Cakto, Wiapy)', DEMO_TOKEN, 1))

        # Configuração inicial de Meta CAPI vazia
        cursor.execute("INSERT OR REPLACE INTO meta_settings (user_id, pixel_id, access_token, test_event_code, active) VALUES (?, '', '', '', 1)", (user_id,))

    conn.commit()

    conn.commit()
    conn.close()

# ==================== PARSER UNIVERSAL DE WEBHOOKS ====================
def parse_webhook_payload(headers, body):
    """
    Parser adaptativo para Greenn, Hotmart, Cakto, Kiwify, Wiapy e UTMify Universal.
    Extrai dados do comprador, valor, status e parâmetros de tráfego UTM.
    """
    platform = 'Universal'
    order_id = None
    status = 'paid'
    customer_name = 'Comprador'
    customer_email = ''
    customer_phone = ''
    customer_doc = ''
    product_name = 'Produto'
    payment_method = 'pix'
    price_cents = 0
    gateway_fee_cents = 0
    tracking = {}
    fbc = None
    fbp = None

    # Normalizar headers em minúsculas
    norm_headers = {k.lower(): v for k, v in headers.items()}

    # 1. HOTMART WEBHOOK (v2.0.0 ou 1.0.0)
    if 'x-hotmart-hottok' in norm_headers or 'hottok' in body or (body.get('data') and body.get('data', {}).get('purchase')):
        platform = 'Hotmart'
        data = body.get('data', {})
        purchase = data.get('purchase', {})
        buyer = data.get('buyer', {})
        prod = data.get('product', {})
        order_id = purchase.get('transaction') or body.get('id') or f"HM-{uuid.uuid4().hex[:6].upper()}"
        p_status = str(purchase.get('status', '')).upper()
        status = 'paid' if p_status in ['APPROVED', 'COMPLETE', 'PAID'] else ('refunded' if p_status in ['REFUNDED', 'CHARGEBACK', 'DISPUTE'] else 'waiting_payment')
        customer_name = buyer.get('name', 'Comprador Hotmart')
        customer_email = buyer.get('email', '')
        customer_phone = buyer.get('phone', '')
        customer_doc = buyer.get('document', '')
        product_name = prod.get('name', 'Produto Hotmart')
        price_val = purchase.get('price', {}).get('value', 0)
        price_cents = int(float(price_val) * 100) if price_val else 0
        gateway_fee_cents = int(price_cents * 0.099)
        track = purchase.get('tracking', {})
        tracking = {
            'src': track.get('external_code'),
            'sck': track.get('source_sck'),
            'utm_source': track.get('source') if track.get('source') != 'HOTMART' else 'hotmart',
            'utm_medium': 'cpc',
            'utm_campaign': track.get('external_code') or 'campanha_hotmart',
            'utm_content': track.get('source_sck')
        }

    # 2. KIWIFY WEBHOOK
    elif 'order_status' in body or 'TrackingParameters' in body or 'sale_type' in body:
        platform = 'Kiwify'
        order_id = body.get('order_id') or body.get('order_ref') or f"KW-{uuid.uuid4().hex[:6].upper()}"
        k_status = str(body.get('order_status', '')).lower()
        status = 'paid' if k_status in ['paid', 'approved'] else ('refunded' if 'refund' in k_status or 'chargeback' in k_status else 'waiting_payment')
        cust = body.get('Customer', {})
        customer_name = cust.get('full_name', 'Comprador Kiwify')
        customer_email = cust.get('email', '')
        customer_phone = cust.get('mobile', '')
        customer_doc = cust.get('CPF', '')
        product_name = body.get('Product', {}).get('product_name', 'Produto Kiwify')
        payment_method = body.get('payment_method', 'pix')
        comm = body.get('Commissions', {})
        price_cents = int(comm.get('charge_amount') or comm.get('product_base_price') or 0)
        gateway_fee_cents = int(comm.get('kiwify_fee') or (price_cents * 0.0899))
        track = body.get('TrackingParameters', {})
        tracking = {
            'src': track.get('src'),
            'sck': track.get('sck'),
            'utm_source': track.get('utm_source'),
            'utm_medium': track.get('utm_medium'),
            'utm_campaign': track.get('utm_campaign'),
            'utm_content': track.get('utm_content'),
            'utm_term': track.get('utm_term')
        }

    # 3. GREENN WEBHOOK
    elif 'x-webhook-token' in norm_headers or body.get('event') in ['salePaid', 'saleCreated', 'saleRefunded'] or (body.get('data') and 'transaction' in body.get('data', {})):
        platform = 'Greenn'
        data = body.get('data', {})
        trans = data.get('transaction', {})
        cust = data.get('customer', {})
        order_id = trans.get('id') or body.get('id') or f"GN-{uuid.uuid4().hex[:6].upper()}"
        ev = str(body.get('event', trans.get('status', ''))).lower()
        status = 'paid' if 'paid' in ev else ('refunded' if 'refund' in ev else 'waiting_payment')
        customer_name = cust.get('name', 'Comprador Greenn')
        customer_email = cust.get('email', '')
        customer_phone = cust.get('phone', '')
        customer_doc = cust.get('document', '')
        product_name = data.get('product', {}).get('name', 'Produto Greenn')
        payment_method = trans.get('payment_method', 'pix')
        price_cents = int(trans.get('amount') or 0)
        gateway_fee_cents = int(price_cents * 0.059)
        track = data.get('tracking', {})
        tracking = {
            'src': track.get('src'),
            'sck': track.get('sck'),
            'utm_source': track.get('utm_source'),
            'utm_medium': track.get('utm_medium'),
            'utm_campaign': track.get('utm_campaign'),
            'utm_content': track.get('utm_content'),
            'utm_term': track.get('utm_term')
        }

    # 4. CAKTO WEBHOOK
    elif 'x-cakto-signature' in norm_headers or str(body.get('event', '')).startswith('purchase_') or (body.get('data') and 'offer_type' in body.get('data', {})):
        platform = 'Cakto'
        data = body.get('data', {})
        order_id = data.get('id') or body.get('id') or f"CK-{uuid.uuid4().hex[:6].upper()}"
        ev = str(body.get('event', data.get('status', ''))).lower()
        status = 'paid' if 'approved' in ev or 'paid' in ev else ('refunded' if 'refund' in ev else 'waiting_payment')
        cust = data.get('customer', {})
        customer_name = cust.get('name', 'Comprador Cakto')
        customer_email = cust.get('email', '')
        customer_phone = cust.get('phone', '')
        product_name = data.get('product', {}).get('name', 'Produto Cakto')
        payment_method = data.get('paymentMethod', 'credit_card')
        price_val = data.get('amount', 0)
        price_cents = int(float(price_val) * 100) if price_val else 0
        gateway_fee_cents = int(price_cents * 0.049)
        tracking = {
            'src': data.get('src'),
            'sck': data.get('sck'),
            'utm_source': data.get('utm_source'),
            'utm_medium': data.get('utm_medium'),
            'utm_campaign': data.get('utm_campaign'),
            'utm_content': data.get('utm_content'),
            'utm_term': data.get('utm_term')
        }

    # 5. WIAPY WEBHOOK
    elif 'payment' in body and ('customer' in body or 'tracking' in body):
        platform = 'Wiapy'
        payment = body.get('payment', {})
        cust = body.get('customer', {})
        order_id = payment.get('id') or str(body.get('id', f"WP-{uuid.uuid4().hex[:6].upper()}"))
        w_status = str(payment.get('status', '')).lower()
        status = 'paid' if w_status in ['approved', 'paid'] else ('refunded' if 'refund' in w_status else 'waiting_payment')
        customer_name = cust.get('name', 'Comprador Wiapy')
        customer_email = cust.get('email', '')
        customer_phone = cust.get('mobile_phone', '')
        price_cents = int(payment.get('amount', 0))
        gateway_fee_cents = int(payment.get('fee', price_cents * 0.05))
        track = body.get('tracking', {})
        tracking = {
            'src': track.get('src'),
            'sck': track.get('sck'),
            'utm_source': track.get('utm_source'),
            'utm_medium': track.get('utm_medium'),
            'utm_campaign': track.get('utm_campaign'),
            'utm_content': track.get('utm_content'),
            'utm_term': track.get('utm_term')
        }
        fbc = track.get('fbc')
        fbp = track.get('fbp')

    # 6. UNIVERSAL / UTMIFY PADRÃO
    else:
        order_id = body.get('orderId') or body.get('order_id') or body.get('transaction_id') or f"ORD-{uuid.uuid4().hex[:6].upper()}"
        cust = body.get('customer', {})
        customer_name = cust.get('name', 'Comprador Webhook')
        customer_email = cust.get('email', '')
        customer_phone = cust.get('phone', '')
        customer_doc = cust.get('document', '')
        price_cents = body.get('priceInCents') or body.get('price_in_cents') or int(float(body.get('value', 297)) * 100)
        gateway_fee_cents = body.get('gatewayFeeInCents') or int(price_cents * 0.05)
        status = body.get('status', 'paid')
        platform = body.get('platform', 'Checkout Personalizado')
        track = body.get('trackingParameters', {}) or body.get('tracking_parameters', {})
        tracking = {
            'src': track.get('src'),
            'sck': track.get('sck'),
            'utm_source': track.get('utm_source'),
            'utm_medium': track.get('utm_medium'),
            'utm_campaign': track.get('utm_campaign'),
            'utm_content': track.get('utm_content'),
            'utm_term': track.get('utm_term')
        }
        fbc = track.get('fbc')
        fbp = track.get('fbp')

    return {
        'platform': platform,
        'order_id': str(order_id),
        'status': status,
        'customer_name': customer_name,
        'customer_email': customer_email,
        'customer_phone': customer_phone,
        'customer_doc': customer_doc,
        'product_name': product_name,
        'payment_method': payment_method,
        'price_cents': price_cents,
        'gateway_fee_cents': gateway_fee_cents,
        'net_amount_cents': price_cents - gateway_fee_cents,
        'tracking': tracking,
        'fbc': fbc,
        'fbp': fbp
    }

# ==================== DISPARADOR SERVER-SIDE META ADS CAPI ====================
def send_meta_capi(user_id, order_data):
    """
    Envia o evento 'Purchase' diretamente para a Conversions API (CAPI) do Meta Ads.
    Hasheia dados do usuário em SHA-256 conforme padrão oficial da Meta.
    """
    conn = get_db()
    cursor = conn.cursor()
    meta = cursor.execute("SELECT pixel_id, access_token, test_event_code, active FROM meta_settings WHERE user_id = ? AND active = 1", (user_id,)).fetchone()
    
    if not meta or not meta['pixel_id'] or not meta['access_token']:
        conn.close()
        return {"status": "skipped", "message": "Meta CAPI não configurado. Adicione seu Pixel ID e Token CAPI na aba Meta Ads."}

    pixel_id = meta['pixel_id'].strip()
    access_token = meta['access_token'].strip()
    test_code = meta['test_event_code'].strip() if meta['test_event_code'] else None

    def hash_val(val):
        if not val:
            return None
        clean = str(val).strip().lower()
        return hashlib.sha256(clean.encode('utf-8')).hexdigest()

    user_data = {}
    if order_data.get('customer_email'):
        user_data['em'] = [hash_val(order_data.get('customer_email'))]
    if order_data.get('customer_phone'):
        phone_nums = ''.join(c for c in str(order_data.get('customer_phone')) if c.isdigit())
        if phone_nums:
            if not phone_nums.startswith('55') and len(phone_nums) in [10, 11]:
                phone_nums = '55' + phone_nums
            user_data['ph'] = [hash_val(phone_nums)]
    if order_data.get('customer_name'):
        parts = order_data.get('customer_name').strip().split(' ', 1)
        user_data['fn'] = [hash_val(parts[0])]
        if len(parts) > 1:
            user_data['ln'] = [hash_val(parts[1])]
    if order_data.get('customer_ip'):
        user_data['client_ip_address'] = order_data.get('customer_ip')
    if order_data.get('fbp'):
        user_data['fbp'] = order_data.get('fbp')
    if order_data.get('fbc'):
        user_data['fbc'] = order_data.get('fbc')

    event_payload = {
        "event_name": "Purchase",
        "event_time": int(datetime.datetime.now().timestamp()),
        "event_id": str(order_data.get('order_id')),
        "action_source": "website",
        "user_data": user_data,
        "custom_data": {
            "currency": "BRL",
            "value": float(order_data.get('price_cents', 0)) / 100.0,
            "content_name": order_data.get('product_name', 'Produto'),
            "content_type": "product"
        }
    }

    body = {"data": [event_payload]}
    if test_code:
        body["test_event_code"] = test_code

    url = f"https://graph.facebook.com/v19.0/{pixel_id}/events?access_token={access_token}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_code = resp.getcode()
            resp_text = resp.read().decode('utf-8')
            cursor.execute("INSERT INTO capi_logs (user_id, order_id, event_name, pixel_id, status, response_code, response_body) VALUES (?, ?, 'Purchase', ?, 'success', ?, ?)",
                           (user_id, str(order_data.get('order_id')), pixel_id, resp_code, resp_text))
            conn.commit()
            conn.close()
            return {"status": "success", "code": resp_code, "response": json.loads(resp_text)}
    except urllib.error.HTTPError as e:
        err_text = e.read().decode('utf-8', errors='replace')
        cursor.execute("INSERT INTO capi_logs (user_id, order_id, event_name, pixel_id, status, response_code, response_body) VALUES (?, ?, 'Purchase', ?, 'error', ?, ?)",
                       (user_id, str(order_data.get('order_id')), pixel_id, e.code, err_text))
        conn.commit()
        conn.close()
        return {"status": "error", "code": e.code, "response": err_text}
    except Exception as ex:
        conn.close()
        return {"status": "error", "code": 500, "response": str(ex)}


# ==================== HANDLER HTTP ====================
class TrackProHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-api-token, X-HOTMART-HOTTOK, X-Webhook-Token, X-Cakto-Signature')

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _read_json(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = self.rfile.read(content_length).decode('utf-8', errors='replace')
            try:
                return json.loads(body)
            except Exception:
                return {}
        return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # Health
        if path == '/api/health':
            self._send_json({"status": "ok", "app": "TrackPro Engine", "version": "2.0.0", "capi": True})
            return

        # PWA Manifest
        if path in ['/manifest.webmanifest', '/manifest.json']:
            manifest = {
                "name": "TrackPro — Rastreamento UTM & Meta CAPI",
                "short_name": "TrackPro",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#060911",
                "theme_color": "#10b981",
                "orientation": "portrait-primary",
                "icons": [
                    {
                        "src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='25' fill='%2310b981'/><text x='50' y='65' font-size='45' font-weight='bold' text-anchor='middle' fill='white'>TP</text></svg>",
                        "sizes": "192x192 512x512",
                        "type": "image/svg+xml",
                        "purpose": "any maskable"
                    }
                ]
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/manifest+json; charset=utf-8')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(manifest).encode('utf-8'))
            return

        # PWA Service Worker
        if path == '/sw.js':
            sw_code = """
            self.addEventListener('install', (e) => {
              self.skipWaiting();
            });
            self.addEventListener('activate', (e) => {
              e.waitUntil(clients.claim());
            });
            self.addEventListener('fetch', (e) => {
              // Network-first com fallback para cache
              e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
            });
            """
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(sw_code.encode('utf-8'))
            return

        # Pixel JS com Link Forwarder Automático (Kiwify, Hotmart, Greenn, Cakto, Wiapy)
        if path == '/tracking/pixel.js':
            token = params.get('token', [''])[0]
            script = f"""(function(){{
  'use strict';
  var TOKEN = '{token}';
  var API = window.location.origin;

  function getQueryParam(name) {{
    var search = window.location.search.substring(1);
    var vars = search.split('&');
    for (var i = 0; i < vars.length; i++) {{
      var pair = vars[i].split('=');
      if (decodeURIComponent(pair[0]) === name) return decodeURIComponent(pair[1] || '');
    }}
    return null;
  }}

  // 1. Extração de Parâmetros UTM e Meta Click IDs
  var currentUtms = {{
    utm_source: getQueryParam('utm_source'),
    utm_medium: getQueryParam('utm_medium'),
    utm_campaign: getQueryParam('utm_campaign'),
    utm_content: getQueryParam('utm_content'),
    utm_term: getQueryParam('utm_term'),
    src: getQueryParam('src'),
    sck: getQueryParam('sck')
  }};

  var fbclid = getQueryParam('fbclid');

  // Gerar / Recuperar _fbp (Facebook Browser ID)
  function getCookie(n) {{
    var v = document.cookie.match('(^|;) ?' + n + '=([^;]*)(;|$)');
    return v ? decodeURIComponent(v[2]) : null;
  }}
  function setCookie(n, v, days) {{
    var d = new Date();
    d.setTime(d.getTime() + (days * 86400000));
    document.cookie = n + '=' + encodeURIComponent(v) + '; path=/; expires=' + d.toUTCString();
  }}

  var fbp = getCookie('_fbp');
  if (!fbp) {{
    fbp = 'fb.1.' + (+new Date()) + '.' + Math.floor(Math.random() * 1000000000);
    setCookie('_fbp', fbp, 90);
  }}

  var fbc = getCookie('_fbc');
  if (fbclid) {{
    fbc = 'fb.1.' + (+new Date()) + '.' + fbclid;
    setCookie('_fbc', fbc, 90);
  }}

  // Persistir em LocalStorage e Cookies First-Party
  var hasUtm = false;
  for (var k in currentUtms) {{
    if (currentUtms[k]) {{ hasUtm = true; break; }}
  }}

  if (hasUtm) {{
    currentUtms.fbp = fbp;
    if (fbc) currentUtms.fbc = fbc;
    localStorage.setItem('_trackpro_utms', JSON.stringify(currentUtms));
    setCookie('_trackpro_utms', JSON.stringify(currentUtms), 30);
  }}

  var stored = JSON.parse(localStorage.getItem('_trackpro_utms') || '{{}}');
  if (!stored.fbp) stored.fbp = fbp;
  if (fbc && !stored.fbc) stored.fbc = fbc;

  // 2. Disparar Pageview para a API
  fetch(API + '/api/tracking/event', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json', 'x-api-token': TOKEN }},
    body: JSON.stringify({{
      event_type: 'pageview',
      utm_source: stored.utm_source,
      utm_medium: stored.utm_medium,
      utm_campaign: stored.utm_campaign,
      utm_content: stored.utm_content,
      utm_term: stored.utm_term,
      src: stored.src,
      sck: stored.sck,
      fbc: stored.fbc,
      fbp: stored.fbp,
      page_url: window.location.href,
      referrer: document.referrer
    }})
  }}).catch(function(){{}});

  // 3. Link Forwarder Automático (Injeta UTMs em botões de Kiwify, Hotmart, Greenn, Cakto, Wiapy)
  function decorateCheckoutLinks() {{
    var links = document.querySelectorAll('a[href]');
    var checkouts = ['kiwify.com.br', 'hotmart.com', 'greenn.com.br', 'cakto.com.br', 'wiapy.com'];
    
    links.forEach(function(link) {{
      var href = link.getAttribute('href');
      if (!href) return;
      var isCheckout = checkouts.some(function(domain) {{ return href.indexOf(domain) !== -1; }});
      if (isCheckout) {{
        var separator = href.indexOf('?') !== -1 ? '&' : '?';
        var params = [];
        if (stored.utm_source) params.push('utm_source=' + encodeURIComponent(stored.utm_source));
        if (stored.utm_medium) params.push('utm_medium=' + encodeURIComponent(stored.utm_medium));
        if (stored.utm_campaign) params.push('utm_campaign=' + encodeURIComponent(stored.utm_campaign));
        if (stored.utm_content) params.push('utm_content=' + encodeURIComponent(stored.utm_content));
        if (stored.utm_term) params.push('utm_term=' + encodeURIComponent(stored.utm_term));
        if (stored.src) params.push('src=' + encodeURIComponent(stored.src));
        if (stored.sck) params.push('sck=' + encodeURIComponent(stored.sck));
        if (stored.fbc) params.push('fbc=' + encodeURIComponent(stored.fbc));
        if (stored.fbp) params.push('fbp=' + encodeURIComponent(stored.fbp));

        if (params.length > 0) {{
          link.setAttribute('href', href + separator + params.join('&'));
        }}
      }}
    }});
  }}

  if (document.readyState === 'complete' || document.readyState === 'interactive') {{
    decorateCheckoutLinks();
  }} else {{
    document.addEventListener('DOMContentLoaded', decorateCheckoutLinks);
  }}

  window.TrackPro = {{
    getUtms: function() {{ return stored; }},
    getFbp: function() {{ return fbp; }},
    getFbc: function() {{ return fbc; }}
  }};
}})();"""
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(script.encode('utf-8'))
            return

        # Dashboard Overview API
        if path in ['/api/dashboard', '/api/dashboard/overview']:
            conn = get_db()
            cursor = conn.cursor()
            
            row = cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN status = 'paid' THEN price_in_cents ELSE 0 END), 0) as total_revenue,
                    COALESCE(SUM(CASE WHEN status = 'paid' THEN gateway_fee_in_cents ELSE 0 END), 0) as total_fees,
                    COALESCE(SUM(CASE WHEN status = 'paid' THEN net_amount_in_cents ELSE 0 END), 0) as total_net,
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_orders
                FROM orders WHERE user_id = 1
            """).fetchone()

            spend_row = cursor.execute("SELECT COALESCE(SUM(total_spent_in_cents), 0) as total_spent FROM campaigns WHERE user_id = 1").fetchone()

            tot_rev = row['total_revenue']
            tot_spent = spend_row['total_spent']
            paid_ord = row['paid_orders'] or 0

            roas = round(tot_rev / tot_spent, 2) if tot_spent > 0 else 0
            roi = round(((tot_rev - tot_spent) / tot_spent) * 100, 2) if tot_spent > 0 else 0
            cpa = round((tot_spent / paid_ord) / 100, 2) if paid_ord > 0 else 0

            # Sources breakdown
            sources_rows = cursor.execute("""
                SELECT COALESCE(t.utm_source, 'direto') as source, 
                       SUM(o.price_in_cents) as revenue,
                       COUNT(o.id) as orders
                FROM orders o
                LEFT JOIN tracking_events t ON o.id = t.order_id
                WHERE o.status = 'paid'
                GROUP BY source
                ORDER BY revenue DESC
            """).fetchall()

            colors = {'facebook': '#1877F2', 'google': '#4285F4', 'instagram': '#E4405F', 'tiktok': '#00F2FE', 'direto': '#10B981'}
            sources_chart = [
                {"name": s['source'], "value": s['revenue'] / 100, "color": colors.get(s['source'].lower(), '#8B5CF6')}
                for s in sources_rows
            ]

            # Recent orders
            recent_rows = cursor.execute("""
                SELECT o.order_external_id as id, o.customer_name as customer, o.customer_email as email,
                       o.price_in_cents as amount_cents, o.status, o.payment_method, o.platform, o.created_at as date,
                       COALESCE(t.utm_source, 'direto') as utm_source,
                       COALESCE(t.utm_campaign, 'nenhuma') as utm_campaign,
                       COALESCE(t.utm_content, '-') as utm_content
                FROM orders o
                LEFT JOIN tracking_events t ON o.id = t.order_id
                ORDER BY o.created_at DESC LIMIT 15
            """).fetchall()

            recent_orders = [
                {
                    "id": r['id'],
                    "customer": r['customer'],
                    "email": r['email'],
                    "amount": r['amount_cents'] / 100,
                    "status": r['status'],
                    "platform": r['platform'],
                    "source": r['utm_source'],
                    "utm_source": r['utm_source'],
                    "utm_campaign": r['utm_campaign'],
                    "utm_content": r['utm_content'],
                    "date": r['date']
                } for r in recent_rows
            ]

            # Campaigns summary
            c_rows = cursor.execute("SELECT name, platform, status, total_spent_in_cents FROM campaigns WHERE user_id = 1").fetchall()
            campaign_summary = [
                {
                    "name": c['name'],
                    "platform": c['platform'],
                    "status": c['status'],
                    "spent": c['total_spent_in_cents'] / 100,
                    "revenue": (c['total_spent_in_cents'] * 3.4) / 100,
                    "roas": 3.4
                } for c in c_rows
            ]

            conn.close()

            resp = {
                "kpis": {
                    "faturamento": tot_rev / 100,
                    "gastoAds": tot_spent / 100,
                    "roi": roi,
                    "roas": roas,
                    "cpa": cpa,
                    "vendasHoje": paid_ord,
                    "faturamentoTrend": 0,
                    "gastoAdsTrend": 0,
                    "roiTrend": 0,
                    "roasTrend": 0,
                    "cpaTrend": 0,
                    "vendasHojeTrend": 0
                },
                "revenueChart": [],
                "sourcesChart": sources_chart,
                "recentOrders": recent_orders,
                "campaignSummary": campaign_summary
            }
            self._send_json(resp)
            return

        # Orders list
        if path == '/api/orders':
            conn = get_db()
            cursor = conn.cursor()
            rows = cursor.execute("""
                SELECT o.id, o.order_external_id, o.customer_name, o.customer_email, o.price_in_cents,
                       o.status, o.payment_method, o.platform, o.created_at,
                       t.utm_source, t.utm_medium, t.utm_campaign, t.utm_content, t.utm_term
                FROM orders o
                LEFT JOIN tracking_events t ON o.id = t.order_id
                ORDER BY o.created_at DESC
            """).fetchall()
            
            orders = [
                {
                    "id": r['order_external_id'],
                    "customer": r['customer_name'],
                    "email": r['customer_email'],
                    "amount": r['price_in_cents'] / 100,
                    "status": r['status'],
                    "paymentMethod": r['payment_method'],
                    "platform": r['platform'],
                    "date": r['created_at'],
                    "utm_source": r['utm_source'] or 'direto',
                    "utm_medium": r['utm_medium'] or '-',
                    "utm_campaign": r['utm_campaign'] or 'nenhuma',
                    "utm_content": r['utm_content'] or '-',
                    "utm_term": r['utm_term'] or '-'
                } for r in rows
            ]
            conn.close()
            self._send_json({"orders": orders})
            return

        # Meta Settings GET
        if path == '/api/meta/settings':
            conn = get_db()
            cursor = conn.cursor()
            meta = cursor.execute("SELECT pixel_id, access_token, test_event_code, active FROM meta_settings WHERE user_id = 1").fetchone()
            conn.close()
            self._send_json({
                "pixel_id": meta['pixel_id'] if meta else '',
                "access_token": meta['access_token'] if meta else '',
                "test_event_code": meta['test_event_code'] if meta else '',
                "active": meta['active'] if meta else 1
            })
            return

        # Meta CAPI Logs GET
        if path == '/api/meta/logs':
            conn = get_db()
            cursor = conn.cursor()
            logs = cursor.execute("SELECT * FROM capi_logs WHERE user_id = 1 ORDER BY id DESC LIMIT 20").fetchall()
            conn.close()
            self._send_json({"logs": [dict(l) for l in logs]})
            return

        # Serve static web application (raiz ou pasta demo)
        root_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
        demo_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'demo', 'index.html')
        html_to_serve = root_html if os.path.exists(root_html) else demo_html

        if path in ['/', '/index.html'] and os.path.exists(html_to_serve):
            with open(html_to_serve, 'r', encoding='utf-8') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
            return

        # 404
        self._send_json({"error": "Endpoint não encontrado"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        # Configurar Meta CAPI (Pixel ID + Token)
        if path == '/api/meta/settings':
            pixel_id = body.get('pixel_id', '').strip()
            access_token = body.get('access_token', '').strip()
            test_event_code = body.get('test_event_code', '').strip()
            active = 1 if body.get('active', True) else 0

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO meta_settings (user_id, pixel_id, access_token, test_event_code, active, updated_at)
                VALUES (1, ?, ?, ?, ?, datetime('now'))
            """, (pixel_id, access_token, test_event_code, active))
            conn.commit()
            conn.close()

            self._send_json({"success": True, "message": "Configurações do Meta CAPI salvas com sucesso!"})
            return

        # Disparar Evento de Teste Meta CAPI
        if path == '/api/meta/test':
            test_order = {
                'order_id': f"TEST-{uuid.uuid4().hex[:6].upper()}",
                'customer_name': 'Cliente Teste Meta',
                'customer_email': 'teste.capi@dominio.com',
                'customer_phone': '11999998888',
                'customer_ip': self.client_address[0],
                'price_cents': 19700,
                'product_name': 'Produto Teste CAPI'
            }
            res = send_meta_capi(1, test_order)
            self._send_json(res)
            return

        # Ingestão de Webhooks (Kiwify, Hotmart, Greenn, Cakto, Wiapy ou Universal)
        webhook_routes = [
            '/api/webhook/orders',
            '/api/webhook/kiwify',
            '/api/webhook/hotmart',
            '/api/webhook/greenn',
            '/api/webhook/cakto',
            '/api/webhook/wiapy',
            '/api/orders/webhook/orders'
        ]

        if path in webhook_routes:
            parsed_order = parse_webhook_payload(self.headers, body)
            
            # Se a rota foi específica (ex: /api/webhook/greenn), fixar a plataforma
            if 'kiwify' in path: parsed_order['platform'] = 'Kiwify'
            elif 'hotmart' in path: parsed_order['platform'] = 'Hotmart'
            elif 'greenn' in path: parsed_order['platform'] = 'Greenn'
            elif 'cakto' in path: parsed_order['platform'] = 'Cakto'
            elif 'wiapy' in path: parsed_order['platform'] = 'Wiapy'

            conn = get_db()
            cursor = conn.cursor()

            # Verificar se pedido já existe
            existing = cursor.execute("SELECT id FROM orders WHERE order_external_id = ?", (parsed_order['order_id'],)).fetchone()
            if existing:
                cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (parsed_order['status'], existing['id']))
                order_id = existing['id']
            else:
                cursor.execute('''
                    INSERT INTO orders (user_id, order_external_id, platform, payment_method, status,
                                        customer_name, customer_email, customer_phone, customer_document, customer_ip,
                                        price_in_cents, gateway_fee_in_cents, net_amount_in_cents)
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    parsed_order['order_id'], parsed_order['platform'], parsed_order['payment_method'], parsed_order['status'],
                    parsed_order['customer_name'], parsed_order['customer_email'], parsed_order['customer_phone'],
                    parsed_order['customer_doc'], self.client_address[0],
                    parsed_order['price_cents'], parsed_order['gateway_fee_cents'], parsed_order['net_amount_cents']
                ))
                order_id = cursor.lastrowid

                # Gravar UTMs vinculadas ao pedido
                t = parsed_order['tracking']
                cursor.execute('''
                    INSERT INTO tracking_events (user_id, order_id, event_type, utm_source, utm_medium, utm_campaign, utm_content, utm_term, src, sck, fbc, fbp)
                    VALUES (1, ?, 'purchase', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    order_id,
                    t.get('utm_source'), t.get('utm_medium'), t.get('utm_campaign'),
                    t.get('utm_content'), t.get('utm_term'), t.get('src'), t.get('sck'),
                    parsed_order.get('fbc'), parsed_order.get('fbp')
                ))

            conn.commit()
            conn.close()

            # Se status for pago/aprovado, dispara Meta CAPI automaticamente
            capi_result = None
            if parsed_order['status'] == 'paid':
                capi_result = send_meta_capi(1, parsed_order)

            self._send_json({
                "success": True,
                "message": f"Pedido {parsed_order['order_id']} da plataforma {parsed_order['platform']} atribuído com sucesso!",
                "platform": parsed_order['platform'],
                "status": parsed_order['status'],
                "orderId": parsed_order['order_id'],
                "metaCapi": capi_result
            }, 200)
            return

        # Pixel Tracking Event
        if path == '/api/tracking/event':
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tracking_events (user_id, event_type, utm_source, utm_medium, utm_campaign, utm_content, utm_term, src, sck, fbc, fbp, page_url, ip_address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                1,
                body.get('event_type', 'pageview'),
                body.get('utm_source'),
                body.get('utm_medium'),
                body.get('utm_campaign'),
                body.get('utm_content'),
                body.get('utm_term'),
                body.get('src'),
                body.get('sck'),
                body.get('fbc'),
                body.get('fbp'),
                body.get('page_url'),
                self.client_address[0]
            ))
            conn.commit()
            conn.close()
            self._send_json({"success": True})
            return

        self._send_json({"error": "Rota POST não encontrada"}, 404)


def run_server(port=3001):
    init_db()
    server = HTTPServer(('0.0.0.0', port), TrackProHandler)
    print(f"[TrackPro] Servidor Ativo em: http://localhost:{port}")
    print(f"[TrackPro] Dashboard Visual & PWA: http://localhost:{port}/")
    print(f"[TrackPro] Webhook Universal: http://localhost:{port}/api/webhook/orders")
    print(f"[TrackPro] Webhook Kiwify: http://localhost:{port}/api/webhook/kiwify")
    print(f"[TrackPro] Webhook Hotmart: http://localhost:{port}/api/webhook/hotmart")
    print(f"[TrackPro] Webhook Greenn: http://localhost:{port}/api/webhook/greenn")
    print(f"[TrackPro] Webhook Cakto: http://localhost:{port}/api/webhook/cakto")
    print(f"[TrackPro] Webhook Wiapy: http://localhost:{port}/api/webhook/wiapy")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == '__main__':
    port = 3001
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run_server(port)
