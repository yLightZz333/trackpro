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
        ('campaigns', 'external_campaign_id', 'TEXT')
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
        cursor.execute("INSERT OR REPLACE INTO meta_settings (user_id, pixel_id, access_token, test_event_code, active) VALUES (?, '', '', '', 1)", (user_id,))

    dash = cursor.execute("SELECT id FROM custom_dashboards WHERE name = 'Geral'").fetchone()
    if not dash:
        cursor.execute("INSERT INTO custom_dashboards (user_id, name, platform_filter, is_default) VALUES (1, 'Geral', 'all', 1)")

    conn.commit()
    conn.close()

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

        # Dashboard Overview API (com suporte a filtros por dashboard/workspace)
        if path in ['/api/dashboard', '/api/dashboard/overview']:
            conn = get_db()
            cursor = conn.cursor()
            
            platform_filter = params.get('platform', ['all'])[0]
            dash_id = params.get('dashboard_id', [''])[0]
            if dash_id:
                d_row = cursor.execute("SELECT platform_filter FROM custom_dashboards WHERE id = ?", (dash_id,)).fetchone()
                if d_row and d_row['platform_filter']:
                    platform_filter = d_row['platform_filter']

            where_clause = ""
            where_params = []
            if platform_filter and platform_filter != 'all':
                where_clause = "WHERE platform = ?"
                where_params = [platform_filter]

            if where_clause:
                paid_filter = where_clause + " AND status = 'paid'"
            else:
                paid_filter = "WHERE status = 'paid'"
            query_paid = f"SELECT COALESCE(SUM(price_in_cents), 0) as total, COUNT(*) as count FROM orders {paid_filter}"
            row_paid = cursor.execute(query_paid, where_params).fetchone()
            tot_revenue = (row_paid['total'] or 0) / 100.0
            paid_ord = row_paid['count'] or 0

            row_spent = cursor.execute("SELECT COALESCE(SUM(total_spent_in_cents), 0) as total FROM campaigns").fetchone()
            tot_spent = (row_spent['total'] or 0) / 100.0

            roas = round(tot_revenue / tot_spent, 2) if tot_spent > 0 else 0
            cpa = round(tot_spent / paid_ord, 2) if paid_ord > 0 else 0
            roi = round(((tot_revenue - tot_spent) / tot_spent) * 100, 1) if tot_spent > 0 else 0

            # Fontes de tráfego
            query_sources = f"SELECT utm_source, COUNT(*) as count, SUM(price_in_cents) as total FROM orders {paid_filter} GROUP BY utm_source"
            sources_rows = cursor.execute(query_sources, where_params).fetchall()
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
                {where_clause}
                ORDER BY o.created_at DESC LIMIT 15
            """
            recent_rows = cursor.execute(query_orders, where_params).fetchall()
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
            camp_rows = cursor.execute("SELECT * FROM campaigns ORDER BY total_spent_in_cents DESC").fetchall()
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

            conn.close()

            resp = {
                "kpis": {
                    "faturamento": tot_revenue,
                    "gastoAds": tot_spent,
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

        # Conjuntos de Anúncio isolados
        if path in ['/api/facebook/adsets', '/api/adsets']:
            conn = get_db()
            cursor = conn.cursor()
            camp_id = params.get('campaign_id', [''])[0]
            if camp_id:
                rows = cursor.execute("SELECT * FROM ad_sets WHERE campaign_id = ?", (camp_id,)).fetchall()
            else:
                rows = cursor.execute("SELECT a.*, c.name as campaign_name FROM ad_sets a LEFT JOIN campaigns c ON a.campaign_id = c.id").fetchall()
            conn.close()
            self._send_json({"adsets": [dict(r) for r in rows]})
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

        # Configurar Meta CAPI
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
            cursor.execute("""
                INSERT INTO ad_sets (campaign_id, external_id, name, status, daily_budget_cents, spent_cents)
                VALUES (?, ?, ?, 'active', ?, 0)
            """, (camp_id, f"ADSET-{uuid.uuid4().hex[:6].upper()}", f"Conjunto Aberto - {name}", budget))

            conn.commit()
            conn.close()
            self._send_json({"success": True, "campaign_id": camp_id, "message": f"Campanha {name} criada com sucesso!"})
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
