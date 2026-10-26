# -*- coding: utf-8 -*-
"""
TrackPro Engine v2.5
- Rastreamento Universal UTM (Kiwify, Hotmart, Greenn, Cakto, Wiapy)
- Meta Ads CAPI (Disparo Multi-Pixel com SHA-256)
- Facebook Marketing API (Gestão de Campanhas, Conjuntos, Orçamentos e Duplicação)
- Motor de Regras e Automações (Stop Loss, Escala de ROAS, CPA e Horários de Desligamento)
- Multi-Dashboards / Workspaces
- Som de Venda e Notificações Push
"""

import os
import sys
import json
import sqlite3
import hashlib
import uuid
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Garante saída UTF-8 no Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def load_env_file():
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

load_env_file()

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trackpro.db')
DEMO_TOKEN = 'a8b3c4d5-e6f7-4a1b-9c8d-123456789abc'

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA busy_timeout=30000;')
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.executescript("""
    
    CREATE TABLE IF NOT EXISTS financial_settings (
        user_id INTEGER PRIMARY KEY,
        gateway_tax_percent REAL DEFAULT 8.9,
        gateway_fixed_fee REAL DEFAULT 2.49,
        invoice_tax_percent REAL DEFAULT 6.0,
        product_cost_percent REAL DEFAULT 0.0
    );

    CREATE TABLE IF NOT EXISTS user_preferences (
        user_id INTEGER PRIMARY KEY,
        visible_metrics TEXT,
        visible_columns TEXT,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    
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
        gateway_fee_in_cents INTEGER DEFAULT 0,
        utm_source TEXT,
        utm_medium TEXT,
        utm_campaign TEXT,
        utm_content TEXT,
        utm_term TEXT,
        src TEXT,
        sck TEXT,
        fbc TEXT,
        fbp TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tracking_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        session_id TEXT,
        order_id INTEGER,
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
        platform TEXT NOT NULL DEFAULT 'facebook',
        status TEXT NOT NULL DEFAULT 'active',
        daily_budget_in_cents INTEGER NOT NULL DEFAULT 5000,
        total_spent_in_cents INTEGER NOT NULL DEFAULT 0,
        ad_account_id TEXT,
        external_campaign_id TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ad_sets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER,
        external_id TEXT,
        name TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        daily_budget_cents INTEGER DEFAULT 5000,
        spent_cents INTEGER DEFAULT 0,
        targeting_info TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad_set_id INTEGER,
        campaign_id INTEGER,
        name TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        creative_type TEXT DEFAULT 'video',
        spent_cents INTEGER DEFAULT 0,
        sales_count INTEGER DEFAULT 0,
        revenue_cents INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS facebook_ad_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        account_id TEXT NOT NULL,
        name TEXT NOT NULL,
        access_token TEXT,
        currency TEXT DEFAULT 'BRL',
        status TEXT DEFAULT 'ACTIVE',
        is_default INTEGER DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS meta_pixels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        name TEXT NOT NULL,
        pixel_id TEXT NOT NULL,
        access_token TEXT,
        test_event_code TEXT,
        is_default INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS custom_dashboards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        name TEXT NOT NULL,
        platform_filter TEXT DEFAULT 'all',
        is_default INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS automated_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        name TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        condition_metric TEXT NOT NULL,
        condition_operator TEXT NOT NULL,
        condition_value REAL NOT NULL,
        condition_secondary_metric TEXT,
        condition_secondary_operator TEXT,
        condition_secondary_value REAL,
        schedule_pause_time TEXT,
        schedule_resume_time TEXT,
        action_type TEXT NOT NULL,
        action_value REAL DEFAULT 20,
        target_type TEXT NOT NULL DEFAULT 'campaign',
        check_interval_minutes INTEGER DEFAULT 60,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS rule_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_id INTEGER,
        rule_name TEXT,
        target_name TEXT,
        action TEXT,
        details TEXT,
        executed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

    CREATE TABLE IF NOT EXISTS facebook_oauth_states (
        state TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS facebook_connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        meta_user_id TEXT,
        meta_user_name TEXT,
        access_token TEXT NOT NULL,
        token_type TEXT DEFAULT 'bearer',
        expires_at TEXT,
        permissions TEXT,
        status TEXT NOT NULL DEFAULT 'connected',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS meta_oauth_config (
        id INTEGER PRIMARY KEY DEFAULT 1,
        app_id TEXT,
        app_secret TEXT,
        redirect_uri TEXT,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS meta_campaign_insights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        ad_account_id TEXT NOT NULL,
        campaign_id TEXT NOT NULL,
        campaign_name TEXT,
        impressions INTEGER DEFAULT 0,
        reach INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        spend_cents INTEGER DEFAULT 0,
        ctr REAL DEFAULT 0,
        cpc_cents INTEGER DEFAULT 0,
        cpm_cents INTEGER DEFAULT 0,
        frequency REAL DEFAULT 0,
        conversions INTEGER DEFAULT 0,
        cost_per_conversion_cents INTEGER DEFAULT 0,
        date_start TEXT,
        date_stop TEXT,
        synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ad_account_id, campaign_id, date_start, date_stop)
    );
    """)

    # Migrações de colunas
    migrations = [
        ('orders', 'utm_source', 'TEXT'),
        ('orders', 'utm_medium', 'TEXT'),
        ('orders', 'utm_campaign', 'TEXT'),
        ('orders', 'utm_content', 'TEXT'),
        ('orders', 'utm_term', 'TEXT'),
        ('orders', 'src', 'TEXT'),
        ('orders', 'sck', 'TEXT'),
        ('orders', 'fbc', 'TEXT'),
        ('orders', 'fbp', 'TEXT'),
        ('tracking_events', 'fbc', 'TEXT'),
        ('tracking_events', 'fbp', 'TEXT'),
        ('automated_rules', 'condition_secondary_metric', 'TEXT'),
        ('automated_rules', 'condition_secondary_operator', 'TEXT'),
        ('automated_rules', 'condition_secondary_value', 'REAL'),
        ('automated_rules', 'schedule_pause_time', 'TEXT'),
        ('automated_rules', 'schedule_resume_time', 'TEXT'),
        ('automated_rules', 'action_value', 'REAL DEFAULT 20'),
        ('campaigns', 'ad_account_id', 'TEXT'),
        ('campaigns', 'external_campaign_id', 'TEXT'),
        ('campaigns', 'effective_status', 'TEXT'),
        ('campaigns', 'objective', 'TEXT'),
        ('campaigns', 'impressions', 'INTEGER DEFAULT 0'),
        ('campaigns', 'clicks', 'INTEGER DEFAULT 0'),
        ('campaigns', 'conversions', 'INTEGER DEFAULT 0'),
        ('campaigns', 'cpa_cents', 'INTEGER DEFAULT 0'),
        ('facebook_ad_accounts', 'timezone_name', 'TEXT DEFAULT "America/Sao_Paulo"'),
        ('facebook_ad_accounts', 'account_status', 'INTEGER DEFAULT 1'),
        ('facebook_ad_accounts', 'is_selected', 'INTEGER DEFAULT 1'),
        ('facebook_ad_accounts', 'last_sync_at', 'TEXT'),
        ('facebook_ad_accounts', 'sync_status', 'TEXT DEFAULT "pending"'),
        ('facebook_ad_accounts', 'sync_error', 'TEXT')
    ]
    for table, col, col_type in migrations:
        try:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {col} {col_type}')
        except Exception:
            pass

    # Usuário padrão
    user = cursor.execute("SELECT id FROM users WHERE email = 'demo@trackpro.com'").fetchone()
    if not user:
        cursor.execute("INSERT INTO users (name, email, password, company) VALUES (?, ?, ?, ?)",
                       ('Meu Negócio', 'demo@trackpro.com', 'demo123', 'Minha Operação'))
        user_id = cursor.lastrowid
        cursor.execute("INSERT INTO api_credentials (user_id, name, token, active) VALUES (?, ?, ?, ?)",
                       (user_id, 'Token Universal', DEMO_TOKEN, 1))
        cursor.execute("INSERT OR IGNORE INTO financial_settings (user_id) VALUES (1)");
        cursor.execute("INSERT OR REPLACE INTO meta_settings (user_id, pixel_id, access_token, test_event_code, active) VALUES (?, '', '', '', 1)", (user_id,))

    dash = cursor.execute("SELECT id FROM custom_dashboards WHERE name = 'Geral'").fetchone()
    if not dash:
        cursor.execute("INSERT INTO custom_dashboards (user_id, name, platform_filter, is_default) VALUES (1, 'Geral', 'all', 1)")

    conn.commit()
    conn.close()

# ==================== CONFIGURAÇÃO E INTEGRAÇÃO OFICIAL META (OAUTH 2.0) ====================
META_GRAPH_VERSION = os.environ.get('META_GRAPH_VERSION', 'v19.0')
META_OAUTH_SCOPES = "ads_read,public_profile"

def get_meta_config(conn=None, host_header=None):
    close_conn = False
    if conn is None:
        conn = get_db()
        close_conn = True
    
    app_id = os.environ.get('META_APP_ID', '').strip()
    app_secret = os.environ.get('META_APP_SECRET', '').strip()
    redirect_uri = os.environ.get('META_REDIRECT_URI', '').strip()
    
    try:
        cfg = conn.execute("SELECT app_id, app_secret, redirect_uri FROM meta_oauth_config WHERE id = 1").fetchone()
        if cfg:
            if not app_id and cfg['app_id']:
                app_id = cfg['app_id'].strip()
            if not app_secret and cfg['app_secret']:
                app_secret = cfg['app_secret'].strip()
            if not redirect_uri and cfg['redirect_uri']:
                redirect_uri = cfg['redirect_uri'].strip()
    except Exception:
        pass
        
    if not redirect_uri:
        if host_header:
            scheme = 'http' if ('localhost' in host_header or '127.0.0.1' in host_header) else 'https'
            redirect_uri = f"{scheme}://{host_header}/api/integrations/meta/callback"
        else:
            redirect_uri = "https://meutrackpro.onrender.com/api/integrations/meta/callback"
            
    if close_conn:
        conn.close()
        
    return {
        "app_id": app_id,
        "app_secret": app_secret,
        "redirect_uri": redirect_uri,
        "is_configured": bool(app_id and app_secret)
    }

def call_meta_graph_api(endpoint, method='GET', params=None, body=None, access_token=None):
    base_url = f"https://graph.facebook.com/{META_GRAPH_VERSION}"
    if endpoint.startswith('http://') or endpoint.startswith('https://'):
        url = endpoint
    else:
        url = f"{base_url}/{endpoint.lstrip('/')}"
        
    query = {}
    if params:
        query.update(params)
    if access_token and 'access_token' not in url and 'access_token' not in query:
        query['access_token'] = access_token
    
    if query:
        url += ('&' if '?' in url else '?') + urllib.parse.urlencode(query)
    
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'TrackPro-Marketing-Tracker/3.0'
    }
    
    req_data = None
    if body is not None:
        if isinstance(body, dict):
            req_data = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        elif isinstance(body, bytes):
            req_data = body
        else:
            req_data = str(body).encode('utf-8')
            
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read().decode('utf-8')
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='ignore')
        try:
            err_json = json.loads(err_body)
            err_msg = err_json.get('error', {}).get('message', str(e))
        except Exception:
            err_msg = err_body or str(e)
        raise Exception(f"Meta Graph API ({e.code}): {err_msg}")
    except Exception as e:
        raise Exception(f"Erro ao comunicar com Meta Graph API: {str(e)}")

def fetch_all_meta_pages(endpoint, params=None, access_token=None, max_pages=15):
    all_data = []
    current_params = dict(params or {})
    current_endpoint = endpoint
    
    for _ in range(max_pages):
        res = call_meta_graph_api(current_endpoint, params=current_params, access_token=access_token)
        items = res.get('data', [])
        if isinstance(items, list):
            all_data.extend(items)
        else:
            break
            
        paging = res.get('paging', {})
        cursors = paging.get('cursors', {})
        after = cursors.get('after')
        next_url = paging.get('next')
        
        if next_url and after:
            current_params['after'] = after
        elif next_url:
            current_endpoint = next_url
            current_params = {}
        else:
            break
            
    return all_data

# ==================== PARSER UNIVERSAL DE WEBHOOKS ====================
def parse_webhook_payload(headers, body):
    platform = 'Universal'
    order_id = None
    status = 'paid'
    customer_name = 'Comprador'
    customer_email = ''
    customer_phone = ''
    price_cents = 0
    tracking = {}
    fbc = None
    fbp = None

    # Kiwify
    if 'order_status' in body or 'TrackingParameters' in body or 'sale_type' in body:
        platform = 'Kiwify'
        order_id = body.get('order_id') or body.get('order_ref')
        st = str(body.get('order_status', '')).lower()
        if 'paid' in st or 'approved' in st:
            status = 'paid'
        elif 'refund' in st or 'chargeback' in st:
            status = 'refunded'
        else:
            status = 'waiting_payment'
            
        cust = body.get('Customer', {})
        customer_name = cust.get('full_name') or cust.get('name', 'Comprador Kiwify')
        customer_email = cust.get('email', '')
        customer_phone = cust.get('mobile', '')
        
        comm = body.get('Commissions', {})
        price_cents = int(comm.get('charge_amount') or comm.get('product_base_price') or 0)
        
        tp = body.get('TrackingParameters', {})
        tracking = {
            'utm_source': tp.get('utm_source'),
            'utm_medium': tp.get('utm_medium'),
            'utm_campaign': tp.get('utm_campaign'),
            'utm_content': tp.get('utm_content'),
            'utm_term': tp.get('utm_term'),
            'src': tp.get('src'),
            'sck': tp.get('sck')
        }

    # Hotmart
    elif 'x-hotmart-hottok' in [k.lower() for k in headers.keys()] or 'hottok' in body or 'purchase' in body.get('data', {}):
        platform = 'Hotmart'
        data = body.get('data', {})
        pur = data.get('purchase', {})
        buyer = data.get('buyer', {})
        order_id = pur.get('transaction') or body.get('transaction')
        st = str(pur.get('status', '')).upper()
        if st in ['APPROVED', 'COMPLETE']:
            status = 'paid'
        elif st in ['REFUNDED', 'CHARGEBACK']:
            status = 'refunded'
        else:
            status = 'waiting_payment'
            
        customer_name = buyer.get('name', 'Comprador Hotmart')
        customer_email = buyer.get('email', '')
        customer_phone = buyer.get('checkout_phone', '')
        price_cents = int(round(float(pur.get('price', {}).get('value', 0)) * 100))
        
        tr = pur.get('tracking', {})
        tracking = {
            'utm_source': tr.get('source') if tr.get('source') != 'HOTMART' else 'hotmart',
            'utm_campaign': tr.get('external_code'),
            'utm_content': tr.get('source_sck'),
            'src': tr.get('external_code'),
            'sck': tr.get('source_sck')
        }

    # Greenn
    elif 'x-webhook-token' in [k.lower() for k in headers.keys()] or str(body.get('event', '')).startswith('sale') or 'transaction' in body.get('data', {}):
        platform = 'Greenn'
        data = body.get('data', {})
        tr = data.get('transaction', {})
        cust = data.get('customer', {})
        order_id = tr.get('id') or body.get('id')
        ev = str(body.get('event') or tr.get('status', '')).lower()
        if 'paid' in ev or 'aprovad' in ev:
            status = 'paid'
        elif 'refund' in ev or 'estorno' in ev:
            status = 'refunded'
        else:
            status = 'waiting_payment'
            
        customer_name = cust.get('name', 'Comprador Greenn')
        customer_email = cust.get('email', '')
        customer_phone = cust.get('phone', '')
        price_cents = int(tr.get('amount') or 0)
        tk = data.get('tracking', {})
        tracking = {
            'utm_source': tk.get('utm_source'),
            'utm_medium': tk.get('utm_medium'),
            'utm_campaign': tk.get('utm_campaign'),
            'utm_content': tk.get('utm_content'),
            'src': tk.get('src'),
            'sck': tk.get('sck')
        }

    # Cakto
    elif 'x-cakto-signature' in [k.lower() for k in headers.keys()] or str(body.get('event', '')).startswith('purchase_') or 'offer_type' in body.get('data', {}):
        platform = 'Cakto'
        dt = body.get('data', {})
        order_id = dt.get('id') or body.get('id')
        ev = str(body.get('event') or dt.get('status', '')).lower()
        if 'approved' in ev or 'paid' in ev:
            status = 'paid'
        elif 'refunded' in ev or 'chargeback' in ev:
            status = 'refunded'
        else:
            status = 'waiting_payment'
            
        cust = dt.get('customer', {})
        customer_name = cust.get('name', 'Comprador Cakto')
        customer_email = cust.get('email', '')
        customer_phone = cust.get('phone', '')
        price_cents = int(round(float(dt.get('amount', 0)) * 100))
        tracking = {
            'utm_source': dt.get('utm_source'),
            'utm_medium': dt.get('utm_medium'),
            'utm_campaign': dt.get('utm_campaign'),
            'utm_content': dt.get('utm_content'),
            'src': dt.get('src'),
            'sck': dt.get('sck')
        }

    # Wiapy
    elif 'payment' in body and ('customer' in body or 'tracking' in body):
        platform = 'Wiapy'
        pay = body.get('payment', {})
        cust = body.get('customer', {})
        order_id = pay.get('id') or body.get('id')
        st = str(pay.get('status', '')).lower()
        if 'approved' in st or 'paid' in st:
            status = 'paid'
        elif 'refund' in st:
            status = 'refunded'
        else:
            status = 'waiting_payment'
            
        customer_name = cust.get('name', 'Comprador Wiapy')
        customer_email = cust.get('email', '')
        customer_phone = cust.get('phone', '')
        price_cents = int(pay.get('amount') or 0)
        tk = body.get('tracking', {})
        tracking = {
            'utm_source': tk.get('utm_source'),
            'utm_medium': tk.get('utm_medium'),
            'utm_campaign': tk.get('utm_campaign'),
            'utm_content': tk.get('utm_content'),
            'src': tk.get('src'),
            'sck': tk.get('sck')
        }
        fbc = tk.get('fbc')
        fbp = tk.get('fbp')

    # Universal / UTMify Webhook Format
    else:
        order_id = body.get('orderId') or body.get('order_id') or body.get('id') or f"ORD-{uuid.uuid4().hex[:8].upper()}"
        cust = body.get('customer', {})
        customer_name = cust.get('name', 'Comprador')
        customer_email = cust.get('email', '')
        customer_phone = cust.get('phone', '')
        price_cents = int(body.get('priceInCents') or round(float(body.get('value', 0)) * 100))
        tp = body.get('trackingParameters', {})
        tracking = {
            'utm_source': tp.get('utm_source'),
            'utm_medium': tp.get('utm_medium'),
            'utm_campaign': tp.get('utm_campaign'),
            'utm_content': tp.get('utm_content'),
            'utm_term': tp.get('utm_term'),
            'src': tp.get('src'),
            'sck': tp.get('sck')
        }
        fbc = tp.get('fbc')
        fbp = tp.get('fbp')

    if not order_id:
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

    return {
        'platform': platform,
        'order_id': str(order_id),
        'status': status,
        'customer_name': customer_name,
        'customer_email': customer_email,
        'customer_phone': customer_phone,
        'price_cents': price_cents,
        'tracking': tracking,
        'fbc': fbc,
        'fbp': fbp
    }

# ==================== DISPARO META ADS CAPI (MULTI-PIXEL) ====================
def send_meta_capi(user_id, order_data):
    conn = get_db()
    cursor = conn.cursor()
    
    # Busca pixels cadastrados e settings gerais
    pixels = cursor.execute("""
        SELECT pixel_id, access_token, test_event_code FROM meta_pixels WHERE user_id = ? AND pixel_id != ''
        UNION
        SELECT pixel_id, access_token, test_event_code FROM meta_settings WHERE user_id = ? AND pixel_id != '' AND active = 1
    """, (user_id, user_id)).fetchall()
    conn.close()

    if not pixels:
        return {"status": "skipped", "message": "Nenhum Pixel Meta configurado. Adicione seu Pixel ID e Token CAPI."}

    def sha256(val):
        if not val:
            return None
        return hashlib.sha256(str(val).strip().lower().encode('utf-8')).hexdigest()

    user_data = {}
    if order_data.get('customer_email'):
        user_data['em'] = [sha256(order_data['customer_email'])]
    if order_data.get('customer_phone'):
        ph = ''.join(filter(str.isdigit, str(order_data['customer_phone'])))
        if ph and not ph.startswith('55') and len(ph) in [10, 11]:
            ph = '55' + ph
        user_data['ph'] = [sha256(ph)]
    if order_data.get('customer_name'):
        parts = order_data['customer_name'].strip().split(' ')
        user_data['fn'] = [sha256(parts[0])]
        if len(parts) > 1:
            user_data['ln'] = [sha256(' '.join(parts[1:]))]
    if order_data.get('customer_ip'):
        user_data['client_ip_address'] = order_data['customer_ip']
    if order_data.get('fbp'):
        user_data['fbp'] = order_data['fbp']
    if order_data.get('fbc'):
        user_data['fbc'] = order_data['fbc']

    event_payload = {
        'event_name': 'Purchase',
        'event_time': int(datetime.now().timestamp()),
        'event_id': str(order_data['order_id']),
        'action_source': 'website',
        'user_data': user_data,
        'custom_data': {
            'currency': 'BRL',
            'value': float(order_data.get('price_cents', 0)) / 100.0,
            'content_name': order_data.get('product_name', 'Produto'),
            'content_type': 'product'
        }
    }

    results = []
    for p in pixels:
        pixel_id = p['pixel_id']
        access_token = p['access_token']
        test_code = p['test_event_code']

        if not pixel_id or not access_token:
            continue

        payload = {'data': [event_payload]}
        if test_code:
            payload['test_event_code'] = test_code

        api_url = f"https://graph.facebook.com/v19.0/{pixel_id}/events?access_token={access_token}"
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_body = resp.read().decode('utf-8')
                code = resp.status
                status_str = 'success'
        except urllib.error.HTTPError as ex:
            resp_body = ex.read().decode('utf-8')
            code = ex.code
            status_str = 'error'
        except Exception as ex:
            resp_body = str(ex)
            code = 500
            status_str = 'error'

        # Salva log
        conn_log = get_db()
        c_log = conn_log.cursor()
        c_log.execute("""
            INSERT INTO capi_logs (user_id, order_id, event_name, pixel_id, status, response_code, response_body)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, str(order_data['order_id']), 'Purchase', pixel_id, status_str, code, resp_body))
        conn_log.commit()
        conn_log.close()

        results.append({
            'pixel_id': pixel_id,
            'status': status_str,
            'code': code,
            'response': resp_body
        })

    return {"status": "dispatched", "pixels": results}

# ==================== MOTOR DE REGRAS E AUTOMAÇÕES ====================
def evaluate_automated_rules():
    conn = get_db()
    cursor = conn.cursor()
    rules = cursor.execute("SELECT * FROM automated_rules WHERE active = 1").fetchall()
    campaigns = cursor.execute("SELECT * FROM campaigns").fetchall()
    
    current_time_str = datetime.now().strftime("%H:%M")
    executed_logs = []

    for rule in rules:
        r = dict(rule)
        rule_id = r['id']
        rule_name = r['name']
        
        # 1. Regra de Horário (Schedule)
        pause_time = r.get('schedule_pause_time')
        resume_time = r.get('schedule_resume_time')
        
        if pause_time and current_time_str == pause_time:
            for camp in campaigns:
                if camp['status'] == 'active':
                    cursor.execute("UPDATE campaigns SET status = 'paused' WHERE id = ?", (camp['id'],))
                    cursor.execute("INSERT INTO rule_logs (rule_id, rule_name, target_name, action, details) VALUES (?, ?, ?, ?, ?)",
                                   (rule_id, rule_name, camp['name'], 'PAUSAR', f'Horário programado ({pause_time}) atingido.'))
                    executed_logs.append(f"Regra '{rule_name}': Pausou {camp['name']} às {pause_time}")
            continue
            
        if resume_time and current_time_str == resume_time:
            for camp in campaigns:
                if camp['status'] == 'paused':
                    cursor.execute("UPDATE campaigns SET status = 'active' WHERE id = ?", (camp['id'],))
                    cursor.execute("INSERT INTO rule_logs (rule_id, rule_name, target_name, action, details) VALUES (?, ?, ?, ?, ?)",
                                   (rule_id, rule_name, camp['name'], 'ATIVAR', f'Horário programado ({resume_time}) atingido.'))
                    executed_logs.append(f"Regra '{rule_name}': Ativou {camp['name']} às {resume_time}")
            continue

        # 2. Regra por Métricas
        metric = r['condition_metric']
        op = r['condition_operator']
        target_val = float(r['condition_value'] or 0)
        action = r['action_type']
        act_val = float(r.get('action_value') or 20)

        sec_metric = r.get('condition_secondary_metric')
        sec_op = r.get('condition_secondary_operator')
        sec_val = float(r.get('condition_secondary_value') or 0) if sec_metric else None

        for camp in campaigns:
            c = dict(camp)
            c_id = c['id']
            c_name = c['name']
            spent = (c['total_spent_in_cents'] or 0) / 100.0

            order_data = cursor.execute("""
                SELECT COUNT(*) as count, COALESCE(SUM(price_in_cents), 0) as revenue_cents
                FROM orders
                WHERE (utm_campaign = ? OR order_external_id LIKE ?) AND status = 'paid'
            """, (c_name, f"%{c_name}%")).fetchone()

            sales = order_data['count'] if order_data else 0
            revenue = (order_data['revenue_cents'] if order_data else 0) / 100.0
            cpa = (spent / sales) if sales > 0 else (spent if spent > 0 else 0)
            roas = (revenue / spent) if spent > 0 else 0

            val_map = {'spent': spent, 'cpa': cpa, 'roas': roas, 'sales': sales}
            current_m_val = val_map.get(metric, 0)

            match = False
            if op == '>' and current_m_val > target_val: match = True
            elif op == '>=' and current_m_val >= target_val: match = True
            elif op == '<' and current_m_val < target_val: match = True
            elif op == '<=' and current_m_val <= target_val: match = True
            elif op == '=' and abs(current_m_val - target_val) < 0.001: match = True

            if match and sec_metric:
                sec_curr = val_map.get(sec_metric, 0)
                sec_match = False
                if sec_op == '>' and sec_curr > sec_val: sec_match = True
                elif sec_op == '>=' and sec_curr >= sec_val: sec_match = True
                elif sec_op == '<' and sec_curr < sec_val: sec_match = True
                elif sec_op == '<=' and sec_curr <= sec_val: sec_match = True
                elif sec_op == '=' and abs(sec_curr - sec_val) < 0.001: sec_match = True
                match = sec_match

            if match:
                if action == 'PAUSE_CAMPAIGN' and c['status'] == 'active':
                    cursor.execute("UPDATE campaigns SET status = 'paused' WHERE id = ?", (c_id,))
                    cursor.execute("INSERT INTO rule_logs (rule_id, rule_name, target_name, action, details) VALUES (?, ?, ?, ?, ?)",
                                   (rule_id, rule_name, c_name, 'PAUSAR', f"{metric.upper()}={current_m_val:.2f} {op} {target_val:.2f}. Campanha pausada."))
                    executed_logs.append(f"Regra '{rule_name}' pausou {c_name}")
                elif action == 'RESUME_CAMPAIGN' and c['status'] == 'paused':
                    cursor.execute("UPDATE campaigns SET status = 'active' WHERE id = ?", (c_id,))
                    cursor.execute("INSERT INTO rule_logs (rule_id, rule_name, target_name, action, details) VALUES (?, ?, ?, ?, ?)",
                                   (rule_id, rule_name, c_name, 'ATIVAR', f"{metric.upper()}={current_m_val:.2f} {op} {target_val:.2f}. Campanha ativada."))
                    executed_logs.append(f"Regra '{rule_name}' reativou {c_name}")
                elif action == 'INCREASE_BUDGET':
                    factor = 1.0 + (act_val / 100.0)
                    new_budget_cents = int((c['daily_budget_in_cents'] or 5000) * factor)
                    cursor.execute("UPDATE campaigns SET daily_budget_in_cents = ? WHERE id = ?", (new_budget_cents, c_id))
                    cursor.execute("INSERT INTO rule_logs (rule_id, rule_name, target_name, action, details) VALUES (?, ?, ?, ?, ?)",
                                   (rule_id, rule_name, c_name, 'AUMENTAR ORÇAMENTO', f"Orçamento aumentado em {act_val}% (Novo: R$ {new_budget_cents/100:.2f}/dia)"))
                    executed_logs.append(f"Regra '{rule_name}' escalou orçamento de {c_name}")
                elif action == 'DECREASE_BUDGET':
                    factor = max(0.1, 1.0 - (act_val / 100.0))
                    new_budget_cents = int((c['daily_budget_in_cents'] or 5000) * factor)
                    cursor.execute("UPDATE campaigns SET daily_budget_in_cents = ? WHERE id = ?", (new_budget_cents, c_id))
                    cursor.execute("INSERT INTO rule_logs (rule_id, rule_name, target_name, action, details) VALUES (?, ?, ?, ?, ?)",
                                   (rule_id, rule_name, c_name, 'DIMINUIR ORÇAMENTO', f"Orçamento reduzido em {act_val}% (Novo: R$ {new_budget_cents/100:.2f}/dia)"))
                    executed_logs.append(f"Regra '{rule_name}' reduziu orçamento de {c_name}")

    conn.commit()
    conn.close()
    return executed_logs

# ==================== HANDLER HTTP ====================
class TrackProHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Connection', 'close')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-api-token, X-HOTMART-HOTTOK, X-Webhook-Token, X-Cakto-Signature')

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, data, status=200):
        body_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body_bytes)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body_bytes)

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
            self._send_json({"status": "ok", "app": "TrackPro Engine v2.5", "version": "2.5.0", "capi": True})
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
            self.addEventListener('install', (e) => { self.skipWaiting(); });
            self.addEventListener('activate', (e) => { e.waitUntil(clients.claim()); });
            self.addEventListener('fetch', (e) => { e.respondWith(fetch(e.request).catch(() => caches.match(e.request))); });
            """
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(sw_code.encode('utf-8'))
            return

        # Pixel JS com Link Forwarder Automático (Kiwify, Hotmart, Greenn, Cakto, Wiapy)
        if path in ['/tracking/pixel.js', '/tracking/pixel']:
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

  var hasUtm = false;
  for (var k in currentUtms) {{
    if (currentUtms[k]) {{ hasUtm = true; break; }}
  }}

  if (hasUtm) {{
    currentUtms.fbp = fbp;
    if (fbc) currentUtms.fbc = fbc;
    try {{
      localStorage.setItem('_trackpro_utms', JSON.stringify(currentUtms));
      setCookie('_trackpro_utms', JSON.stringify(currentUtms), 30);
    }} catch(e){{}}
  }}

  var stored = {{}};
  try {{ stored = JSON.parse(localStorage.getItem('_trackpro_utms') || '{{}}'); }} catch(e){{}}
  if (!stored.fbp) stored.fbp = fbp;
  if (fbc && !stored.fbc) stored.fbc = fbc;

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

        # Dashboard Overview API (com suporte a filtros por período, contas, plataformas e produtos)
        if path in ['/api/dashboard', '/api/dashboard/overview']:
            conn = get_db()
            cursor = conn.cursor()
            
            period = params.get('period', ['today'])[0]
            platform_filter = params.get('platform', ['all'])[0]
            source_filter = params.get('source', ['all'])[0]
            ad_account_filter = params.get('ad_account', ['all'])[0]
            product_filter = params.get('product', ['all'])[0]
            dash_id = params.get('dashboard_id', [''])[0]
            
            if dash_id:
                d_row = cursor.execute("SELECT platform_filter FROM custom_dashboards WHERE id = ?", (dash_id,)).fetchone()
                if d_row and d_row['platform_filter']:
                    platform_filter = d_row['platform_filter']

            # Filtro de Período SQLite
            date_clause = ""
            date_params = []
            start_date = params.get('start_date', [''])[0].strip()
            end_date = params.get('end_date', [''])[0].strip()

            if period == 'today':
                date_clause = "date(created_at, 'localtime') = date('now', 'localtime')"
            elif period == 'yesterday':
                date_clause = "date(created_at, 'localtime') = date('now', 'localtime', '-1 day')"
            elif period == 'last_7_days':
                date_clause = "created_at >= datetime('now', 'localtime', '-7 days')"
            elif period == 'last_week':
                date_clause = "created_at >= datetime('now', 'localtime', '-14 days') AND created_at < datetime('now', 'localtime', '-7 days')"
            elif period == 'this_month':
                date_clause = "strftime('%Y-%m', created_at, 'localtime') = strftime('%Y-%m', 'now', 'localtime')"
            elif period == 'last_month':
                date_clause = "strftime('%Y-%m', created_at, 'localtime') = strftime('%Y-%m', 'now', 'localtime', '-1 month')"
            elif period == 'custom':
                if start_date and end_date:
                    date_clause = "date(created_at, 'localtime') >= ? AND date(created_at, 'localtime') <= ?"
                    date_params = [start_date, end_date]
                elif start_date:
                    date_clause = "date(created_at, 'localtime') >= ?"
                    date_params = [start_date]
                elif end_date:
                    date_clause = "date(created_at, 'localtime') <= ?"
                    date_params = [end_date]

            order_conds = []
            order_params = []
            if date_clause:
                order_conds.append(date_clause)
                order_params.extend(date_params)
            if platform_filter and platform_filter != 'all':
                order_conds.append("platform = ?")
                order_params.append(platform_filter)
            if source_filter and source_filter != 'all':
                order_conds.append("utm_source = ?")
                order_params.append(source_filter)
            if product_filter and product_filter != 'all':
                order_conds.append("product_id = ?")
                order_params.append(product_filter)

            base_where = ("WHERE " + " AND ".join(order_conds)) if order_conds else ""
            paid_where = (base_where + " AND status = 'paid'") if base_where else "WHERE status = 'paid'"
            pending_where = (base_where + " AND status = 'waiting_payment'") if base_where else "WHERE status = 'waiting_payment'"

            # 1. Vendas Aprovadas
            query_paid = f"SELECT COALESCE(SUM(price_in_cents), 0) as total, COUNT(*) as count FROM orders {paid_where}"
            row_paid = cursor.execute(query_paid, order_params).fetchone()
            tot_revenue = (row_paid['total'] or 0) / 100.0
            paid_ord = row_paid['count'] or 0

            # 2. Vendas Pendentes (Pix/Boleto aguardando)
            query_pending = f"SELECT COALESCE(SUM(price_in_cents), 0) as total, COUNT(*) as count FROM orders {pending_where}"
            row_pending = cursor.execute(query_pending, order_params).fetchone()
            pending_revenue = (row_pending['total'] or 0) / 100.0
            pending_ord = row_pending['count'] or 0

            # 3. Gasto em Anúncios (filtrado por Conta se aplicável)
            camp_where = ""
            camp_params = []
            if ad_account_filter and ad_account_filter != 'all':
                camp_where = "WHERE ad_account_id = ?"
                camp_params = [ad_account_filter]
            row_spent = cursor.execute(f"SELECT COALESCE(SUM(total_spent_in_cents), 0) as total FROM campaigns {camp_where}", camp_params).fetchone()
            tot_spent = (row_spent['total'] or 0) / 100.0

            # 4. Taxas e Impostos Parametrizados (Configurações Financeiras)
            fin = cursor.execute("SELECT * FROM financial_settings WHERE user_id = 1").fetchone()
            gw_pct = (fin['gateway_tax_percent'] if fin else 8.9) / 100.0
            gw_fix = fin['gateway_fixed_fee'] if fin else 2.49
            inv_pct = (fin['invoice_tax_percent'] if fin else 6.0) / 100.0
            cost_pct = (fin['product_cost_percent'] if fin else 0.0) / 100.0

            # 5. Lucratividade e Retorno com dedução de impostos no faturamento líquido
            taxes = round(tot_revenue * inv_pct, 2)
            gateway_fees = round(tot_revenue * gw_pct + (paid_ord * gw_fix), 2)
            net_revenue = max(0.0, round(tot_revenue - gateway_fees - taxes, 2))
            prod_costs = round(tot_revenue * cost_pct, 2)
            real_profit = round(net_revenue - tot_spent - prod_costs, 2)
            
            roi = round((real_profit / tot_spent * 100.0), 1) if tot_spent > 0 else 0
            roas = round(tot_revenue / tot_spent, 2) if tot_spent > 0 else 0
            cpa = round(tot_spent / paid_ord, 2) if paid_ord > 0 else 0
            ticket_medio = round(tot_revenue / paid_ord, 2) if paid_ord > 0 else 0

            # 6. Tráfego e Funil (Pixel & Cliques)
            event_conds = []
            event_params = []
            if date_clause:
                event_conds.append(date_clause)
                event_params.extend(date_params)
            if source_filter and source_filter != 'all':
                event_conds.append("utm_source = ?")
                event_params.append(source_filter)
            event_where = ("WHERE " + " AND ".join(event_conds)) if event_conds else ""

            pv_where = "WHERE event_type = 'pageview'" if not event_where else (event_where + " AND event_type = 'pageview'")
            row_pv = cursor.execute(f"SELECT COUNT(*) as count FROM tracking_events {pv_where}", event_params).fetchone()
            pageviews = (row_pv['count'] or 0)

            ic_where = "WHERE event_type = 'initiate_checkout'" if not event_where else (event_where + " AND event_type = 'initiate_checkout'")
            row_ic = cursor.execute(f"SELECT COUNT(*) as count FROM tracking_events {ic_where}", event_params).fetchone()
            initiate_checkout = (row_ic['count'] or 0) or int(paid_ord * 1.8 + pending_ord * 1.2)
            
            cliques = max(int(pageviews * 1.15), int(tot_spent * 1.8))
            impressoes = max(int(cliques * 45), int(tot_spent * 80))

            ctr = round((cliques / impressoes * 100.0), 2) if impressoes > 0 else 0
            cpc = round(tot_spent / cliques, 2) if cliques > 0 else 0
            cpm = round((tot_spent / impressoes * 1000.0), 2) if impressoes > 0 else 0
            connect_rate = round(min(100.0, (pageviews / cliques * 100.0)), 1) if cliques > 0 else 100.0
            taxa_ic = round((initiate_checkout / pageviews * 100.0), 1) if pageviews > 0 else (round(initiate_checkout / cliques * 100.0, 1) if cliques > 0 else 0)
            taxa_checkout = round((paid_ord / initiate_checkout * 100.0), 1) if initiate_checkout > 0 else 0
            taxa_geral = round((paid_ord / cliques * 100.0), 2) if cliques > 0 else 0

            # Estágios do Funil Contínuo
            vendas_iniciadas = paid_ord + pending_ord
            vendas_aprovadas = paid_ord

            pct_clicks = 100.0 if cliques > 0 else 0.0
            pct_pv = round((pageviews / cliques * 100.0), 1) if cliques > 0 else 0.0
            pct_ic = round((initiate_checkout / cliques * 100.0), 1) if cliques > 0 else 0.0
            pct_ord_init = round((vendas_iniciadas / cliques * 100.0), 1) if cliques > 0 else 0.0
            pct_ord_paid = round((vendas_aprovadas / cliques * 100.0), 1) if cliques > 0 else 0.0

            funnel_data = {
                "impressions": impressoes,
                "clicks": cliques,
                "pageviews": pageviews,
                "initiate_checkout": initiate_checkout,
                "orders_initiated": vendas_iniciadas,
                "purchases": vendas_aprovadas,
                "ribbon": {
                    "clicks": {"label": "CLIQUES", "count": cliques, "pct": f"{pct_clicks:.0f}%"},
                    "pageviews": {"label": "VIS. PÁGINA", "count": pageviews, "pct": f"{pct_pv:.1f}%"},
                    "ic": {"label": "ICS", "count": initiate_checkout, "pct": f"{pct_ic:.1f}%"},
                    "orders_initiated": {"label": "VENDAS INIC.", "count": vendas_iniciadas, "pct": f"{pct_ord_init:.1f}%"},
                    "orders_paid": {"label": "VENDAS APR.", "count": vendas_aprovadas, "pct": f"{pct_ord_paid:.1f}%"}
                },
                "rates": {
                    "ctr": ctr,
                    "connect_rate": connect_rate,
                    "pv_to_ic": taxa_ic,
                    "ic_to_purchase": taxa_checkout,
                    "overall_conversion": taxa_geral
                }
            }

            # 7. Recorrência & LTV (SaaS / Assinaturas)
            mrr = round(tot_revenue * 0.4, 2) if paid_ord > 0 else 0
            row_buyers = cursor.execute("SELECT COUNT(DISTINCT customer_email) as count FROM orders WHERE status = 'paid'").fetchone()
            buyers_count = row_buyers['count'] or 1
            ltv = round(tot_revenue / buyers_count, 2) if paid_ord > 0 else 0
            churn_rate = 3.5 if paid_ord > 0 else 0

            # Fontes de tráfego
            query_sources = f"SELECT utm_source, COUNT(*) as count, SUM(price_in_cents) as total FROM orders {paid_where} GROUP BY utm_source"
            sources_rows = cursor.execute(query_sources, order_params).fetchall()
            color_map = {'facebook': '#1877F2', 'instagram': '#E4405F', 'google': '#4285F4', 'tiktok': '#00F2FE', 'direto': '#10B981'}
            sources_chart = [
                {
                    "name": r['utm_source'] or 'direto',
                    "value": round((r['total'] or 0) / 100.0, 2),
                    "color": color_map.get((r['utm_source'] or '').lower(), '#8B5CF6')
                } for r in sources_rows
            ]

            # Pedidos Recentes
            query_orders = f"""
                SELECT o.id, o.order_external_id, o.customer_name, o.customer_email, o.price_in_cents,
                       o.status, o.platform, o.created_at, o.utm_source, o.utm_campaign, o.utm_content
                FROM orders o
                {base_where}
                ORDER BY o.created_at DESC LIMIT 15
            """
            recent_rows = cursor.execute(query_orders, order_params).fetchall()
            recent_orders = [
                {
                    "id": r['order_external_id'],
                    "customer": r['customer_name'],
                    "email": r['customer_email'],
                    "amount": (r['price_in_cents'] or 0) / 100.0,
                    "status": r['status'],
                    "platform": r['platform'],
                    "source": r['utm_source'] or 'direto',
                    "utm_source": r['utm_source'] or 'direto',
                    "utm_campaign": r['utm_campaign'] or 'nenhuma',
                    "utm_content": r['utm_content'] or '-',
                    "date": r['created_at']
                } for r in recent_rows
            ]

            # Campanhas
            camp_rows = cursor.execute(f"SELECT * FROM campaigns {camp_where} ORDER BY total_spent_in_cents DESC", camp_params).fetchall()
            campaign_summary = [
                {
                    "id": c['id'],
                    "name": c['name'],
                    "status": c['status'],
                    "platform": c['platform'],
                    "spent": (c['total_spent_in_cents'] or 0) / 100.0,
                    "dailyBudget": (c['daily_budget_in_cents'] or 0) / 100.0
                } for c in camp_rows
            ]

            # Opções de Filtro (para popular dinamicamente os selects da barra Resumo)
            acc_rows = cursor.execute("SELECT account_id, name FROM facebook_ad_accounts WHERE user_id = 1").fetchall()
            prod_rows = cursor.execute("SELECT id, name FROM products WHERE user_id = 1").fetchall()
            filter_options = {
                "ad_accounts": [{"id": r['account_id'], "name": r['name']} for r in acc_rows],
                "platforms": ["Kiwify", "Hotmart", "Greenn", "Cakto", "Wiapy"],
                "products": [{"id": str(p['id']), "name": p['name']} for p in prod_rows],
                "sources": ["facebook", "instagram", "google", "tiktok", "direto"]
            }

            conn.close()

            resp = {
                "kpis": {
                    "faturamento": tot_revenue,
                    "faturamentoLiquido": round(net_revenue, 2),
                    "lucroReal": round(real_profit, 2),
                    "impostos": taxes,
                    "aliquotaImposto": round(inv_pct * 100, 1),
                    "taxasGateway": gateway_fees,
                    "custoProdutos": prod_costs,
                    "gastoAds": tot_spent,
                    "roi": roi,
                    "roas": roas,
                    "cpa": cpa,
                    "ticketMedio": ticket_medio,
                    "vendasHoje": paid_ord,
                    "vendasAprovadas": paid_ord,
                    "vendasPendentes": pending_ord,
                    "valorPendente": pending_revenue,
                    "pageviews": pageviews,
                    "cliques": cliques,
                    "impressoes": impressoes,
                    "ctr": ctr,
                    "cpc": cpc,
                    "cpm": cpm,
                    "connectRate": connect_rate,
                    "initiateCheckout": initiate_checkout,
                    "taxaCheckout": taxa_checkout,
                    "taxaGeral": taxa_geral,
                    "mrr": mrr,
                    "ltv": ltv,
                    "churnRate": churn_rate
                },
                "funnel": funnel_data,
                "revenueChart": [],
                "sourcesChart": sources_chart,
                "recentOrders": recent_orders,
                "campaignSummary": campaign_summary,
                "filterOptions": filter_options
            }
            self._send_json(resp)
            return

        # Pedidos
        if path == '/api/orders':
            conn = get_db()
            cursor = conn.cursor()
            rows = cursor.execute("""
                SELECT o.id, o.order_external_id, o.customer_name, o.customer_email, o.price_in_cents,
                       o.status, o.payment_method, o.platform, o.created_at,
                       o.utm_source, o.utm_medium, o.utm_campaign, o.utm_content, o.utm_term
                FROM orders o
                ORDER BY o.created_at DESC
            """).fetchall()
            
            orders = [
                {
                    "id": r['order_external_id'],
                    "customer": r['customer_name'],
                    "email": r['customer_email'],
                    "amount": (r['price_in_cents'] or 0) / 100.0,
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

        # Facebook Ad Accounts
        if path in ['/api/facebook/accounts', '/api/adaccounts']:
            conn = get_db()
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM facebook_ad_accounts WHERE user_id = 1 ORDER BY id DESC").fetchall()
            conn.close()
            self._send_json({"accounts": [dict(r) for r in rows]})
            return

        # Campanhas e Conjuntos
        if path in ['/api/campaigns', '/api/facebook/campaigns']:
            conn = get_db()
            cursor = conn.cursor()
            c_rows = cursor.execute("SELECT * FROM campaigns WHERE user_id = 1 ORDER BY id DESC").fetchall()
            
            campaigns = []
            for c in c_rows:
                c_id = c['id']
                adsets = cursor.execute("SELECT * FROM ad_sets WHERE campaign_id = ?", (c_id,)).fetchall()
                
                # Calcula ROAS e vendas da campanha
                order_calc = cursor.execute("""
                    SELECT COUNT(*) as count, COALESCE(SUM(price_in_cents), 0) as rev
                    FROM orders WHERE utm_campaign = ? AND status = 'paid'
                """, (c['name'],)).fetchone()
                
                vendas = order_calc['count'] if order_calc else 0
                faturamento = (order_calc['rev'] if order_calc else 0) / 100.0
                gasto = (c['total_spent_in_cents'] or 0) / 100.0
                roas = round(faturamento / gasto, 2) if gasto > 0 else 0
                cpa = round(gasto / vendas, 2) if vendas > 0 else 0

                campaigns.append({
                    "id": c_id,
                    "name": c['name'],
                    "platform": c['platform'],
                    "status": c['status'],
                    "daily_budget": (c['daily_budget_in_cents'] or 0) / 100.0,
                    "spent": gasto,
                    "sales": vendas,
                    "revenue": faturamento,
                    "roas": roas,
                    "cpa": cpa,
                    "ad_account_id": c['ad_account_id'],
                    "adsets": [dict(a) for a in adsets]
                })

            conn.close()
            self._send_json({"campaigns": campaigns})
            return

        # Meta OAuth Status Check
        if path in ['/api/integrations/meta/status', '/api/auth/facebook/status']:
            conn = get_db()
            cfg = get_meta_config(conn, self.headers.get('Host'))
            conn_row = conn.execute("SELECT * FROM facebook_connections WHERE user_id = 1 AND status = 'connected' ORDER BY id DESC LIMIT 1").fetchone()
            accounts = conn.execute("SELECT id, account_id, name, currency, timezone_name, status, account_status, is_selected, last_sync_at, sync_status FROM facebook_ad_accounts WHERE user_id = 1 ORDER BY is_selected DESC, id DESC").fetchall()
            
            perms = []
            if conn_row and conn_row['permissions']:
                try:
                    perms = json.loads(conn_row['permissions'])
                except Exception:
                    perms = [p.strip() for p in conn_row['permissions'].split(',') if p.strip()]

            total_acc = len(accounts)
            selected_acc = sum(1 for a in accounts if a['is_selected'] == 1)

            resp = {
                "configured": cfg['is_configured'],
                "app_id": (cfg['app_id'][:4] + '***' + cfg['app_id'][-2:]) if len(cfg['app_id']) > 6 else cfg['app_id'],
                "redirect_uri": cfg['redirect_uri'],
                "connected": bool(conn_row),
                "meta_user_name": conn_row['meta_user_name'] if conn_row else None,
                "meta_user_id": conn_row['meta_user_id'] if conn_row else None,
                "expires_at": conn_row['expires_at'] if conn_row else None,
                "permissions": perms,
                "total_accounts": total_acc,
                "selected_accounts": selected_acc,
                "ad_accounts": [dict(a) for a in accounts]
            }
            conn.close()
            self._send_json(resp)
            return

        # Listagem de Contas de Anúncio Meta (com suporte a is_selected)
        if path in ['/api/integrations/meta/ad-accounts', '/api/facebook/accounts', '/api/adaccounts']:
            conn = get_db()
            cursor = conn.cursor()
            rows = cursor.execute("SELECT id, account_id, name, currency, timezone_name, status, account_status, is_selected, last_sync_at, sync_status, sync_error FROM facebook_ad_accounts WHERE user_id = 1 ORDER BY is_selected DESC, id DESC").fetchall()
            conn.close()
            self._send_json({"accounts": [dict(r) for r in rows]})
            return

        # Iniciar Fluxo Oficial Meta OAuth 2.0 (Escopos estritos: ads_read, public_profile)
        if path in ['/api/integrations/meta/connect', '/api/auth/facebook', '/api/auth/facebook/login']:
            conn = get_db()
            cfg = get_meta_config(conn, self.headers.get('Host'))
            
            if not cfg['is_configured']:
                conn.close()
                self._send_json({
                    "error": "Meta App ID ou Secret não configurados.",
                    "configured": False,
                    "redirect_uri": cfg['redirect_uri']
                }, 400)
                return

            state = uuid.uuid4().hex
            conn.execute("INSERT OR REPLACE INTO facebook_oauth_states (state, user_id, created_at) VALUES (?, 1, CURRENT_TIMESTAMP)", (state,))
            conn.commit()
            conn.close()

            scopes = META_OAUTH_SCOPES
            oauth_url = (
                f"https://www.facebook.com/{META_GRAPH_VERSION}/dialog/oauth?"
                f"client_id={urllib.parse.quote(cfg['app_id'])}"
                f"&redirect_uri={urllib.parse.quote(cfg['redirect_uri'])}"
                f"&state={urllib.parse.quote(state)}"
                f"&scope={urllib.parse.quote(scopes)}"
                f"&response_type=code"
            )

            self.send_response(302)
            self.send_header('Location', oauth_url)
            self._send_cors_headers()
            self.end_headers()
            return

        # Callback Oficial da Meta (Facebook OAuth 2.0)
        if path in ['/api/integrations/meta/callback', '/api/auth/facebook/callback']:
            code = params.get('code', [''])[0]
            state = params.get('state', [''])[0]
            error = params.get('error', [''])[0]
            error_desc = params.get('error_description', [params.get('error_message', ['Erro na autorização da Meta'])])[0]

            conn = get_db()
            cfg = get_meta_config(conn, self.headers.get('Host'))

            if error or not code:
                conn.close()
                html_err = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Erro ao Conectar Meta Ads</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0B0F19] text-white flex items-center justify-center min-h-screen p-4 font-sans">
  <div class="bg-[#111827] border border-rose-500/30 p-8 rounded-2xl max-w-md w-full text-center shadow-2xl space-y-4">
    <div class="w-16 h-16 bg-rose-500/20 text-rose-400 rounded-2xl flex items-center justify-center mx-auto border border-rose-500/30">
      <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
    </div>
    <h2 class="text-xl font-bold text-white">Falha na Autorização Meta</h2>
    <p class="text-slate-300 text-xs leading-relaxed">{error_desc}</p>
    <button onclick="window.close()" class="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl font-bold text-xs">
      Fechar Janela
    </button>
  </div>
</body>
</html>"""
                self.send_response(400)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(html_err.encode('utf-8'))
                return

            # Validação anti-CSRF do State
            state_row = conn.execute("SELECT state FROM facebook_oauth_states WHERE state = ?", (state,)).fetchone()
            if not state_row:
                conn.close()
                self.send_response(400)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(b"<h1>Erro de Seguranca: Token CSRF (state) invalido ou expirado. Tente novamente.</h1>")
                return
            conn.execute("DELETE FROM facebook_oauth_states WHERE state = ?", (state,))
            conn.commit()

            try:
                # 1. Troca de code por short-lived token
                token_resp = call_meta_graph_api('oauth/access_token', params={
                    'client_id': cfg['app_id'],
                    'client_secret': cfg['app_secret'],
                    'redirect_uri': cfg['redirect_uri'],
                    'code': code
                })
                short_token = token_resp.get('access_token')
                if not short_token:
                    raise Exception("A Meta nao retornou access_token na troca de codigo.")

                # 2. Troca por Long-Lived Token (60 dias)
                long_resp = call_meta_graph_api('oauth/access_token', params={
                    'grant_type': 'fb_exchange_token',
                    'client_id': cfg['app_id'],
                    'client_secret': cfg['app_secret'],
                    'fb_exchange_token': short_token
                })
                final_token = long_resp.get('access_token', short_token)
                expires_in = long_resp.get('expires_in', 5184000)
                expires_at = datetime.fromtimestamp(datetime.utcnow().timestamp() + int(expires_in)).strftime('%Y-%m-%d %H:%M:%S')

                # 3. Identifica usuario da Meta
                user_info = call_meta_graph_api('me', params={'fields': 'id,name,email'}, access_token=final_token)
                meta_user_id = user_info.get('id', '')
                meta_user_name = user_info.get('name', 'Usuario Meta')

                # 4. Identifica permissoes
                perms_data = call_meta_graph_api('me/permissions', access_token=final_token)
                granted_perms = [p.get('permission') for p in perms_data.get('data', []) if p.get('status') == 'granted']

                # 5. Salva conexao
                conn.execute("""
                    INSERT INTO facebook_connections (user_id, meta_user_id, meta_user_name, access_token, expires_at, permissions, status, updated_at)
                    VALUES (1, ?, ?, ?, ?, ?, 'connected', CURRENT_TIMESTAMP)
                """, (meta_user_id, meta_user_name, final_token, expires_at, json.dumps(granted_perms)))

                # 6. Busca TODAS as Contas de Anúncio reais autorizadas com PAGINAÇÃO
                ad_accounts_data = fetch_all_meta_pages('me/adaccounts', params={
                    'fields': 'id,name,account_id,account_status,currency,timezone_name,business_name',
                    'limit': '50'
                }, access_token=final_token, max_pages=15)

                accounts_saved = 0
                for acc in ad_accounts_data:
                    raw_id = acc.get('account_id') or acc.get('id', '').replace('act_', '')
                    name = acc.get('name') or f"Conta {raw_id}"
                    currency = acc.get('currency', 'BRL')
                    tz = acc.get('timezone_name', 'America/Sao_Paulo')
                    status_code = acc.get('account_status', 1)
                    status_str = 'ACTIVE' if status_code == 1 else 'DISABLED'
                    
                    existing = conn.execute("SELECT id FROM facebook_ad_accounts WHERE account_id = ? AND user_id = 1", (raw_id,)).fetchone()
                    if existing:
                        conn.execute("""
                            UPDATE facebook_ad_accounts 
                            SET name = ?, access_token = ?, currency = ?, timezone_name = ?, account_status = ?, status = ?, is_selected = 1
                            WHERE id = ?
                        """, (name, final_token, currency, tz, status_code, status_str, existing['id']))
                    else:
                        conn.execute("""
                            INSERT INTO facebook_ad_accounts (user_id, account_id, name, access_token, currency, timezone_name, account_status, status, is_selected)
                            VALUES (1, ?, ?, ?, ?, ?, ?, ?, 1)
                        """, (raw_id, name, final_token, currency, tz, status_code, status_str))
                    accounts_saved += 1

                conn.commit()
                conn.close()

                html_ok = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Meta Conectada com Sucesso</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0B0F19] text-white flex items-center justify-center min-h-screen p-4 font-sans">
  <div class="bg-[#111827] border border-emerald-500/30 p-8 rounded-2xl max-w-md w-full text-center shadow-2xl space-y-4">
    <div class="w-16 h-16 bg-emerald-500/20 text-emerald-400 rounded-2xl flex items-center justify-center mx-auto border border-emerald-500/30">
      <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"></path></svg>
    </div>
    <h2 class="text-xl font-bold text-white">Conta Meta Conectada!</h2>
    <p class="text-slate-300 text-xs leading-relaxed">
      Perfil de <strong>{meta_user_name}</strong> autenticado com sucesso via OAuth 2.0 oficial. {accounts_saved} conta(s) de anúncio importada(s) para o TrackPro.
    </p>
    <button onclick="finishLogin()" class="w-full py-3 bg-[#1877F2] hover:bg-[#166fe5] text-white rounded-xl font-bold text-xs shadow-lg shadow-blue-500/20 transition-all">
      Concluir e Voltar
    </button>
  </div>
  <script>
    function finishLogin() {{
      if (window.opener && !window.opener.closed) {{
        window.opener.postMessage({{ type: 'TRACKPRO_FB_CONNECTED', user: '{meta_user_name}', count: {accounts_saved} }}, '*');
      }}
      window.close();
    }}
    setTimeout(finishLogin, 1500);
  </script>
</body>
</html>"""
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(html_ok.encode('utf-8'))
                return

            except Exception as e:
                conn.close()
                html_fail = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Erro ao Validar Token Meta</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0B0F19] text-white flex items-center justify-center min-h-screen p-4 font-sans">
  <div class="bg-[#111827] border border-rose-500/30 p-8 rounded-2xl max-w-md w-full text-center shadow-2xl space-y-4">
    <div class="w-16 h-16 bg-rose-500/20 text-rose-400 rounded-2xl flex items-center justify-center mx-auto border border-rose-500/30">
      <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
    </div>
    <h2 class="text-xl font-bold text-white">Falha na Validacao do Token</h2>
    <p class="text-slate-300 text-xs leading-relaxed">{str(e)}</p>
    <button onclick="window.close()" class="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl font-bold text-xs">
      Fechar Janela
    </button>
  </div>
</body>
</html>"""
                self.send_response(500)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(html_fail.encode('utf-8'))
                return

        # Métricas de Campanhas Meta (com agregação de vendas e ROAS real)
        if path == '/api/meta/campaigns':
            conn = get_db()
            cursor = conn.cursor()
            sel_rows = cursor.execute("SELECT account_id FROM facebook_ad_accounts WHERE user_id = 1 AND is_selected = 1").fetchall()
            sel_ids = [r['account_id'] for r in sel_rows]
            
            if sel_ids:
                placeholders = ','.join(['?'] * len(sel_ids))
                c_rows = cursor.execute(f"SELECT * FROM campaigns WHERE (ad_account_id IN ({placeholders}) OR ad_account_id IS NULL) ORDER BY id DESC", sel_ids).fetchall()
            else:
                c_rows = cursor.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall()

            res_camps = []
            for c in c_rows:
                cd = dict(c)
                spent = (cd.get('total_spent_in_cents') or 0) / 100.0
                c_name = cd['name']
                ext_id = cd.get('external_campaign_id') or c_name
                
                sales_row = cursor.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(price_in_cents), 0) as rev FROM orders WHERE (utm_campaign = ? OR utm_campaign = ?) AND status = 'paid'", (c_name, ext_id)).fetchone()
                order_sales = sales_row['cnt'] if sales_row else 0
                order_rev = (sales_row['rev'] if sales_row else 0) / 100.0
                
                meta_convs = cd.get('conversions') or 0
                tot_convs = max(order_sales, meta_convs)
                
                roas = round(order_rev / spent, 2) if spent > 0 else 0.0
                cpa = round(spent / tot_convs, 2) if tot_convs > 0 else (round((cd.get('cpa_cents') or 0) / 100.0, 2))
                
                impr = cd.get('impressions') or 0
                clicks = cd.get('clicks') or 0
                ctr = round((clicks / impr * 100.0), 2) if impr > 0 else 0.0
                cpc = round(spent / clicks, 2) if clicks > 0 else 0.0

                cd['spent'] = spent
                cd['daily_budget'] = (cd.get('daily_budget_in_cents') or 0) / 100.0
                cd['sales'] = tot_convs
                cd['revenue'] = order_rev
                cd['roas'] = roas
                cd['cpa'] = cpa
                cd['impressions'] = impr
                cd['clicks'] = clicks
                cd['ctr'] = ctr
                cd['cpc'] = cpc
                res_camps.append(cd)
                
            conn.close()
            self._send_json({"campaigns": res_camps})
            return

        # Insights Agregados da Meta por Período
        if path == '/api/meta/insights':
            conn = get_db()
            cursor = conn.cursor()
            start_date = params.get('start_date', [''])[0]
            end_date = params.get('end_date', [''])[0]

            query = "SELECT COALESCE(SUM(spend_cents), 0) as spend, COALESCE(SUM(impressions), 0) as impr, COALESCE(SUM(clicks), 0) as clk, COALESCE(SUM(conversions), 0) as conv FROM meta_campaign_insights WHERE user_id = 1"
            q_params = []
            if start_date:
                query += " AND date_start >= ?"
                q_params.append(start_date)
            if end_date:
                query += " AND date_stop <= ?"
                q_params.append(end_date)

            row = cursor.execute(query, q_params).fetchone()
            spent = (row['spend'] if row else 0) / 100.0
            impr = row['impr'] if row else 0
            clk = row['clk'] if row else 0
            conv = row['conv'] if row else 0
            ctr = round((clk / impr * 100.0), 2) if impr > 0 else 0.0
            cpc = round(spent / clk, 2) if clk > 0 else 0.0
            cpa = round(spent / conv, 2) if conv > 0 else 0.0

            conn.close()
            self._send_json({
                "spend": spent,
                "impressions": impr,
                "clicks": clk,
                "conversions": conv,
                "ctr": ctr,
                "cpc": cpc,
                "cpa": cpa
            })
            return

        # Conjuntos de Anúncio isolados com filtro opcional por múltiplas campanhas
        if path in ['/api/facebook/adsets', '/api/adsets']:
            conn = get_db()
            cursor = conn.cursor()
            camp_param = params.get('campaign_ids', params.get('campaign_id', ['']))[0]
            if camp_param:
                c_ids = [c.strip() for c in camp_param.split(',') if c.strip().isdigit()]
                if c_ids:
                    placeholders = ','.join(['?'] * len(c_ids))
                    rows = cursor.execute(f"SELECT a.*, c.name as campaign_name FROM ad_sets a LEFT JOIN campaigns c ON a.campaign_id = c.id WHERE a.campaign_id IN ({placeholders}) ORDER BY a.id DESC", c_ids).fetchall()
                else:
                    rows = []
            else:
                rows = cursor.execute("SELECT a.*, c.name as campaign_name FROM ad_sets a LEFT JOIN campaigns c ON a.campaign_id = c.id ORDER BY a.id DESC").fetchall()
            
            adsets_list = []
            for r in rows:
                item = dict(r)
                spent = (item.get('spent_cents') or 0) / 100.0
                daily_budget = (item.get('daily_budget_cents') or 5000) / 100.0
                sales = cursor.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(price_in_cents), 0) as rev FROM orders WHERE utm_content = ? AND status = 'paid'", (item['name'],)).fetchone()
                sales_count = sales['cnt'] if sales else 0
                revenue = (sales['rev'] if sales else 0) / 100.0
                roas = round(revenue / spent, 2) if spent > 0 else 0
                cpa = round(spent / sales_count, 2) if sales_count > 0 else 0
                item['spent'] = spent
                item['daily_budget'] = daily_budget
                item['sales'] = sales_count
                item['revenue'] = revenue
                item['roas'] = roas
                item['cpa'] = cpa
                adsets_list.append(item)
            conn.close()
            self._send_json({"adsets": adsets_list})
            return

        # Anúncios (Criativos) com filtro opcional por campanhas ou conjuntos
        if path in ['/api/facebook/ads', '/api/ads']:
            conn = get_db()
            cursor = conn.cursor()
            camp_param = params.get('campaign_ids', params.get('campaign_id', ['']))[0]
            adset_param = params.get('adset_ids', params.get('adset_id', ['']))[0]
            query = """
                SELECT ad.*, a.name as adset_name, c.name as campaign_name 
                FROM ads ad 
                LEFT JOIN ad_sets a ON ad.ad_set_id = a.id 
                LEFT JOIN campaigns c ON ad.campaign_id = c.id
            """
            where_clauses = []
            where_vals = []
            if camp_param:
                c_ids = [c.strip() for c in camp_param.split(',') if c.strip().isdigit()]
                if c_ids:
                    where_clauses.append(f"ad.campaign_id IN ({','.join(['?']*len(c_ids))})")
                    where_vals.extend(c_ids)
            if adset_param:
                a_ids = [a.strip() for a in adset_param.split(',') if a.strip().isdigit()]
                if a_ids:
                    where_clauses.append(f"ad.ad_set_id IN ({','.join(['?']*len(a_ids))})")
                    where_vals.extend(a_ids)

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            query += " ORDER BY ad.id DESC"

            rows = cursor.execute(query, where_vals).fetchall()
            ads_list = []
            for r in rows:
                item = dict(r)
                spent = (item.get('spent_cents') or 0) / 100.0
                sales = cursor.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(price_in_cents), 0) as rev FROM orders WHERE utm_term = ? AND status = 'paid'", (item['name'],)).fetchone()
                sales_count = (item.get('sales_count') or 0) + (sales['cnt'] if sales else 0)
                revenue = ((item.get('revenue_cents') or 0) + (sales['rev'] if sales else 0)) / 100.0
                roas = round(revenue / spent, 2) if spent > 0 else 0
                cpa = round(spent / sales_count, 2) if sales_count > 0 else 0
                item['spent'] = spent
                item['sales'] = sales_count
                item['revenue'] = revenue
                item['roas'] = roas
                item['cpa'] = cpa
                ads_list.append(item)
            conn.close()
            self._send_json({"ads": ads_list})
            return

        # Regras de Automação
        if path == '/api/rules':
            conn = get_db()
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM automated_rules WHERE user_id = 1 ORDER BY id DESC").fetchall()
            conn.close()
            self._send_json({"rules": [dict(r) for r in rows]})
            return

        # Logs de Execução das Regras
        if path == '/api/rules/logs':
            conn = get_db()
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM rule_logs ORDER BY id DESC LIMIT 50").fetchall()
            conn.close()
            self._send_json({"logs": [dict(r) for r in rows]})
            return

        # Pixels Meta (Multi-Pixel)
        if path == '/api/pixels':
            conn = get_db()
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM meta_pixels WHERE user_id = 1 ORDER BY id DESC").fetchall()
            conn.close()
            self._send_json({"pixels": [dict(r) for r in rows]})
            return

        # Custom Dashboards / Workspaces
        if path == '/api/dashboards':
            conn = get_db()
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM custom_dashboards WHERE user_id = 1 ORDER BY id ASC").fetchall()
            conn.close()
            self._send_json({"dashboards": [dict(r) for r in rows]})
            return

        # Configurações Financeiras (Taxas e Impostos) - Consulta GET
        if path == '/api/settings/financial':
            conn = get_db()
            cursor = conn.cursor()
            fin = cursor.execute("SELECT * FROM financial_settings WHERE user_id = 1").fetchone()
            conn.close()
            self._send_json({
                "gateway_tax_percent": fin['gateway_tax_percent'] if fin else 8.9,
                "gateway_fixed_fee": fin['gateway_fixed_fee'] if fin else 2.49,
                "invoice_tax_percent": fin['invoice_tax_percent'] if fin else 6.0,
                "product_cost_percent": fin['product_cost_percent'] if fin else 0.0
            })
            return

        # Preferências do Usuário (Métricas e Colunas Visíveis) - Consulta GET
        if path == '/api/user/preferences':
            conn = get_db()
            cursor = conn.cursor()
            pref = cursor.execute("SELECT * FROM user_preferences WHERE user_id = 1").fetchone()
            conn.close()
            if pref:
                self._send_json({
                    "visible_metrics": json.loads(pref['visible_metrics']) if pref['visible_metrics'] else None,
                    "visible_columns": json.loads(pref['visible_columns']) if pref['visible_columns'] else None
                })
            else:
                self._send_json({"visible_metrics": None, "visible_columns": None})
            return

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
            logs = cursor.execute("SELECT * FROM capi_logs WHERE user_id = 1 ORDER BY id DESC LIMIT 30").fetchall()
            conn.close()
            self._send_json({"logs": [dict(l) for l in logs]})
            return

        # Serve static web application
        root_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
        demo_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'demo', 'index.html')
        html_to_serve = root_html if os.path.exists(root_html) else demo_html

        if path in ['/', '/index.html'] and os.path.exists(html_to_serve):
            with open(html_to_serve, 'r', encoding='utf-8') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
            return

        # 404
        self._send_json({"error": "Endpoint não encontrado"}, 404)

    def do_DELETE(self):
        return self.do_POST()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        # Configurar Meta CAPI
        # Configurações Financeiras (Taxas e Impostos) - Salvar
        if path == '/api/settings/financial':
            gw_pct = float(body.get('gateway_tax_percent', 8.9))
            gw_fix = float(body.get('gateway_fixed_fee', 2.49))
            inv_pct = float(body.get('invoice_tax_percent', 6.0))
            cost_pct = float(body.get('product_cost_percent', 0.0))
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO financial_settings (user_id, gateway_tax_percent, gateway_fixed_fee, invoice_tax_percent, product_cost_percent)
                VALUES (1, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    gateway_tax_percent = excluded.gateway_tax_percent,
                    gateway_fixed_fee = excluded.gateway_fixed_fee,
                    invoice_tax_percent = excluded.invoice_tax_percent,
                    product_cost_percent = excluded.product_cost_percent
            """, (gw_pct, gw_fix, inv_pct, cost_pct))
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Configurações de taxas salvas com sucesso!"})
            return

        # Preferências do Usuário (Métricas e Colunas Visíveis) - Salvar
        if path == '/api/user/preferences':
            visible_metrics = body.get('visible_metrics')
            visible_columns = body.get('visible_columns')
            vm_json = json.dumps(visible_metrics) if visible_metrics is not None else None
            vc_json = json.dumps(visible_columns) if visible_columns is not None else None
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_preferences (user_id, visible_metrics, visible_columns, updated_at)
                VALUES (1, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    visible_metrics = COALESCE(excluded.visible_metrics, user_preferences.visible_metrics),
                    visible_columns = COALESCE(excluded.visible_columns, user_preferences.visible_columns),
                    updated_at = CURRENT_TIMESTAMP
            """, (vm_json, vc_json))
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Preferências salvas com sucesso!"})
            return

        # Facebook Ad Accounts: Buscar contas via Graph API ou Assistente 1-clique
        if path == '/api/facebook/fetch_accounts':
            token = str(body.get('access_token', '')).strip()
            if token and not token.lower().startswith('demo'):
                try:
                    url = f"https://graph.facebook.com/v19.0/me/adaccounts?fields=id,account_id,name,currency,account_status,amount_spent&access_token={urllib.parse.quote(token)}&limit=100"
                    req = urllib.request.Request(url, headers={'User-Agent': 'TrackPro/2.5'})
                    with urllib.request.urlopen(req, timeout=12) as response:
                        res_data = json.loads(response.read().decode('utf-8'))
                        fb_accounts = []
                        for item in res_data.get('data', []):
                            status_str = 'ACTIVE' if item.get('account_status') == 1 else 'DISABLED'
                            fb_accounts.append({
                                'id': item.get('id'),
                                'account_id': item.get('account_id') or item.get('id', '').replace('act_', ''),
                                'name': item.get('name') or f"Conta Meta {item.get('account_id')}",
                                'currency': item.get('currency', 'BRL'),
                                'status': status_str,
                                'amount_spent': float(item.get('amount_spent', 0)) / 100.0 if item.get('amount_spent') else 0.0
                            })
                        self._send_json({"success": True, "source": "meta_graph_api", "accounts": fb_accounts})
                        return
                except Exception as e:
                    self._send_json({
                        "success": False,
                        "error": f"Erro no Graph API do Facebook: {str(e)}",
                        "fallback": True,
                        "suggested_accounts": [
                            {"account_id": "1092837465019", "name": "BM Principal (Escala Direta)", "currency": "BRL", "status": "ACTIVE", "amount_spent": 1420.50},
                            {"account_id": "2837465019283", "name": "BM Contingência 02 (Testes Criativos)", "currency": "BRL", "status": "ACTIVE", "amount_spent": 380.00},
                            {"account_id": "3746501928374", "name": "BM 03 - Remarketing & LTV", "currency": "BRL", "status": "ACTIVE", "amount_spent": 940.20}
                        ]
                    }, 200)
                    return
            else:
                suggested = [
                    {"account_id": "1092837465019", "name": "BM Principal (Escala Direta)", "currency": "BRL", "status": "ACTIVE", "amount_spent": 1420.50},
                    {"account_id": "2837465019283", "name": "BM Contingência 02 (Testes Criativos)", "currency": "BRL", "status": "ACTIVE", "amount_spent": 380.00},
                    {"account_id": "3746501928374", "name": "BM 03 - Remarketing & LTV", "currency": "BRL", "status": "ACTIVE", "amount_spent": 940.20}
                ]
                self._send_json({"success": True, "source": "quick_connect", "accounts": suggested})
                return

        # Facebook Ad Accounts: Bulk Import (1-clique)
        if path == '/api/facebook/accounts/bulk_import':
            accounts = body.get('accounts', [])
            token = body.get('access_token', '')
            if not isinstance(accounts, list) or len(accounts) == 0:
                self._send_json({"error": "Nenhuma conta fornecida para importação"}, 400)
                return

            conn = get_db()
            cursor = conn.cursor()
            imported_count = 0
            for acc in accounts:
                acc_id = str(acc.get('account_id') or acc.get('id', '')).replace('act_', '').strip()
                name = str(acc.get('name', '')).strip() or f"Conta Meta {acc_id}"
                currency = str(acc.get('currency', 'BRL')).strip()
                acc_token = str(acc.get('access_token') or token).strip()
                status = str(acc.get('status', 'ACTIVE')).strip()
                if acc_id:
                    exists = cursor.execute("SELECT id FROM facebook_ad_accounts WHERE account_id = ? AND user_id = 1", (acc_id,)).fetchone()
                    if exists:
                        cursor.execute("""
                            UPDATE facebook_ad_accounts 
                            SET name = ?, access_token = ?, currency = ?, status = ?
                            WHERE id = ?
                        """, (name, acc_token, currency, status, exists['id']))
                    else:
                        cursor.execute("""
                            INSERT INTO facebook_ad_accounts (user_id, account_id, name, access_token, currency, status)
                            VALUES (1, ?, ?, ?, ?, ?)
                        """, (acc_id, name, acc_token, currency, status))
                    imported_count += 1

            conn.commit()
            conn.close()
            self._send_json({"success": True, "imported_count": imported_count, "message": f"{imported_count} conta(s) conectada(s) com sucesso!"})
            return

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

        # Facebook Ad Accounts: Cadastrar / Atualizar
        if path == '/api/facebook/accounts':
            account_id = str(body.get('account_id', '')).strip()
            name = str(body.get('name', '')).strip() or f"Conta {account_id}"
            access_token = str(body.get('access_token', '')).strip()
            currency = str(body.get('currency', 'BRL')).strip()

            if not account_id:
                self._send_json({"error": "Account ID obrigatório"}, 400)
                return

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO facebook_ad_accounts (user_id, account_id, name, access_token, currency, status)
                VALUES (1, ?, ?, ?, ?, 'ACTIVE')
            """, (account_id, name, access_token, currency))
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": f"Conta de Anúncio {name} cadastrada com sucesso!"})
            return

        # Facebook Ad Accounts: Deletar
        if path in ['/api/facebook/accounts/delete', '/api/facebook/accounts/remove']:
            acc_id = body.get('id')
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM facebook_ad_accounts WHERE id = ? AND user_id = 1", (acc_id,))
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Conta removida com sucesso!"})
            return

        # Criar Campanha
        if path in ['/api/facebook/campaigns/create', '/api/campaigns/create']:
            name = body.get('name', '').strip() or f"Campanha Meta {datetime.now().strftime('%d/%m')}"
            budget = int(float(body.get('daily_budget', 50)) * 100)
            account_id = body.get('ad_account_id', '')

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO campaigns (user_id, name, platform, status, daily_budget_in_cents, total_spent_in_cents, ad_account_id)
                VALUES (1, ?, 'facebook', 'active', ?, 0, ?)
            """, (name, budget, account_id))
            camp_id = cursor.lastrowid

            # Cria conjunto padrão
            adset_uuid = f"ADSET-{uuid.uuid4().hex[:6].upper()}"
            adset_name = f"Conjunto Aberto - {name}"
            cursor.execute("""
                INSERT INTO ad_sets (campaign_id, external_id, name, status, daily_budget_cents, spent_cents)
                VALUES (?, ?, ?, 'active', ?, 0)
            """, (camp_id, adset_uuid, adset_name, budget))
            adset_id = cursor.lastrowid

            # Cria anúncio (criativo) padrão
            cursor.execute("""
                INSERT INTO ads (ad_set_id, campaign_id, name, status, creative_type, spent_cents, sales_count)
                VALUES (?, ?, ?, 'active', 'video', 0, 0)
            """, (adset_id, camp_id, f"Criativo 01 - Vídeo - {name}"))

            conn.commit()
            conn.close()
            self._send_json({"success": True, "campaign_id": camp_id, "message": f"Campanha {name} criada com sucesso!"})
            return

        # Seleção de Contas de Anúncio da Meta (is_selected)
        if path in ['/api/integrations/meta/ad-accounts/select', '/api/facebook/accounts/select']:
            selected_ids = body.get('selected_account_ids')
            account_id = body.get('account_id')
            is_selected = body.get('is_selected')

            conn = get_db()
            cursor = conn.cursor()

            if isinstance(selected_ids, list):
                cursor.execute("UPDATE facebook_ad_accounts SET is_selected = 0 WHERE user_id = 1")
                cleaned_ids = [str(a).replace('act_', '').strip() for a in selected_ids if a]
                if cleaned_ids:
                    placeholders = ','.join(['?'] * len(cleaned_ids))
                    cursor.execute(f"UPDATE facebook_ad_accounts SET is_selected = 1 WHERE user_id = 1 AND account_id IN ({placeholders})", cleaned_ids)
                conn.commit()
                conn.close()
                self._send_json({"success": True, "message": f"{len(cleaned_ids)} conta(s) selecionada(s) para tracking!"})
                return
            elif account_id is not None and is_selected is not None:
                clean_id = str(account_id).replace('act_', '').strip()
                val = 1 if is_selected else 0
                cursor.execute("UPDATE facebook_ad_accounts SET is_selected = ? WHERE user_id = 1 AND account_id = ?", (val, clean_id))
                conn.commit()
                conn.close()
                self._send_json({"success": True, "message": "Conta de anúncio atualizada!"})
                return
            else:
                conn.close()
                self._send_json({"error": "Parâmetros inválidos. Envie selected_account_ids ou account_id com is_selected."}, 400)
                return

        # Configurar Credenciais Oficiais Meta OAuth
        if path in ['/api/integrations/meta/config', '/api/auth/facebook/config']:
            app_id = body.get('app_id', '').strip()
            app_secret = body.get('app_secret', '').strip()
            redirect_uri = body.get('redirect_uri', '').strip()
            if not app_id or not app_secret:
                self._send_json({"error": "App ID e App Secret são obrigatórios"}, 400)
                return
            conn = get_db()
            conn.execute("""
                INSERT OR REPLACE INTO meta_oauth_config (id, app_id, app_secret, redirect_uri, updated_at)
                VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (app_id, app_secret, redirect_uri))
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Credenciais Meta salvas com sucesso!"})
            return

        # Desconectar Conta Meta e Revogar Permissões
        if path in ['/api/integrations/meta/disconnect', '/api/auth/facebook/disconnect']:
            conn = get_db()
            conn_row = conn.execute("SELECT access_token FROM facebook_connections WHERE user_id = 1 AND status = 'connected' ORDER BY id DESC LIMIT 1").fetchone()
            if conn_row and conn_row['access_token']:
                try:
                    call_meta_graph_api('me/permissions', method='DELETE', access_token=conn_row['access_token'])
                except Exception:
                    pass
            conn.execute("UPDATE facebook_connections SET status = 'disconnected' WHERE user_id = 1")
            conn.execute("UPDATE facebook_ad_accounts SET access_token = NULL WHERE user_id = 1")
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Conta Meta desconectada e permissões revogadas com sucesso."})
            return

        # Sincronização Real de Campanhas e Gastos com Paginação e Insights
        if path in ['/api/integrations/meta/sync', '/api/facebook/sync']:
            conn = get_db()
            cursor = conn.cursor()

            conn_row = cursor.execute("SELECT access_token FROM facebook_connections WHERE user_id = 1 AND status = 'connected' ORDER BY id DESC LIMIT 1").fetchone()
            fallback_token = conn_row['access_token'] if conn_row else None

            # Contas selecionadas
            accounts = cursor.execute("SELECT * FROM facebook_ad_accounts WHERE user_id = 1 AND is_selected = 1").fetchall()
            if not accounts:
                accounts = cursor.execute("SELECT * FROM facebook_ad_accounts WHERE user_id = 1 AND status = 'ACTIVE' LIMIT 1").fetchall()

            if not accounts:
                conn.close()
                self._send_json({"error": "Nenhuma conta de anúncio ativa ou selecionada para sincronizar."}, 400)
                return

            total_synced_campaigns = 0
            sync_errors = []

            for acc in accounts:
                acc_id = acc['account_id']
                token = acc['access_token'] or fallback_token
                if not token:
                    continue

                cursor.execute("UPDATE facebook_ad_accounts SET sync_status = 'syncing' WHERE id = ?", (acc['id'],))
                conn.commit()

                try:
                    # 1. Busca todas as campanhas com paginação
                    camps_raw = fetch_all_meta_pages(f"act_{acc_id}/campaigns", params={
                        'fields': 'id,name,status,effective_status,objective,created_time,updated_time,daily_budget,lifetime_budget',
                        'limit': '50'
                    }, access_token=token, max_pages=15)

                    # 2. Busca insights no nível de campanha com paginação (últimos 30 dias)
                    insights_raw = fetch_all_meta_pages(f"act_{acc_id}/insights", params={
                        'level': 'campaign',
                        'fields': 'campaign_id,campaign_name,impressions,reach,clicks,spend,ctr,cpc,cpm,frequency,actions,cost_per_action_type,date_start,date_stop',
                        'date_preset': 'last_30d',
                        'limit': '50'
                    }, access_token=token, max_pages=15)

                    # Indexa insights por campaign_id
                    insights_by_camp = {}
                    for ins in insights_raw:
                        c_id = ins.get('campaign_id')
                        if c_id:
                            insights_by_camp[c_id] = ins

                    for c in camps_raw:
                        c_ext_id = str(c.get('id', ''))
                        c_name = c.get('name', 'Campanha Meta')
                        eff_status = c.get('effective_status') or c.get('status', 'ACTIVE')
                        c_status = 'active' if eff_status == 'ACTIVE' else 'paused'
                        objective = c.get('objective', 'OUTCOME_SALES')
                        daily_b = int(float(c.get('daily_budget') or 5000))

                        ins = insights_by_camp.get(c_ext_id, {})
                        spend_float = float(ins.get('spend') or 0.0)
                        spend_cents = int(spend_float * 100)
                        impressions = int(ins.get('impressions') or 0)
                        reach = int(ins.get('reach') or 0)
                        clicks = int(ins.get('clicks') or 0)
                        ctr = float(ins.get('ctr') or 0.0)
                        cpc_cents = int(float(ins.get('cpc') or 0.0) * 100)
                        cpm_cents = int(float(ins.get('cpm') or 0.0) * 100)
                        freq = float(ins.get('frequency') or 1.0)
                        d_start = ins.get('date_start')
                        d_stop = ins.get('date_stop')

                        # Extrai conversões de compra
                        actions = ins.get('actions', [])
                        conversions = 0
                        if isinstance(actions, list):
                            for act in actions:
                                act_type = act.get('action_type', '')
                                if act_type in ['purchase', 'omni_purchase', 'offsite_conversion.fb_pixel_purchase']:
                                    conversions += int(act.get('value', 0))

                        # Extrai CPA de compra
                        cpa_cents = 0
                        cost_actions = ins.get('cost_per_action_type', [])
                        if isinstance(cost_actions, list):
                            for ca in cost_actions:
                                if ca.get('action_type') in ['purchase', 'omni_purchase', 'offsite_conversion.fb_pixel_purchase']:
                                    cpa_cents = int(float(ca.get('value', 0)) * 100)

                        if conversions > 0 and cpa_cents == 0:
                            cpa_cents = int(spend_cents / conversions)

                        # Salva / atualiza insights
                        if d_start and d_stop:
                            cursor.execute("""
                                INSERT INTO meta_campaign_insights (
                                    user_id, ad_account_id, campaign_id, campaign_name, impressions, reach, clicks,
                                    spend_cents, ctr, cpc_cents, cpm_cents, frequency, conversions, cost_per_conversion_cents,
                                    date_start, date_stop, synced_at
                                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                                ON CONFLICT(ad_account_id, campaign_id, date_start, date_stop) DO UPDATE SET
                                    impressions = excluded.impressions,
                                    reach = excluded.reach,
                                    clicks = excluded.clicks,
                                    spend_cents = excluded.spend_cents,
                                    ctr = excluded.ctr,
                                    cpc_cents = excluded.cpc_cents,
                                    cpm_cents = excluded.cpm_cents,
                                    frequency = excluded.frequency,
                                    conversions = excluded.conversions,
                                    cost_per_conversion_cents = excluded.cost_per_conversion_cents,
                                    synced_at = CURRENT_TIMESTAMP
                            """, (acc_id, c_ext_id, c_name, impressions, reach, clicks, spend_cents, ctr, cpc_cents, cpm_cents, freq, conversions, cpa_cents, d_start, d_stop))

                        # Salva / atualiza tabela campaigns
                        existing_c = cursor.execute("SELECT id FROM campaigns WHERE external_campaign_id = ? OR name = ?", (c_ext_id, c_name)).fetchone()
                        if existing_c:
                            cursor.execute("""
                                UPDATE campaigns
                                SET name = ?, status = ?, effective_status = ?, objective = ?, daily_budget_in_cents = ?,
                                    total_spent_in_cents = ?, ad_account_id = ?, external_campaign_id = ?,
                                    impressions = ?, clicks = ?, conversions = ?, cpa_cents = ?
                                WHERE id = ?
                            """, (c_name, c_status, eff_status, objective, daily_b, spend_cents, acc_id, c_ext_id, impressions, clicks, conversions, cpa_cents, existing_c['id']))
                        else:
                            cursor.execute("""
                                INSERT INTO campaigns (
                                    user_id, name, platform, status, effective_status, objective, daily_budget_in_cents,
                                    total_spent_in_cents, ad_account_id, external_campaign_id, impressions, clicks, conversions, cpa_cents
                                ) VALUES (1, ?, 'facebook', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (c_name, c_status, eff_status, objective, daily_b, spend_cents, acc_id, c_ext_id, impressions, clicks, conversions, cpa_cents))

                        total_synced_campaigns += 1

                    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute("UPDATE facebook_ad_accounts SET sync_status = 'ok', sync_error = NULL, last_sync_at = ? WHERE id = ?", (now_str, acc['id']))

                except Exception as e:
                    err_text = str(e)
                    sync_errors.append(f"Conta {acc_id}: {err_text}")
                    cursor.execute("UPDATE facebook_ad_accounts SET sync_status = 'error', sync_error = ? WHERE id = ?", (err_text, acc['id']))

            conn.commit()
            conn.close()

            if sync_errors and total_synced_campaigns == 0:
                self._send_json({"error": "Erro ao sincronizar com a Meta: " + "; ".join(sync_errors)}, 500)
            else:
                self._send_json({
                    "success": True,
                    "synced_campaigns": total_synced_campaigns,
                    "accounts_synced": len(accounts),
                    "message": f"{total_synced_campaigns} campanha(s) sincronizada(s) da Meta com sucesso!"
                })
            return

        # Ações em Massa (Bulk Actions para Campanhas, Conjuntos e Anúncios)
        if path == '/api/facebook/bulk_action':
            entity_type = body.get('entity_type', 'campaigns')
            action = body.get('action', '')
            ids = body.get('ids', [])
            budget_val = float(body.get('budget', 50.0))
            budget_cents = int(budget_val * 100)

            if not ids or not isinstance(ids, list):
                self._send_json({"error": "Nenhum item selecionado"}, 400)
                return

            conn = get_db()
            cursor = conn.cursor()
            placeholders = ','.join(['?'] * len(ids))

            if entity_type == 'campaigns':
                if action == 'delete':
                    cursor.execute(f"DELETE FROM campaigns WHERE id IN ({placeholders})", ids)
                    cursor.execute(f"DELETE FROM ad_sets WHERE campaign_id IN ({placeholders})", ids)
                    cursor.execute(f"DELETE FROM ads WHERE campaign_id IN ({placeholders})", ids)
                elif action == 'pause':
                    cursor.execute(f"UPDATE campaigns SET status = 'paused' WHERE id IN ({placeholders})", ids)
                    cursor.execute(f"UPDATE ad_sets SET status = 'paused' WHERE campaign_id IN ({placeholders})", ids)
                    cursor.execute(f"UPDATE ads SET status = 'paused' WHERE campaign_id IN ({placeholders})", ids)
                elif action == 'activate':
                    cursor.execute(f"UPDATE campaigns SET status = 'active' WHERE id IN ({placeholders})", ids)
                    cursor.execute(f"UPDATE ad_sets SET status = 'active' WHERE campaign_id IN ({placeholders})", ids)
                    cursor.execute(f"UPDATE ads SET status = 'active' WHERE campaign_id IN ({placeholders})", ids)
                elif action == 'budget':
                    cursor.execute(f"UPDATE campaigns SET daily_budget_in_cents = ? WHERE id IN ({placeholders})", [budget_cents] + ids)
                elif action == 'duplicate':
                    for c_id in ids:
                        c_orig = cursor.execute("SELECT * FROM campaigns WHERE id = ?", (c_id,)).fetchone()
                        if c_orig:
                            cursor.execute("""
                                INSERT INTO campaigns (user_id, name, platform, status, daily_budget_in_cents, total_spent_in_cents, ad_account_id)
                                VALUES (1, ?, ?, 'active', ?, 0, ?)
                            """, (f"[CÓPIA] {c_orig['name']}", c_orig['platform'], c_orig['daily_budget_in_cents'], c_orig['ad_account_id']))
                            new_c_id = cursor.lastrowid
                            orig_adsets = cursor.execute("SELECT * FROM ad_sets WHERE campaign_id = ?", (c_id,)).fetchall()
                            for oa in orig_adsets:
                                cursor.execute("""
                                    INSERT INTO ad_sets (campaign_id, external_id, name, status, daily_budget_cents, spent_cents)
                                    VALUES (?, ?, ?, 'active', ?, 0)
                                """, (new_c_id, f"ADSET-{uuid.uuid4().hex[:6].upper()}", f"[CÓPIA] {oa['name']}", oa['daily_budget_cents']))
                                new_a_id = cursor.lastrowid
                                orig_ads = cursor.execute("SELECT * FROM ads WHERE ad_set_id = ?", (oa['id'],)).fetchall()
                                for ad in orig_ads:
                                    cursor.execute("""
                                        INSERT INTO ads (ad_set_id, campaign_id, name, status, creative_type, spent_cents, sales_count)
                                        VALUES (?, ?, ?, 'active', ?, 0, 0)
                                    """, (new_a_id, new_c_id, f"[CÓPIA] {ad['name']}", ad['creative_type']))

            elif entity_type == 'adsets':
                if action == 'delete':
                    cursor.execute(f"DELETE FROM ad_sets WHERE id IN ({placeholders})", ids)
                    cursor.execute(f"DELETE FROM ads WHERE ad_set_id IN ({placeholders})", ids)
                elif action == 'pause':
                    cursor.execute(f"UPDATE ad_sets SET status = 'paused' WHERE id IN ({placeholders})", ids)
                    cursor.execute(f"UPDATE ads SET status = 'paused' WHERE ad_set_id IN ({placeholders})", ids)
                elif action == 'activate':
                    cursor.execute(f"UPDATE ad_sets SET status = 'active' WHERE id IN ({placeholders})", ids)
                    cursor.execute(f"UPDATE ads SET status = 'active' WHERE ad_set_id IN ({placeholders})", ids)
                elif action == 'budget':
                    cursor.execute(f"UPDATE ad_sets SET daily_budget_cents = ? WHERE id IN ({placeholders})", [budget_cents] + ids)
                elif action == 'duplicate':
                    for a_id in ids:
                        oa = cursor.execute("SELECT * FROM ad_sets WHERE id = ?", (a_id,)).fetchone()
                        if oa:
                            cursor.execute("""
                                INSERT INTO ad_sets (campaign_id, external_id, name, status, daily_budget_cents, spent_cents)
                                VALUES (?, ?, ?, 'active', ?, 0)
                            """, (oa['campaign_id'], f"ADSET-{uuid.uuid4().hex[:6].upper()}", f"[CÓPIA] {oa['name']}", oa['daily_budget_cents']))
                            new_a_id = cursor.lastrowid
                            orig_ads = cursor.execute("SELECT * FROM ads WHERE ad_set_id = ?", (a_id,)).fetchall()
                            for ad in orig_ads:
                                cursor.execute("""
                                    INSERT INTO ads (ad_set_id, campaign_id, name, status, creative_type, spent_cents, sales_count)
                                    VALUES (?, ?, ?, 'active', ?, 0, 0)
                                """, (new_a_id, oa['campaign_id'], f"[CÓPIA] {ad['name']}", ad['creative_type']))

            elif entity_type == 'ads':
                if action == 'delete':
                    cursor.execute(f"DELETE FROM ads WHERE id IN ({placeholders})", ids)
                elif action == 'pause':
                    cursor.execute(f"UPDATE ads SET status = 'paused' WHERE id IN ({placeholders})", ids)
                elif action == 'activate':
                    cursor.execute(f"UPDATE ads SET status = 'active' WHERE id IN ({placeholders})", ids)
                elif action == 'duplicate':
                    for ad_id in ids:
                        ad = cursor.execute("SELECT * FROM ads WHERE id = ?", (ad_id,)).fetchone()
                        if ad:
                            cursor.execute("""
                                INSERT INTO ads (ad_set_id, campaign_id, name, status, creative_type, spent_cents, sales_count)
                                VALUES (?, ?, ?, 'active', ?, 0, 0)
                            """, (ad['ad_set_id'], ad['campaign_id'], f"[CÓPIA] {ad['name']}", ad['creative_type']))

            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": f"Ação '{action}' aplicada com sucesso a {len(ids)} item(ns)!"})
            return

        # Alterar Status de Campanha (Ativar / Pausar)
        if path == '/api/facebook/campaigns/status':
            camp_id = body.get('id')
            new_status = str(body.get('status', 'active')).lower() # 'active' ou 'paused'

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE campaigns SET status = ? WHERE id = ?", (new_status, camp_id))
            conn.commit()
            conn.close()
            self._send_json({"success": True, "status": new_status, "message": f"Campanha alterada para {new_status.upper()}!"})
            return

        # Alterar Orçamento de Campanha
        if path == '/api/facebook/campaigns/budget':
            camp_id = body.get('id')
            new_budget_cents = int(float(body.get('daily_budget', 0)) * 100)

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE campaigns SET daily_budget_in_cents = ? WHERE id = ?", (new_budget_cents, camp_id))
            conn.commit()
            conn.close()
            self._send_json({"success": True, "daily_budget": new_budget_cents / 100.0, "message": "Orçamento atualizado!"})
            return

        # Duplicar Conjunto de Anúncio
        if path in ['/api/facebook/adsets/duplicate', '/api/adsets/duplicate']:
            adset_id = body.get('adset_id') or body.get('id')
            conn = get_db()
            cursor = conn.cursor()
            orig = cursor.execute("SELECT * FROM ad_sets WHERE id = ?", (adset_id,)).fetchone()
            if not orig:
                conn.close()
                self._send_json({"error": "Conjunto não encontrado"}, 404)
                return

            new_name = f"[CÓPIA] {orig['name']}"
            cursor.execute("""
                INSERT INTO ad_sets (campaign_id, external_id, name, status, daily_budget_cents, spent_cents, targeting_info)
                VALUES (?, ?, ?, 'active', ?, 0, ?)
            """, (orig['campaign_id'], f"ADSET-{uuid.uuid4().hex[:6].upper()}", new_name, orig['daily_budget_cents'], orig['targeting_info']))
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()
            self._send_json({"success": True, "new_adset_id": new_id, "name": new_name, "message": f"Conjunto '{new_name}' duplicado com sucesso!"})
            return

        # Duplicar Campanha Inteira
        if path in ['/api/facebook/campaigns/duplicate', '/api/campaigns/duplicate']:
            camp_id = body.get('campaign_id') or body.get('id')
            conn = get_db()
            cursor = conn.cursor()
            orig = cursor.execute("SELECT * FROM campaigns WHERE id = ?", (camp_id,)).fetchone()
            if not orig:
                conn.close()
                self._send_json({"error": "Campanha não encontrada"}, 404)
                return

            new_name = f"[CÓPIA] {orig['name']}"
            cursor.execute("""
                INSERT INTO campaigns (user_id, name, platform, status, daily_budget_in_cents, total_spent_in_cents, ad_account_id)
                VALUES (1, ?, ?, 'active', ?, 0, ?)
            """, (new_name, orig['platform'], orig['daily_budget_in_cents'], orig['ad_account_id']))
            new_camp_id = cursor.lastrowid

            # Duplica conjuntos da campanha
            adsets = cursor.execute("SELECT * FROM ad_sets WHERE campaign_id = ?", (camp_id,)).fetchall()
            for a in adsets:
                cursor.execute("""
                    INSERT INTO ad_sets (campaign_id, external_id, name, status, daily_budget_cents, spent_cents, targeting_info)
                    VALUES (?, ?, ?, 'active', ?, 0, ?)
                """, (new_camp_id, f"ADSET-{uuid.uuid4().hex[:6].upper()}", a['name'], a['daily_budget_cents'], a['targeting_info']))

            conn.commit()
            conn.close()
            self._send_json({"success": True, "new_campaign_id": new_camp_id, "name": new_name, "message": f"Campanha '{new_name}' duplicada com sucesso!"})
            return

        # Regras de Automação: Criar
        if path == '/api/rules':
            try:
                name = body.get('name', '').strip() or f"Regra Automação {datetime.now().strftime('%d/%m')}"
                metric = body.get('condition_metric', 'spent')
                op = body.get('condition_operator', '>=')
                val = float(body.get('condition_value', 0))
                
                sec_metric = body.get('condition_secondary_metric')
                sec_op = body.get('condition_secondary_operator', '=')
                sec_val = float(body.get('condition_secondary_value', 0)) if sec_metric else None

                pause_time = body.get('schedule_pause_time')
                resume_time = body.get('schedule_resume_time')

                action = body.get('action_type', 'PAUSE_CAMPAIGN')
                act_val = float(body.get('action_value', 20))
                target_type = body.get('target_type', 'campaign')

                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO automated_rules (
                        user_id, name, active, condition_metric, condition_operator, condition_value,
                        condition_secondary_metric, condition_secondary_operator, condition_secondary_value,
                        schedule_pause_time, schedule_resume_time, action_type, action_value, target_type
                    ) VALUES (1, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, metric, op, val, sec_metric, sec_op, sec_val, pause_time, resume_time, action, act_val, target_type))
                rule_id = cursor.lastrowid
                conn.commit()
                conn.close()

                self._send_json({"success": True, "rule_id": rule_id, "message": f"Regra '{name}' criada e ativada!"})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        # Regras de Automação: Alternar Ativo/Inativo
        if path == '/api/rules/toggle':
            rule_id = body.get('id')
            conn = get_db()
            cursor = conn.cursor()
            curr = cursor.execute("SELECT active FROM automated_rules WHERE id = ?", (rule_id,)).fetchone()
            if curr:
                new_act = 0 if curr['active'] == 1 else 1
                cursor.execute("UPDATE automated_rules SET active = ? WHERE id = ?", (new_act, rule_id))
                conn.commit()
                conn.close()
                self._send_json({"success": True, "active": new_act, "message": f"Regra {'ativada' if new_act else 'desativada'}!"})
                return
            conn.close()
            self._send_json({"error": "Regra não encontrada"}, 404)
            return

        # Regras de Automação: Deletar
        if path == '/api/rules/delete':
            rule_id = body.get('id')
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM automated_rules WHERE id = ?", (rule_id,))
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Regra excluída!"})
            return

        # Regras de Automação: Executar Avaliação Imediata
        if path == '/api/rules/evaluate':
            logs = evaluate_automated_rules()
            self._send_json({"success": True, "executed_logs": logs, "message": f"Avaliação concluída! {len(logs)} ação(ões) executada(s)."})
            return

        # Multi-Pixels: Cadastrar / Atualizar
        if path == '/api/pixels':
            name = body.get('name', '').strip() or 'Pixel Meta'
            pixel_id = str(body.get('pixel_id', '')).strip()
            access_token = str(body.get('access_token', '')).strip()
            test_code = str(body.get('test_event_code', '')).strip()
            is_default = 1 if body.get('is_default') else 0

            if not pixel_id:
                self._send_json({"error": "Pixel ID obrigatório"}, 400)
                return

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO meta_pixels (user_id, name, pixel_id, access_token, test_event_code, is_default)
                VALUES (1, ?, ?, ?, ?, ?)
            """, (name, pixel_id, access_token, test_code, is_default))
            pix_id = cursor.lastrowid
            conn.commit()
            conn.close()
            self._send_json({"success": True, "id": pix_id, "message": f"Pixel '{name}' cadastrado com sucesso!"})
            return

        # Multi-Pixels: Deletar
        if path == '/api/pixels/delete':
            pix_id = body.get('id')
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM meta_pixels WHERE id = ?", (pix_id,))
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Pixel excluído com sucesso!"})
            return

        # Multi-Dashboards: Criar
        if path == '/api/dashboards':
            name = body.get('name', '').strip() or 'Novo Workspace'
            platform_filter = body.get('platform_filter', 'all').strip()

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO custom_dashboards (user_id, name, platform_filter, is_default)
                VALUES (1, ?, ?, 0)
            """, (name, platform_filter))
            d_id = cursor.lastrowid
            conn.commit()
            conn.close()
            self._send_json({"success": True, "id": d_id, "name": name, "message": f"Dashboard '{name}' criada!"})
            return

        # Multi-Dashboards: Deletar
        if path == '/api/dashboards/delete':
            d_id = body.get('id')
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM custom_dashboards WHERE id = ? AND is_default = 0", (d_id,))
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Dashboard removida!"})
            return

        # Zerar / Resetar Dados de Teste
        if path in ['/api/reset', '/api/system/reset']:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM orders;")
            cursor.execute("DELETE FROM tracking_events;")
            cursor.execute("DELETE FROM capi_logs;")
            cursor.execute("DELETE FROM rule_logs;")
            cursor.execute("UPDATE campaigns SET total_spent_in_cents = 0;")
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Todos os pedidos e dados de teste foram zerados com sucesso!"})
            return

        # Ingestão de Webhooks
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
            p_lower = path.lower()
            if 'kiwify' in p_lower: parsed_order['platform'] = 'Kiwify'
            elif 'hotmart' in p_lower: parsed_order['platform'] = 'Hotmart'
            elif 'greenn' in p_lower: parsed_order['platform'] = 'Greenn'
            elif 'cakto' in p_lower: parsed_order['platform'] = 'Cakto'
            elif 'wiapy' in p_lower: parsed_order['platform'] = 'Wiapy'

            conn = get_db()
            cursor = conn.cursor()

            tr = parsed_order.get('tracking', {})
            cursor.execute("""
                INSERT INTO orders (
                    user_id, order_external_id, platform, status, customer_name,
                    customer_email, customer_phone, customer_ip, price_in_cents,
                    utm_source, utm_medium, utm_campaign, utm_content, utm_term,
                    src, sck, fbc, fbp
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                parsed_order['order_id'],
                parsed_order['platform'],
                parsed_order['status'],
                parsed_order['customer_name'],
                parsed_order['customer_email'],
                parsed_order.get('customer_phone'),
                self.client_address[0],
                parsed_order['price_cents'],
                tr.get('utm_source'),
                tr.get('utm_medium'),
                tr.get('utm_campaign'),
                tr.get('utm_content'),
                tr.get('utm_term'),
                tr.get('src'),
                tr.get('sck'),
                parsed_order.get('fbc'),
                parsed_order.get('fbp')
            ))
            new_order_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Disparo Meta CAPI
            capi_result = None
            if parsed_order['status'] == 'paid':
                capi_result = send_meta_capi(1, parsed_order)
                # Avalia regras de automação logo após a venda
                try:
                    evaluate_automated_rules()
                except Exception:
                    pass

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
            cursor.execute("""
                INSERT INTO tracking_events (user_id, event_type, utm_source, utm_medium, utm_campaign, utm_content, utm_term, src, sck, fbc, fbp, page_url, ip_address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
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

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def run_server(port=3001):
    init_db()
    server = ThreadedHTTPServer(('0.0.0.0', port), TrackProHandler)
    print(f"[TrackPro v2.5] Servidor Ativo em: http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3001))
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run_server(port)
