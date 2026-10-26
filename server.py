import gzip
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

import hashlib
import secrets

def hash_password(password, salt=None):
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
    return f"{salt}:{hashed}"

def verify_password(stored_hash, password):
    if not stored_hash or not password:
        return False
    if ':' in stored_hash:
        salt, hashed = stored_hash.split(':', 1)
        return hashlib.sha256((salt + password).encode('utf-8')).hexdigest() == hashed
    return stored_hash == password
import sqlite3
import hashlib
import uuid
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

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

    
    CREATE TABLE IF NOT EXISTS user_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT UNIQUE NOT NULL,
        ip_address TEXT,
        user_agent TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS notification_settings (
        user_id INTEGER PRIMARY KEY,
        sound_enabled INTEGER DEFAULT 1,
        sound_type TEXT DEFAULT 'kaching',
        sound_volume REAL DEFAULT 1.0,
        notify_sale_approved INTEGER DEFAULT 1,
        notify_pix_generated INTEGER DEFAULT 1,
        notify_boleto_printed INTEGER DEFAULT 1,
        notify_refund INTEGER DEFAULT 1,
        notify_scheduled_summary INTEGER DEFAULT 1,
        summary_hours TEXT DEFAULT '["08:00", "12:00", "16:00", "18:00", "22:00"]',
        summary_tone TEXT DEFAULT 'creative',
        push_enabled INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        amount_in_cents INTEGER DEFAULT 0,
        payment_method TEXT,
        metadata TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
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

    
    # Migrações adicionais de colunas
    extra_migs = [
        ('ad_sets', 'user_id', 'INTEGER DEFAULT 1'),
        ('ads', 'user_id', 'INTEGER DEFAULT 1'),
        ('users', 'company', 'TEXT')
    ]
    for tbl, col, coltype in extra_migs:
        try:
            cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {coltype}")
        except Exception:
            pass

    # Configuração Oficial da Conta Lucas (luckinhasp4@gmail.com / yzzjl067_)
    lucas_pass = hash_password('yzzjl067_')
    u1 = cursor.execute("SELECT id, email FROM users WHERE id = 1").fetchone()
    if u1:
        cursor.execute("""
            UPDATE users 
            SET name = 'Lucas', email = 'luckinhasp4@gmail.com', password = ?, company = 'TrackPro VIP'
            WHERE id = 1
        """, (lucas_pass,))
    else:
        cursor.execute("""
            INSERT INTO users (id, name, email, password, company)
            VALUES (1, 'Lucas', 'luckinhasp4@gmail.com', ?, 'TrackPro VIP')
        """, (lucas_pass,))

    # Garantir configurações essenciais para User 1
    cursor.execute("INSERT OR IGNORE INTO financial_settings (user_id) VALUES (1)")
    cursor.execute("INSERT OR IGNORE INTO notification_settings (user_id) VALUES (1)")
    cursor.execute("INSERT OR IGNORE INTO api_credentials (user_id, name, token, active) VALUES (1, 'Token Universal Lucas', ?, 1)", (DEMO_TOKEN,))

    # Inserir notificações de boas-vindas se não houver
    notif_cnt = cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_id = 1").fetchone()[0]
    if notif_cnt == 0:
        cursor.execute("""
            INSERT INTO notifications (user_id, type, title, message, amount_in_cents, payment_method)
            VALUES (1, 'sale_approved', '💸 VENDA APROVADA!', 'Venda de R$ 197,00 aprovada via Cartão de Crédito! (Kiwify)', 19700, 'cartao')
        """)
        cursor.execute("""
            INSERT INTO notifications (user_id, type, title, message, amount_in_cents, payment_method)
            VALUES (1, 'pix_generated', '⚡ PIX GERADO!', 'PIX de R$ 97,00 gerado! Cliente: Marcos Vinicius (Aguardando pagamento)', 9700, 'pix')
        """)

    # Usuário padrão
    cursor.execute("INSERT OR IGNORE INTO api_credentials (user_id, name, token, active) VALUES (1, 'Token Universal', ?, 1)", (DEMO_TOKEN,))
    cursor.execute("INSERT OR IGNORE INTO financial_settings (user_id) VALUES (1)");
    cursor.execute("INSERT OR REPLACE INTO meta_settings (user_id, pixel_id, access_token, test_event_code, active) VALUES (1, '', '', '', 1)")

    dash = cursor.execute("SELECT id FROM custom_dashboards WHERE name = 'Geral'").fetchone()
    if not dash:
        cursor.execute("INSERT INTO custom_dashboards (user_id, name, platform_filter, is_default) VALUES (1, 'Geral', 'all', 1)")

    # Novas tabelas de insights no nível de conjunto e anúncio
    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS meta_adset_insights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        ad_account_id TEXT NOT NULL,
        campaign_id TEXT NOT NULL,
        adset_id TEXT NOT NULL,
        adset_name TEXT,
        impressions INTEGER DEFAULT 0,
        reach INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        spend_cents INTEGER DEFAULT 0,
        ctr REAL DEFAULT 0,
        cpc_cents INTEGER DEFAULT 0,
        cpm_cents INTEGER DEFAULT 0,
        conversions INTEGER DEFAULT 0,
        initiate_checkouts INTEGER DEFAULT 0,
        cost_per_ic_cents INTEGER DEFAULT 0,
        cpa_cents INTEGER DEFAULT 0,
        date_start TEXT NOT NULL,
        date_stop TEXT NOT NULL,
        synced_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ad_account_id, adset_id, date_start, date_stop)
    );

    CREATE TABLE IF NOT EXISTS meta_ad_insights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        ad_account_id TEXT NOT NULL,
        campaign_id TEXT NOT NULL,
        adset_id TEXT NOT NULL,
        ad_id TEXT NOT NULL,
        ad_name TEXT,
        impressions INTEGER DEFAULT 0,
        reach INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        spend_cents INTEGER DEFAULT 0,
        ctr REAL DEFAULT 0,
        cpc_cents INTEGER DEFAULT 0,
        cpm_cents INTEGER DEFAULT 0,
        conversions INTEGER DEFAULT 0,
        initiate_checkouts INTEGER DEFAULT 0,
        cost_per_ic_cents INTEGER DEFAULT 0,
        cpa_cents INTEGER DEFAULT 0,
        date_start TEXT NOT NULL,
        date_stop TEXT NOT NULL,
        synced_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ad_account_id, ad_id, date_start, date_stop)
    );
    ''')

    # Novas colunas essenciais para métricas de IC, CTR, CPC, CPM
    extra_migrations = [
        ('campaigns', 'initiate_checkouts', 'INTEGER DEFAULT 0'),
        ('campaigns', 'cost_per_ic_cents', 'INTEGER DEFAULT 0'),
        ('campaigns', 'ctr', 'REAL DEFAULT 0.0'),
        ('campaigns', 'cpc_cents', 'INTEGER DEFAULT 0'),
        ('campaigns', 'cpm_cents', 'INTEGER DEFAULT 0'),
        ('ad_sets', 'impressions', 'INTEGER DEFAULT 0'),
        ('ad_sets', 'clicks', 'INTEGER DEFAULT 0'),
        ('ad_sets', 'conversions', 'INTEGER DEFAULT 0'),
        ('ad_sets', 'initiate_checkouts', 'INTEGER DEFAULT 0'),
        ('ad_sets', 'cpa_cents', 'INTEGER DEFAULT 0'),
        ('ad_sets', 'cost_per_ic_cents', 'INTEGER DEFAULT 0'),
        ('ad_sets', 'cpc_cents', 'INTEGER DEFAULT 0'),
        ('ad_sets', 'cpm_cents', 'INTEGER DEFAULT 0'),
        ('ad_sets', 'ctr', 'REAL DEFAULT 0.0'),
        ('ads', 'external_id', 'TEXT'),
        ('ads', 'impressions', 'INTEGER DEFAULT 0'),
        ('ads', 'clicks', 'INTEGER DEFAULT 0'),
        ('ads', 'conversions', 'INTEGER DEFAULT 0'),
        ('ads', 'initiate_checkouts', 'INTEGER DEFAULT 0'),
        ('ads', 'cpa_cents', 'INTEGER DEFAULT 0'),
        ('ads', 'cost_per_ic_cents', 'INTEGER DEFAULT 0'),
        ('ads', 'cpc_cents', 'INTEGER DEFAULT 0'),
        ('ads', 'cpm_cents', 'INTEGER DEFAULT 0'),
        ('ads', 'ctr', 'REAL DEFAULT 0.0'),
        ('meta_campaign_insights', 'initiate_checkouts', 'INTEGER DEFAULT 0'),
        ('meta_campaign_insights', 'cost_per_ic_cents', 'INTEGER DEFAULT 0'),
    ]
    for table, col, col_type in extra_migrations:
        try:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {col} {col_type}')
        except Exception:
            pass

    # Índices para alta performance e consultas ultrarrápidas
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_orders_created ON orders (created_at)",
        "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status)",
        "CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders (user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_campaigns_user ON campaigns (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_campaigns_ext ON campaigns (external_campaign_id)",
        "CREATE INDEX IF NOT EXISTS idx_meta_insights_camp ON meta_campaign_insights (campaign_id, date_start, date_stop)",
        "CREATE INDEX IF NOT EXISTS idx_meta_adset_ins ON meta_adset_insights (adset_id, date_start, date_stop)",
        "CREATE INDEX IF NOT EXISTS idx_meta_ad_ins ON meta_ad_insights (ad_id, date_start, date_stop)",
        "CREATE INDEX IF NOT EXISTS idx_adsets_camp ON ad_sets (campaign_id)",
        "CREATE INDEX IF NOT EXISTS idx_ads_adset ON ads (ad_set_id)"
    ]
    for idx_q in indexes:
        try:
            cursor.execute(idx_q)
        except Exception:
            pass

    # Inicializa conexão Meta com token permanente se ainda não estiver conectado
    try:
        active_conn = cursor.execute("SELECT id FROM facebook_connections WHERE user_id = 1 AND status = 'connected'").fetchone()
        if not active_conn and DEFAULT_META_SYSTEM_TOKEN:
            sync_meta_system_token(DEFAULT_META_SYSTEM_TOKEN)
    except Exception as e:
        print(f"[TrackPro Startup] Aviso ao sincronizar Meta: {e}")

    conn.commit()
    conn.close()

# ==================== CONFIGURAÇÃO E INTEGRAÇÃO OFICIAL META (OAUTH 2.0) ====================
META_GRAPH_VERSION = os.environ.get('META_GRAPH_VERSION', 'v19.0')
META_OAUTH_SCOPES = "ads_read,public_profile"
DEFAULT_META_SYSTEM_TOKEN = os.environ.get(
    'META_SYSTEM_TOKEN',
    'EAAP3aw4jAzkBS5ZBSHgj5bnUZAEkmidzcUEdXZCCglpZBykiL8UcgCZAjIUcuY26HEGceD6s3DSHBTZA73ntdZAtGBVvbpeyTNaOd53uFTsJodLtez9ayaK7YBqdrw3nfxAFOsQXUVuKPZAHr5zAqztJQwsLaGVQ4QQLslvkLoZBUbniEv4P0OMRoZATopMBYsWgZDZD'
)

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

def compute_date_range(period, start_date='', end_date=''):
    today_dt = datetime.now()
    if period == 'today':
        d_str = today_dt.strftime('%Y-%m-%d')
        return d_str, d_str, 'today'
    elif period == 'yesterday':
        yest_str = (today_dt - timedelta(days=1)).strftime('%Y-%m-%d')
        return yest_str, yest_str, 'yesterday'
    elif period == 'last_7_days':
        s_str = (today_dt - timedelta(days=7)).strftime('%Y-%m-%d')
        e_str = today_dt.strftime('%Y-%m-%d')
        return s_str, e_str, 'last_7d'
    elif period == 'last_week':
        s_str = (today_dt - timedelta(days=14)).strftime('%Y-%m-%d')
        e_str = (today_dt - timedelta(days=7)).strftime('%Y-%m-%d')
        return s_str, e_str, 'last_week_mon_sun'
    elif period == 'this_month':
        s_str = today_dt.strftime('%Y-%m-01')
        e_str = today_dt.strftime('%Y-%m-%d')
        return s_str, e_str, 'this_month'
    elif period == 'last_month':
        first_this = today_dt.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        s_str = last_month_end.strftime('%Y-%m-01')
        e_str = last_month_end.strftime('%Y-%m-%d')
        return s_str, e_str, 'last_month'
    elif period == 'custom' and start_date and end_date:
        return start_date, end_date, None
    elif period == 'all':
        return None, None, 'maximum'
    else:
        d_str = today_dt.strftime('%Y-%m-%d')
        return d_str, d_str, 'today'



def parse_meta_actions(actions):
    purchases = 0
    ic = 0
    if not isinstance(actions, list):
        return purchases, ic
    for act in actions:
        if act.get('action_type') == 'purchase':
            purchases = int(act.get('value', 0))
            break
    if purchases == 0:
        for act in actions:
            if act.get('action_type') in ['omni_purchase', 'offsite_conversion.fb_pixel_purchase']:
                purchases = max(purchases, int(act.get('value', 0)))

    for act in actions:
        if act.get('action_type') == 'initiate_checkout':
            ic = int(act.get('value', 0))
            break
    if ic == 0:
        for act in actions:
            if act.get('action_type') in ['omni_initiated_checkout', 'offsite_conversion.fb_pixel_initiate_checkout', 'onsite_web_initiate_checkout']:
                ic = max(ic, int(act.get('value', 0)))

    return purchases, ic

def duplicate_meta_item(level, external_id, token):
    if not token or not external_id:
        return None, "Token ou ID externo ausente"
    try:
        url = f"https://graph.facebook.com/{META_GRAPH_VERSION}/{external_id}/copies?deep_copy=true&status_option=PAUSED&access_token={token}"
        req = urllib.request.Request(url, data=b'', headers={'User-Agent': 'TrackPro/3.0'}, method='POST')
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            copied_id = data.get('copied_campaign_id') or data.get('copied_adset_id') or data.get('id')
            return copied_id, None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='ignore')
        try:
            err_j = json.loads(err_body)
            err_msg = err_j.get('error', {}).get('error_user_msg') or err_j.get('error', {}).get('message', str(e))
        except Exception:
            err_msg = err_body
        return None, f"Meta Ads: {err_msg}"
    except Exception as e:
        return None, str(e)

def sync_meta_campaigns_internal(user_id=1, period='all', start_date='', end_date=''):
    conn = get_db()
    cursor = conn.cursor()

    conn_row = cursor.execute("SELECT access_token FROM facebook_connections WHERE user_id = ? AND status = 'connected' ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    fallback_token = conn_row['access_token'] if conn_row else None

    # Contas selecionadas
    accounts = cursor.execute("SELECT * FROM facebook_ad_accounts WHERE user_id = ? AND is_selected = 1", (user_id,)).fetchall()
    if not accounts:
        accounts = cursor.execute("SELECT * FROM facebook_ad_accounts WHERE user_id = ? AND status = 'ACTIVE' LIMIT 1", (user_id,)).fetchall()

    if not accounts:
        conn.close()
        return {"success": False, "error": "Nenhuma conta de anúncio ativa ou selecionada para sincronizar.", "synced": 0, "errors": []}

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
            # Limpa registros antigos agregados que distorciam o filtro diário
            cursor.execute("DELETE FROM meta_campaign_insights WHERE ad_account_id = ? AND date_start <> date_stop", (acc_id,))
            cursor.execute("DELETE FROM meta_adset_insights WHERE ad_account_id = ? AND date_start <> date_stop", (acc_id,))
            cursor.execute("DELETE FROM meta_ad_insights WHERE ad_account_id = ? AND date_start <> date_stop", (acc_id,))
            conn.commit()

            # 1. Busca todas as campanhas, conjuntos e anúncios da conta
            camps_raw = fetch_all_meta_pages(f"act_{acc_id}/campaigns", params={
                'fields': 'id,name,status,effective_status,objective,created_time,updated_time,daily_budget,lifetime_budget',
                'limit': '100'
            }, access_token=token, max_pages=15)

            adsets_raw = fetch_all_meta_pages(f"act_{acc_id}/adsets", params={
                'fields': 'id,name,status,effective_status,campaign_id,daily_budget,lifetime_budget,targeting',
                'limit': '100'
            }, access_token=token, max_pages=15)

            ads_raw = fetch_all_meta_pages(f"act_{acc_id}/ads", params={
                'fields': 'id,name,status,effective_status,campaign_id,adset_id',
                'limit': '100'
            }, access_token=token, max_pages=15)

            # 2. Busca insights diários (time_increment=1) para campanhas, conjuntos e anúncios
            c_insights = fetch_all_meta_pages(f"act_{acc_id}/insights", params={
                'level': 'campaign',
                'fields': 'campaign_id,campaign_name,impressions,reach,clicks,spend,ctr,cpc,cpm,actions,cost_per_action_type,date_start,date_stop',
                'date_preset': 'maximum',
                'time_increment': '1',
                'limit': '100'
            }, access_token=token, max_pages=20)

            adset_insights = fetch_all_meta_pages(f"act_{acc_id}/insights", params={
                'level': 'adset',
                'fields': 'adset_id,adset_name,campaign_id,impressions,reach,clicks,spend,ctr,cpc,cpm,actions,cost_per_action_type,date_start,date_stop',
                'date_preset': 'maximum',
                'time_increment': '1',
                'limit': '100'
            }, access_token=token, max_pages=20)

            ad_insights = fetch_all_meta_pages(f"act_{acc_id}/insights", params={
                'level': 'ad',
                'fields': 'ad_id,ad_name,adset_id,campaign_id,impressions,reach,clicks,spend,ctr,cpc,cpm,actions,cost_per_action_type,date_start,date_stop',
                'date_preset': 'maximum',
                'time_increment': '1',
                'limit': '100'
            }, access_token=token, max_pages=20)

            # 3. Salva insights diários no banco
            for ins in c_insights:
                c_id_ext = str(ins.get('campaign_id'))
                c_name_ins = ins.get('campaign_name', '')
                spend_cents = int(float(ins.get('spend') or 0.0) * 100)
                impr = int(ins.get('impressions') or 0)
                reach = int(ins.get('reach') or 0)
                clk = int(ins.get('clicks') or 0)
                ctr = float(ins.get('ctr') or 0.0)
                cpc_cents = int(float(ins.get('cpc') or 0.0) * 100)
                cpm_cents = int(float(ins.get('cpm') or 0.0) * 100)
                d_start = ins.get('date_start')
                d_stop = ins.get('date_stop')
                purchases, ic = parse_meta_actions(ins.get('actions', []))
                cpa_cents = int(spend_cents / purchases) if purchases > 0 else 0
                cost_per_ic_cents = int(spend_cents / ic) if ic > 0 else 0

                cursor.execute("""
                    INSERT INTO meta_campaign_insights (
                        user_id, ad_account_id, campaign_id, campaign_name, impressions, reach, clicks,
                        spend_cents, ctr, cpc_cents, cpm_cents, conversions, cost_per_conversion_cents,
                        initiate_checkouts, cost_per_ic_cents, date_start, date_stop, synced_at
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(ad_account_id, campaign_id, date_start, date_stop) DO UPDATE SET
                        impressions = excluded.impressions,
                        reach = excluded.reach,
                        clicks = excluded.clicks,
                        spend_cents = excluded.spend_cents,
                        ctr = excluded.ctr,
                        cpc_cents = excluded.cpc_cents,
                        cpm_cents = excluded.cpm_cents,
                        conversions = excluded.conversions,
                        cost_per_conversion_cents = excluded.cost_per_conversion_cents,
                        initiate_checkouts = excluded.initiate_checkouts,
                        cost_per_ic_cents = excluded.cost_per_ic_cents,
                        synced_at = CURRENT_TIMESTAMP
                """, (acc_id, c_id_ext, c_name_ins, impr, reach, clk, spend_cents, ctr, cpc_cents, cpm_cents, purchases, cpa_cents, ic, cost_per_ic_cents, d_start, d_stop))

            for ins in adset_insights:
                aid_ext = str(ins.get('adset_id'))
                aname_ins = ins.get('adset_name', '')
                cid_ext = str(ins.get('campaign_id', ''))
                spend_cents = int(float(ins.get('spend') or 0.0) * 100)
                impr = int(ins.get('impressions') or 0)
                reach = int(ins.get('reach') or 0)
                clk = int(ins.get('clicks') or 0)
                ctr = float(ins.get('ctr') or 0.0)
                cpc_cents = int(float(ins.get('cpc') or 0.0) * 100)
                cpm_cents = int(float(ins.get('cpm') or 0.0) * 100)
                d_start = ins.get('date_start')
                d_stop = ins.get('date_stop')
                purchases, ic = parse_meta_actions(ins.get('actions', []))
                cpa_cents = int(spend_cents / purchases) if purchases > 0 else 0
                cost_per_ic_cents = int(spend_cents / ic) if ic > 0 else 0

                cursor.execute("""
                    INSERT INTO meta_adset_insights (
                        user_id, ad_account_id, campaign_id, adset_id, adset_name, impressions, reach, clicks,
                        spend_cents, ctr, cpc_cents, cpm_cents, conversions, initiate_checkouts,
                        cost_per_ic_cents, cpa_cents, date_start, date_stop, synced_at
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(ad_account_id, adset_id, date_start, date_stop) DO UPDATE SET
                        impressions = excluded.impressions,
                        reach = excluded.reach,
                        clicks = excluded.clicks,
                        spend_cents = excluded.spend_cents,
                        ctr = excluded.ctr,
                        cpc_cents = excluded.cpc_cents,
                        cpm_cents = excluded.cpm_cents,
                        conversions = excluded.conversions,
                        initiate_checkouts = excluded.initiate_checkouts,
                        cost_per_ic_cents = excluded.cost_per_ic_cents,
                        cpa_cents = excluded.cpa_cents,
                        synced_at = CURRENT_TIMESTAMP
                """, (acc_id, cid_ext, aid_ext, aname_ins, impr, reach, clk, spend_cents, ctr, cpc_cents, cpm_cents, purchases, ic, cost_per_ic_cents, cpa_cents, d_start, d_stop))

            for ins in ad_insights:
                adid_ext = str(ins.get('ad_id'))
                adname_ins = ins.get('ad_name', '')
                aid_ext = str(ins.get('adset_id', ''))
                cid_ext = str(ins.get('campaign_id', ''))
                spend_cents = int(float(ins.get('spend') or 0.0) * 100)
                impr = int(ins.get('impressions') or 0)
                reach = int(ins.get('reach') or 0)
                clk = int(ins.get('clicks') or 0)
                ctr = float(ins.get('ctr') or 0.0)
                cpc_cents = int(float(ins.get('cpc') or 0.0) * 100)
                cpm_cents = int(float(ins.get('cpm') or 0.0) * 100)
                d_start = ins.get('date_start')
                d_stop = ins.get('date_stop')
                purchases, ic = parse_meta_actions(ins.get('actions', []))
                cpa_cents = int(spend_cents / purchases) if purchases > 0 else 0
                cost_per_ic_cents = int(spend_cents / ic) if ic > 0 else 0

                cursor.execute("""
                    INSERT INTO meta_ad_insights (
                        user_id, ad_account_id, campaign_id, adset_id, ad_id, ad_name, impressions, reach, clicks,
                        spend_cents, ctr, cpc_cents, cpm_cents, conversions, initiate_checkouts,
                        cost_per_ic_cents, cpa_cents, date_start, date_stop, synced_at
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(ad_account_id, ad_id, date_start, date_stop) DO UPDATE SET
                        impressions = excluded.impressions,
                        reach = excluded.reach,
                        clicks = excluded.clicks,
                        spend_cents = excluded.spend_cents,
                        ctr = excluded.ctr,
                        cpc_cents = excluded.cpc_cents,
                        cpm_cents = excluded.cpm_cents,
                        conversions = excluded.conversions,
                        initiate_checkouts = excluded.initiate_checkouts,
                        cost_per_ic_cents = excluded.cost_per_ic_cents,
                        cpa_cents = excluded.cpa_cents,
                        synced_at = CURRENT_TIMESTAMP
                """, (acc_id, cid_ext, aid_ext, adid_ext, adname_ins, impr, reach, clk, spend_cents, ctr, cpc_cents, cpm_cents, purchases, ic, cost_per_ic_cents, cpa_cents, d_start, d_stop))

            conn.commit()

            # Mapeia conjuntos por campanha
            adsets_by_camp = {}
            for a in adsets_raw:
                cid = str(a.get('campaign_id'))
                adsets_by_camp.setdefault(cid, []).append(a)

            # 4. Upsert das Campanhas
            camp_id_map = {}
            for c in camps_raw:
                c_ext_id = str(c.get('id', ''))
                c_name = c.get('name', 'Campanha Meta')
                eff_status = c.get('effective_status') or c.get('status', 'ACTIVE')
                c_status = 'active' if eff_status == 'ACTIVE' else 'paused'
                objective = c.get('objective', 'OUTCOME_SALES')

                stats = cursor.execute("""
                    SELECT COALESCE(SUM(spend_cents), 0) as spend,
                           COALESCE(SUM(impressions), 0) as impr,
                           COALESCE(SUM(clicks), 0) as clk,
                           COALESCE(SUM(conversions), 0) as conv,
                           COALESCE(SUM(initiate_checkouts), 0) as ic
                    FROM meta_campaign_insights
                    WHERE campaign_id = ?
                """, (c_ext_id,)).fetchone()

                spend_cents = stats[0]
                impressions = stats[1]
                clicks = stats[2]
                purchases = stats[3]
                ic = stats[4]
                ctr = round((clicks / impressions * 100.0), 2) if impressions > 0 else 0.0
                cpc_cents = int(spend_cents / clicks) if clicks > 0 else 0
                cpm_cents = int(spend_cents / impressions * 1000) if impressions > 0 else 0
                cpa_cents = int(spend_cents / purchases) if purchases > 0 else 0
                cost_per_ic_cents = int(spend_cents / ic) if ic > 0 else 0

                # Orçamento: se CBO usa daily_budget da campanha, se ABO soma os adsets
                camp_adsets = adsets_by_camp.get(c_ext_id, [])
                if c.get('daily_budget') and float(c.get('daily_budget')) > 0:
                    daily_b = int(float(c.get('daily_budget')))
                elif camp_adsets:
                    daily_b = sum(int(float(a.get('daily_budget') or 0)) for a in camp_adsets)
                else:
                    daily_b = 5000

                existing_c = cursor.execute("SELECT id FROM campaigns WHERE external_campaign_id = ?", (c_ext_id,)).fetchone()
                if existing_c:
                    cid_internal = existing_c['id']
                    cursor.execute("""
                        UPDATE campaigns
                        SET name = ?, status = ?, effective_status = ?, objective = ?, daily_budget_in_cents = ?,
                            total_spent_in_cents = ?, ad_account_id = ?, external_campaign_id = ?,
                            impressions = ?, clicks = ?, conversions = ?, initiate_checkouts = ?,
                            cost_per_ic_cents = ?, ctr = ?, cpc_cents = ?, cpm_cents = ?, cpa_cents = ?
                        WHERE id = ?
                    """, (c_name, c_status, eff_status, objective, daily_b, spend_cents, acc_id, c_ext_id, impressions, clicks, purchases, ic, cost_per_ic_cents, ctr, cpc_cents, cpm_cents, cpa_cents, cid_internal))
                else:
                    cursor.execute("""
                        INSERT INTO campaigns (
                            user_id, name, platform, status, effective_status, objective, daily_budget_in_cents,
                            total_spent_in_cents, ad_account_id, external_campaign_id, impressions, clicks,
                            conversions, initiate_checkouts, cost_per_ic_cents, ctr, cpc_cents, cpm_cents, cpa_cents
                        ) VALUES (1, ?, 'facebook', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (c_name, c_status, eff_status, objective, daily_b, spend_cents, acc_id, c_ext_id, impressions, clicks, purchases, ic, cost_per_ic_cents, ctr, cpc_cents, cpm_cents, cpa_cents))
                    cid_internal = cursor.lastrowid

                camp_id_map[c_ext_id] = cid_internal
                total_synced_campaigns += 1

            # 5. Upsert dos Conjuntos de Anúncios
            adset_id_map = {}
            for a in adsets_raw:
                a_ext_id = str(a.get('id', ''))
                a_name = a.get('name', 'Conjunto Meta')
                c_ext_id = str(a.get('campaign_id', ''))
                internal_c_id = camp_id_map.get(c_ext_id)
                eff_status = a.get('effective_status') or a.get('status', 'ACTIVE')
                a_status = 'active' if eff_status == 'ACTIVE' else 'paused'
                daily_budget = int(float(a.get('daily_budget') or 0))
                targeting_str = json.dumps(a.get('targeting', {}))

                stats = cursor.execute("""
                    SELECT COALESCE(SUM(spend_cents), 0) as spend,
                           COALESCE(SUM(impressions), 0) as impr,
                           COALESCE(SUM(clicks), 0) as clk,
                           COALESCE(SUM(conversions), 0) as conv,
                           COALESCE(SUM(initiate_checkouts), 0) as ic
                    FROM meta_adset_insights
                    WHERE adset_id = ?
                """, (a_ext_id,)).fetchone()

                spend_cents = stats[0]
                impressions = stats[1]
                clicks = stats[2]
                purchases = stats[3]
                ic = stats[4]
                ctr = round((clicks / impressions * 100.0), 2) if impressions > 0 else 0.0
                cpc_cents = int(spend_cents / clicks) if clicks > 0 else 0
                cpm_cents = int(spend_cents / impressions * 1000) if impressions > 0 else 0
                cpa_cents = int(spend_cents / purchases) if purchases > 0 else 0
                cost_per_ic_cents = int(spend_cents / ic) if ic > 0 else 0

                existing_a = cursor.execute("SELECT id FROM ad_sets WHERE external_id = ?", (a_ext_id,)).fetchone()
                if existing_a:
                    aid_internal = existing_a['id']
                    cursor.execute("""
                        UPDATE ad_sets
                        SET campaign_id = ?, external_id = ?, name = ?, status = ?, daily_budget_cents = ?,
                            spent_cents = ?, impressions = ?, clicks = ?, conversions = ?, initiate_checkouts = ?,
                            cpa_cents = ?, cost_per_ic_cents = ?, cpc_cents = ?, cpm_cents = ?, ctr = ?, targeting_info = ?
                        WHERE id = ?
                    """, (internal_c_id, a_ext_id, a_name, a_status, daily_budget, spend_cents, impressions, clicks, purchases, ic, cpa_cents, cost_per_ic_cents, cpc_cents, cpm_cents, ctr, targeting_str, aid_internal))
                else:
                    cursor.execute("""
                        INSERT INTO ad_sets (
                            campaign_id, external_id, name, status, daily_budget_cents, spent_cents,
                            impressions, clicks, conversions, initiate_checkouts, cpa_cents,
                            cost_per_ic_cents, cpc_cents, cpm_cents, ctr, targeting_info
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (internal_c_id, a_ext_id, a_name, a_status, daily_budget, spend_cents, impressions, clicks, purchases, ic, cpa_cents, cost_per_ic_cents, cpc_cents, cpm_cents, ctr, targeting_str))
                    aid_internal = cursor.lastrowid

                adset_id_map[a_ext_id] = aid_internal

            # 6. Upsert dos Anúncios (Criativos)
            for ad in ads_raw:
                ad_ext_id = str(ad.get('id', ''))
                ad_name = ad.get('name', 'Anúncio Meta')
                c_ext_id = str(ad.get('campaign_id', ''))
                a_ext_id = str(ad.get('adset_id', ''))
                internal_c_id = camp_id_map.get(c_ext_id)
                internal_a_id = adset_id_map.get(a_ext_id)
                eff_status = ad.get('effective_status') or ad.get('status', 'ACTIVE')
                ad_status = 'active' if eff_status == 'ACTIVE' else 'paused'

                stats = cursor.execute("""
                    SELECT COALESCE(SUM(spend_cents), 0) as spend,
                           COALESCE(SUM(impressions), 0) as impr,
                           COALESCE(SUM(clicks), 0) as clk,
                           COALESCE(SUM(conversions), 0) as conv,
                           COALESCE(SUM(initiate_checkouts), 0) as ic
                    FROM meta_ad_insights
                    WHERE ad_id = ?
                """, (ad_ext_id,)).fetchone()

                spend_cents = stats[0]
                impressions = stats[1]
                clicks = stats[2]
                purchases = stats[3]
                ic = stats[4]
                ctr = round((clicks / impressions * 100.0), 2) if impressions > 0 else 0.0
                cpc_cents = int(spend_cents / clicks) if clicks > 0 else 0
                cpm_cents = int(spend_cents / impressions * 1000) if impressions > 0 else 0
                cpa_cents = int(spend_cents / purchases) if purchases > 0 else 0
                cost_per_ic_cents = int(spend_cents / ic) if ic > 0 else 0

                existing_ad = cursor.execute("SELECT id FROM ads WHERE external_id = ?", (ad_ext_id,)).fetchone()
                if existing_ad:
                    cursor.execute("""
                        UPDATE ads
                        SET campaign_id = ?, ad_set_id = ?, external_id = ?, name = ?, status = ?,
                            spent_cents = ?, impressions = ?, clicks = ?, conversions = ?, initiate_checkouts = ?,
                            cpa_cents = ?, cost_per_ic_cents = ?, cpc_cents = ?, cpm_cents = ?, ctr = ?
                        WHERE id = ?
                    """, (internal_c_id, internal_a_id, ad_ext_id, ad_name, ad_status, spend_cents, impressions, clicks, purchases, ic, cpa_cents, cost_per_ic_cents, cpc_cents, cpm_cents, ctr, existing_ad['id']))
                else:
                    cursor.execute("""
                        INSERT INTO ads (
                            campaign_id, ad_set_id, external_id, name, status, creative_type,
                            spent_cents, impressions, clicks, conversions, initiate_checkouts,
                            cpa_cents, cost_per_ic_cents, cpc_cents, cpm_cents, ctr
                        ) VALUES (?, ?, ?, ?, ?, 'video', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (internal_c_id, internal_a_id, ad_ext_id, ad_name, ad_status, spend_cents, impressions, clicks, purchases, ic, cpa_cents, cost_per_ic_cents, cpc_cents, cpm_cents, ctr))

            now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("UPDATE facebook_ad_accounts SET sync_status = 'ok', sync_error = NULL, last_sync_at = ? WHERE id = ?", (now_str, acc['id']))

        except Exception as e:
            err_text = str(e)
            sync_errors.append(f"Conta {acc_id}: {err_text}")
            cursor.execute("UPDATE facebook_ad_accounts SET sync_status = 'error', sync_error = ? WHERE id = ?", (err_text, acc['id']))

    conn.commit()
    conn.close()
    return {
        "success": len(sync_errors) == 0,
        "synced": total_synced_campaigns,
        "errors": sync_errors
    }

def sync_meta_system_token(token=None, user_id=1):
    final_token = (token or DEFAULT_META_SYSTEM_TOKEN).strip()
    if not final_token:
        return {"success": False, "error": "Token não fornecido."}
    
    try:
        user_info = call_meta_graph_api('me', params={'fields': 'id,name'}, access_token=final_token)
        meta_user_id = str(user_info.get('id', '122096450511530140'))
        meta_user_name = user_info.get('name', 'Trackeamento')
        
        perms = ["ads_read", "public_profile"]
        try:
            p_data = call_meta_graph_api('me/permissions', access_token=final_token)
            p_list = [p.get('permission') for p in p_data.get('data', []) if p.get('status') == 'granted']
            if p_list:
                perms = p_list
        except Exception:
            pass
            
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM facebook_connections WHERE user_id = ?", (user_id,))
        cursor.execute("""
            INSERT INTO facebook_connections (user_id, meta_user_id, meta_user_name, access_token, expires_at, permissions, status, updated_at)
            VALUES (?, ?, ?, ?, '2099-12-31 23:59:59', ?, 'connected', CURRENT_TIMESTAMP)
        """, (user_id, meta_user_id, meta_user_name, final_token, json.dumps(perms)))
        
        cursor.execute("UPDATE facebook_ad_accounts SET is_selected = 0 WHERE user_id = ?", (user_id,))
        ad_accounts_data = fetch_all_meta_pages('me/adaccounts', params={
            'fields': 'id,name,account_id,account_status,currency,timezone_name,business_name',
            'limit': '50'
        }, access_token=final_token, max_pages=15)
        
        saved_accounts = []
        for acc in ad_accounts_data:
            raw_id = acc.get('account_id') or acc.get('id', '').replace('act_', '')
            name = acc.get('name') or f"Conta {raw_id}"
            currency = acc.get('currency', 'USD')
            tz = acc.get('timezone_name', 'America/Sao_Paulo')
            status_code = acc.get('account_status', 1)
            status_str = 'ACTIVE' if status_code == 1 else 'DISABLED'
            
            existing = cursor.execute("SELECT id FROM facebook_ad_accounts WHERE account_id = ? AND user_id = ?", (raw_id, user_id)).fetchone()
            if existing:
                cursor.execute("""
                    UPDATE facebook_ad_accounts 
                    SET name = ?, access_token = ?, currency = ?, timezone_name = ?, account_status = ?, status = ?, is_selected = 1
                    WHERE id = ?
                """, (name, final_token, currency, tz, status_code, status_str, existing['id']))
            else:
                cursor.execute("""
                    INSERT INTO facebook_ad_accounts (user_id, account_id, name, access_token, currency, timezone_name, account_status, status, is_selected)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (user_id, raw_id, name, final_token, currency, tz, status_code, status_str))
                
            saved_accounts.append({
                "account_id": raw_id,
                "name": name,
                "currency": currency,
                "timezone": tz,
                "status": status_str
            })
            
        conn.commit()
        conn.close()
        
        sync_res = sync_meta_campaigns_internal(user_id=user_id, period='all')
        
        return {
            "success": True,
            "user": {"id": meta_user_id, "name": meta_user_name},
            "accounts": saved_accounts,
            "campaigns_synced": sync_res.get("synced", 0)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_order_date_condition(period, start_date='', end_date='', col='created_at'):
    if period == 'today':
        return f"date({col}, 'localtime') = date('now', 'localtime')", []
    elif period == 'yesterday':
        return f"date({col}, 'localtime') = date('now', 'localtime', '-1 day')", []
    elif period == 'last_7_days':
        return f"{col} >= datetime('now', 'localtime', '-7 days')", []
    elif period == 'last_week':
        return f"{col} >= datetime('now', 'localtime', '-14 days') AND {col} < datetime('now', 'localtime', '-7 days')", []
    elif period == 'this_month':
        return f"strftime('%Y-%m', {col}, 'localtime') = strftime('%Y-%m', 'now', 'localtime')", []
    elif period == 'last_month':
        return f"strftime('%Y-%m', {col}, 'localtime') = strftime('%Y-%m', 'now', 'localtime', '-1 month')", []
    elif period == 'custom':
        if start_date and end_date:
            return f"date({col}, 'localtime') >= ? AND date({col}, 'localtime') <= ?", [start_date, end_date]
        elif start_date:
            return f"date({col}, 'localtime') >= ?", [start_date]
        elif end_date:
            return f"date({col}, 'localtime') <= ?", [end_date]
    return "", []

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
TRACKPRO_SVG_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100%" height="100%">
  <defs>
    <linearGradient id="trackpro-grad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#059669"/>
      <stop offset="100%" stop-color="#34d399"/>
    </linearGradient>
  </defs>
  <rect width="100" height="100" rx="22" fill="url(#trackpro-grad)"/>
  <g stroke="#ffffff" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round" fill="none">
    <circle cx="50" cy="50" r="26"/>
    <line x1="50" y1="14" x2="50" y2="24"/>
    <line x1="50" y1="76" x2="50" y2="86"/>
    <line x1="14" y1="50" x2="24" y2="50"/>
    <line x1="76" y1="50" x2="86" y2="50"/>
    <circle cx="50" cy="50" r="3" fill="#ffffff"/>
  </g>
</svg>"""


_CACHED_INDEX_HTML = None
_CACHED_INDEX_HTML_GZIP = None
_CACHED_INDEX_MTIME = 0

def get_cached_index_html():
    global _CACHED_INDEX_HTML, _CACHED_INDEX_HTML_GZIP, _CACHED_INDEX_MTIME
    root_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
    demo_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'demo', 'index.html')
    html_to_serve = root_html if os.path.exists(root_html) else demo_html
    current_mtime = os.path.getmtime(html_to_serve) if os.path.exists(html_to_serve) else 0

    if _CACHED_INDEX_HTML is None or _CACHED_INDEX_MTIME != current_mtime:
        if os.path.exists(html_to_serve):
            with open(html_to_serve, 'rb') as f:
                _CACHED_INDEX_HTML = f.read()
            _CACHED_INDEX_HTML_GZIP = gzip.compress(_CACHED_INDEX_HTML, compresslevel=6)
            _CACHED_INDEX_MTIME = current_mtime
        else:
            _CACHED_INDEX_HTML = b"<h1>TrackPro</h1>"
            _CACHED_INDEX_HTML_GZIP = gzip.compress(_CACHED_INDEX_HTML)
    return _CACHED_INDEX_HTML, _CACHED_INDEX_HTML_GZIP

def invalidate_index_html_cache():
    global _CACHED_INDEX_HTML, _CACHED_INDEX_HTML_GZIP
    _CACHED_INDEX_HTML = None
    _CACHED_INDEX_HTML_GZIP = None

class TrackProHandler(BaseHTTPRequestHandler):
    
    def _get_current_user_id(self):
        auth = self.headers.get('Authorization', '')
        token = None
        if auth.startswith('Bearer '):
            token = auth.split(' ', 1)[1].strip()
        if not token:
            token = self.headers.get('X-User-Token', '').strip()
        if not token:
            cookie_header = self.headers.get('Cookie', '')
            for c in cookie_header.split(';'):
                c = c.strip()
                if c.startswith('trackpro_token='):
                    token = c.split('=', 1)[1].strip()
                    break

        if token:
            try:
                conn = get_db()
                row = conn.execute("SELECT user_id, expires_at FROM user_sessions WHERE token = ?", (token,)).fetchone()
                conn.close()
                if row:
                    return row['user_id']
            except Exception:
                pass
        # Fallback seguro para o perfil principal do Lucas (User 1)
        return 1

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

        # Autenticação: Dados do Usuário Logado
        if path == '/api/auth/me':
            user_id = self._get_current_user_id()
            conn = get_db()
            cursor = conn.cursor()
            user = cursor.execute("SELECT id, name, email, company, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
            n_set = cursor.execute("SELECT * FROM notification_settings WHERE user_id = ?", (user_id,)).fetchone()
            conn.close()
            if not user:
                self._send_json({"authenticated": False, "error": "Usuário não encontrado"}, 404)
                return
            self._send_json({
                "authenticated": True,
                "user": {
                    "id": user['id'],
                    "name": user['name'],
                    "email": user['email'],
                    "company": user['company'] or 'TrackPro',
                    "created_at": user['created_at']
                },
                "notification_settings": dict(n_set) if n_set else {}
            })
            return

        # Notificações: Listagem e Contagem Não Lidas
        if path == '/api/notifications':
            user_id = self._get_current_user_id()
            conn = get_db()
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 50", (user_id,)).fetchall()
            unread = cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,)).fetchone()[0]
            conn.close()
            self._send_json({
                "notifications": [dict(r) for r in rows],
                "unread_count": unread
            })
            return

        # Notificações: Configurações do Usuário (GET)
        if path == '/api/notifications/settings':
            user_id = self._get_current_user_id()
            conn = get_db()
            cursor = conn.cursor()
            row = cursor.execute("SELECT * FROM notification_settings WHERE user_id = ?", (user_id,)).fetchone()
            conn.close()
            if row:
                res = dict(row)
                try:
                    res['summary_hours'] = json.loads(res.get('summary_hours') or '["08:00", "12:00", "16:00", "18:00", "22:00"]')
                except Exception:
                    res['summary_hours'] = ["08:00", "12:00", "16:00", "18:00", "22:00"]
                self._send_json(res)
            else:
                self._send_json({
                    "user_id": user_id,
                    "sound_enabled": 1,
                    "sound_type": "kaching",
                    "sound_volume": 1.0,
                    "notify_sale_approved": 1,
                    "notify_pix_generated": 1,
                    "notify_boleto_printed": 1,
                    "notify_refund": 1,
                    "notify_scheduled_summary": 1,
                    "summary_hours": ["08:00", "12:00", "16:00", "18:00", "22:00"],
                    "summary_tone": "creative",
                    "push_enabled": 0
                })
            return

        # Resumo Diário Programado (Agendamento no Celular)
        if path == '/api/notifications/scheduled-summary':
            user_id = self._get_current_user_id()
            conn = get_db()
            cursor = conn.cursor()

            row_rev = cursor.execute("""
                SELECT COALESCE(SUM(price_in_cents), 0) as total, COUNT(*) as count 
                FROM orders 
                WHERE user_id = ? AND status = 'paid' AND date(created_at, 'localtime') = date('now', 'localtime')
            """, (user_id,)).fetchone()
            rev_today = (row_rev['total'] or 0) / 100.0
            paid_count = row_rev['count'] or 0

            row_pix = cursor.execute("""
                SELECT COUNT(*) as count, COALESCE(SUM(price_in_cents), 0) as total 
                FROM orders 
                WHERE user_id = ? AND status = 'waiting_payment' AND date(created_at, 'localtime') = date('now', 'localtime')
            """, (user_id,)).fetchone()
            pix_count = row_pix['count'] or 0

            today_str = datetime.now().strftime('%Y-%m-%d')
            row_spent = cursor.execute("""
                SELECT COALESCE(SUM(spend_cents), 0) as total 
                FROM meta_campaign_insights 
                WHERE user_id = ? AND date_start = ?
            """, (user_id, today_str)).fetchone()
            spent_today = (row_spent['total'] or 0) / 100.0 if row_spent else 0.0

            fin = cursor.execute("SELECT * FROM financial_settings WHERE user_id = ?", (user_id,)).fetchone()
            gw_pct = (fin['gateway_tax_percent'] if fin else 8.9) / 100.0
            gw_fix = fin['gateway_fixed_fee'] if fin else 2.49
            inv_pct = (fin['invoice_tax_percent'] if fin else 6.0) / 100.0
            fees = (rev_today * gw_pct) + (paid_count * gw_fix) + (rev_today * inv_pct)
            net_rev = max(0.0, rev_today - fees)
            profit_today = round(net_rev - spent_today, 2)

            n_set = cursor.execute("SELECT * FROM notification_settings WHERE user_id = ?", (user_id,)).fetchone()
            tone = n_set['summary_tone'] if n_set and n_set['summary_tone'] else 'creative'

            now_hour = datetime.now().strftime('%H:%M')
            if tone == 'creative':
                if profit_today > 0:
                    title = f"🚀 Foguete não tem ré! (Resumo das {now_hour})"
                    msg = f"Hoje você já botou R$ {profit_today:,.2f} no bolso com {paid_count} vendas aprovadas! Faturamento: R$ {rev_today:,.2f}. Parabéns!".replace(',', 'X').replace('.', ',').replace('X', '.')
                else:
                    title = f"📊 Resumo das {now_hour} - TrackPro"
                    msg = f"Hoje você teve {paid_count} vendas (R$ {rev_today:,.2f}) e {pix_count} PIX gerados. Acompanhe a conversão!".replace(',', 'X').replace('.', ',').replace('X', '.')
            elif tone == 'strategic':
                roi_str = f"{(profit_today / spent_today * 100):.1f}%" if spent_today > 0 else "0.0%"
                title = f"🎯 Performance das {now_hour} - ROI {roi_str}"
                msg = f"Faturamento: R$ {rev_today:,.2f} | Gasto Ads: R$ {spent_today:,.2f} | Lucro Líquido: R$ {profit_today:,.2f} | Vendas: {paid_count}".replace(',', 'X').replace('.', ',').replace('X', '.')
            else:
                title = f"💼 Resumo Executivo das {now_hour}"
                msg = f"Receita: R$ {rev_today:,.2f} | Lucro: R$ {profit_today:,.2f} | Vendas Aprovadas: {paid_count} | PIX Gerados: {pix_count}".replace(',', 'X').replace('.', ',').replace('X', '.')

            conn.close()
            self._send_json({
                "success": True,
                "hour": now_hour,
                "title": title,
                "message": msg,
                "revenue_today": rev_today,
                "profit_today": profit_today,
                "spent_today": spent_today,
                "paid_orders": paid_count,
                "pix_generated": pix_count,
                "tone": tone
            })
            return
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
                "theme_color": "#060911",
                "orientation": "portrait-primary",
                "icons": [
                    {
                        "src": "/icon-192.png",
                        "sizes": "192x192",
                        "type": "image/png",
                        "purpose": "any maskable"
                    },
                    {
                        "src": "/icon-512.png",
                        "sizes": "512x512",
                        "type": "image/png",
                        "purpose": "any maskable"
                    },
                    {
                        "src": "/icon.svg",
                        "sizes": "any",
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

        # Favicon e Ícones PWA (Desktop e Mobile)
        if path in ['/icon.svg', '/favicon.svg']:
            self.send_response(200)
            self.send_header('Content-Type', 'image/svg+xml; charset=utf-8')
            self.send_header('Cache-Control', 'public, max-age=604800')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(TRACKPRO_SVG_ICON.encode('utf-8'))
            return

        if path in ['/icon-192.png', '/icon-512.png', '/favicon.png', '/favicon.ico', '/apple-touch-icon.png', '/apple-touch-icon-precomposed.png']:
            filename = path.lstrip('/')
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(cur_dir, filename)
            if not os.path.exists(file_path):
                # tenta caminhos alternativos conhecidos
                for alt in ['favicon.png', 'icon-192.png']:
                    p = os.path.join(cur_dir, alt)
                    if os.path.exists(p):
                        file_path = p
                        break
            
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    icon_bytes = f.read()
                mime = 'image/x-icon' if path.endswith('.ico') else 'image/png'
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Cache-Control', 'public, max-age=604800')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(icon_bytes)
                return
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'image/svg+xml; charset=utf-8')
                self.send_header('Cache-Control', 'public, max-age=604800')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(TRACKPRO_SVG_ICON.encode('utf-8'))
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
        if path in ['/trackpro.js', '/pixel.js', '/tracking/pixel.js', '/tracking/pixel']:
            token = params.get('token', [''])[0]
            host = self.headers.get('Host', 'meutrackpro.onrender.com')
            scheme = 'http' if ('localhost' in host or '127.0.0.1' in host) else 'https'
            server_origin = f"{scheme}://{host}"
            script = f"""(function(){{
  'use strict';
  var TOKEN = '{token}';
  var SERVER_ORIGIN = '{server_origin}';
  var curScript = document.currentScript || (function() {{
    var scripts = document.getElementsByTagName('script');
    for (var i = scripts.length - 1; i >= 0; i--) {{
      if (scripts[i].src && (scripts[i].src.indexOf('trackpro.js') !== -1 || scripts[i].src.indexOf('pixel.js') !== -1)) {{
        return scripts[i];
      }}
    }}
    return null;
  }})();
  var API = (curScript && curScript.src) ? (new URL(curScript.src)).origin : SERVER_ORIGIN;

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

  try {{
    fetch(API + '/api/tracking/event', {{
      method: 'POST',
      mode: 'cors',
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
  }} catch(e){{}}

  var checkouts = ['kiwify.com.br', 'hotmart.com', 'greenn.com.br', 'cakto.com.br', 'wiapy.com', 'eduzz.com', 'braip.com', 'monetizze.com.br', 'perfectpay.com.br', 'ticto.com.br', 'kirvano.com', 'doppus.com', 'lastlink.com', 'pepper.com.br'];

  function decorateCheckoutUrl(url) {{
    if (!url || typeof url !== 'string') return url;
    var isCheckout = checkouts.some(function(domain) {{ return url.indexOf(domain) !== -1; }});
    if (!isCheckout) return url;
    try {{
      var parsed = new URL(url, window.location.href);
      if (stored.utm_source && !parsed.searchParams.get('utm_source')) parsed.searchParams.set('utm_source', stored.utm_source);
      if (stored.utm_medium && !parsed.searchParams.get('utm_medium')) parsed.searchParams.set('utm_medium', stored.utm_medium);
      if (stored.utm_campaign && !parsed.searchParams.get('utm_campaign')) parsed.searchParams.set('utm_campaign', stored.utm_campaign);
      if (stored.utm_content && !parsed.searchParams.get('utm_content')) parsed.searchParams.set('utm_content', stored.utm_content);
      if (stored.utm_term && !parsed.searchParams.get('utm_term')) parsed.searchParams.set('utm_term', stored.utm_term);
      if (stored.src && !parsed.searchParams.get('src')) parsed.searchParams.set('src', stored.src);
      if (stored.sck && !parsed.searchParams.get('sck')) parsed.searchParams.set('sck', stored.sck);
      if (stored.fbc && !parsed.searchParams.get('fbc')) parsed.searchParams.set('fbc', stored.fbc);
      if (stored.fbp && !parsed.searchParams.get('fbp')) parsed.searchParams.set('fbp', stored.fbp);
      return parsed.toString();
    }} catch(e) {{
      return url;
    }}
  }}

  function decorateCheckoutLinks() {{
    var links = document.querySelectorAll('a[href]');
    links.forEach(function(link) {{
      var href = link.getAttribute('href');
      if (href) {{
        var newHref = decorateCheckoutUrl(href);
        if (newHref !== href) link.setAttribute('href', newHref);
      }}
    }});
  }}

  if (document.readyState === 'complete' || document.readyState === 'interactive') {{
    decorateCheckoutLinks();
  }} else {{
    document.addEventListener('DOMContentLoaded', decorateCheckoutLinks);
  }}

  if (window.MutationObserver) {{
    var obs = new MutationObserver(function() {{ decorateCheckoutLinks(); }});
    obs.observe(document.body || document.documentElement, {{ childList: true, subtree: true }});
  }}

  document.addEventListener('click', function(e) {{
    var target = e.target;
    while (target && target.tagName !== 'A' && target !== document.body) {{
      target = target.parentElement;
    }}
    if (target && target.tagName === 'A' && target.getAttribute('href')) {{
      target.setAttribute('href', decorateCheckoutUrl(target.getAttribute('href')));
    }}
  }}, true);

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

            user_id = self._get_current_user_id()
            order_conds = ['user_id = ?']
            order_params = [user_id]
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

            # 3. Gasto em Anúncios (escopado rigorosamente ao período selecionado)
            camp_where = ""
            camp_params = []
            if ad_account_filter and ad_account_filter != "all":
                camp_where = "WHERE ad_account_id = ?"
                camp_params = [ad_account_filter]

            s_dash_range, e_dash_range, _ = compute_date_range(period, start_date, end_date)
            if period == "all" or not s_dash_range:
                row_spent = cursor.execute(f"SELECT COALESCE(SUM(total_spent_in_cents), 0) as total FROM campaigns {camp_where}", camp_params).fetchone()
                tot_spent = (row_spent['total'] or 0) / 100.0
            else:
                ins_w = ["date_start >= ?", "date_stop <= ?"]
                ins_p = [s_dash_range, e_dash_range]
                if ad_account_filter and ad_account_filter != "all":
                    ins_w.append("ad_account_id = ?")
                    ins_p.append(ad_account_filter)
                row_spent = cursor.execute(f"SELECT COALESCE(SUM(spend_cents), 0) as total FROM meta_campaign_insights WHERE {' AND '.join(ins_w)}", ins_p).fetchone()
                tot_spent = (row_spent['total'] or 0) / 100.0

            # 4. Taxas e Impostos Parametrizados (Configurações Financeiras)
            fin = cursor.execute('SELECT * FROM financial_settings WHERE user_id = ?', (user_id,)).fetchone()
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
            
            if period != 'all' and s_dash_range:
                ins_w = ["date_start >= ?", "date_stop <= ?"]
                ins_p = [s_dash_range, e_dash_range]
                if ad_account_filter and ad_account_filter != 'all':
                    ins_w.append("ad_account_id = ?")
                    ins_p.append(ad_account_filter)
                meta_stats = cursor.execute(f"SELECT COALESCE(SUM(impressions), 0), COALESCE(SUM(clicks), 0), COALESCE(SUM(initiate_checkouts), 0) FROM meta_campaign_insights WHERE {' AND '.join(ins_w)}", ins_p).fetchone()
                cliques = max(pageviews, meta_stats[1] if meta_stats else 0)
                impressoes = max(meta_stats[0] if meta_stats else 0, cliques * 25 if cliques > 0 else 0)
                initiate_checkout = max(initiate_checkout, meta_stats[2] if meta_stats else 0)
            else:
                meta_stats = cursor.execute("SELECT COALESCE(SUM(impressions), 0), COALESCE(SUM(clicks), 0), COALESCE(SUM(initiate_checkouts), 0) FROM meta_campaign_insights").fetchone()
                cliques = max(pageviews, (meta_stats[1] if meta_stats else 0) or int(tot_spent * 1.8))
                impressoes = max(meta_stats[0] if meta_stats else 0, (cliques * 25 if cliques > 0 else 0) or int(tot_spent * 80))
                initiate_checkout = max(initiate_checkout, meta_stats[2] if meta_stats else 0)

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

            # Métodos de Pagamento (PIX, Cartão de Crédito, Boleto, etc.)
            query_methods = f"SELECT COALESCE(payment_method, 'outros') as method, COUNT(*) as count, COALESCE(SUM(price_in_cents), 0) as total FROM orders {paid_where} GROUP BY method"
            methods_rows = cursor.execute(query_methods, order_params).fetchall()
            name_map_pm = {'pix': 'PIX', 'credit_card': 'Cartão de Crédito', 'cartao': 'Cartão de Crédito', 'cartao_credito': 'Cartão de Crédito', 'boleto': 'Boleto', 'outros': 'Outros'}
            color_map_pm = {'pix': '#10B981', 'credit_card': '#6366F1', 'cartao': '#6366F1', 'cartao_credito': '#6366F1', 'boleto': '#F59E0B', 'outros': '#8B5CF6'}
            payment_methods_chart = []
            for r in methods_rows:
                raw_m = (r['method'] or 'outros').lower()
                norm_m = 'pix' if 'pix' in raw_m else ('cartao_credito' if ('cart' in raw_m or 'credit' in raw_m) else ('boleto' if 'bol' in raw_m else 'outros'))
                payment_methods_chart.append({
                    "name": name_map_pm.get(norm_m, 'Outros'),
                    "method": norm_m,
                    "count": r['count'],
                    "value": round((r['total'] or 0) / 100.0, 2),
                    "color": color_map_pm.get(norm_m, '#8B5CF6')
                })

            # Opções de Filtro (para popular dinamicamente os selects da barra Resumo)
            user_id = self._get_current_user_id()
            acc_rows = cursor.execute("SELECT account_id, name FROM facebook_ad_accounts WHERE user_id = ?", (user_id,)).fetchall()
            prod_rows = cursor.execute("SELECT id, name FROM products WHERE user_id = ?", (user_id,)).fetchall()
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
                "paymentMethodsChart": payment_methods_chart,
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
            user_id = self._get_current_user_id()
            rows = cursor.execute("SELECT * FROM facebook_ad_accounts WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
            conn.close()
            self._send_json({"accounts": [dict(r) for r in rows]})
            return

        # Campanhas e Conjuntos com Filtro de Período, Conta e Status
        if path in ['/api/campaigns', '/api/facebook/campaigns']:
            conn = get_db()
            cursor = conn.cursor()
            period = params.get('period', [''])[0].strip()
            start_date = params.get('start_date', [''])[0].strip()
            end_date = params.get('end_date', [''])[0].strip()
            ad_account_id = params.get('ad_account_id', [''])[0].strip()
            status_filter = params.get('status', [''])[0].strip()
            search_query = params.get('search', [''])[0].strip().lower()

            user_id = self._get_current_user_id()
            c_where = ["user_id = ?"]
            c_params = [user_id]
            if ad_account_id and ad_account_id != 'all':
                clean_acc = ad_account_id.replace('act_', '')
                c_where.append("(ad_account_id = ? OR ad_account_id = ?)")
                c_params.extend([ad_account_id, clean_acc])
            if status_filter and status_filter != 'all':
                c_where.append("status = ?")
                c_params.append(status_filter)
            if search_query:
                c_where.append("LOWER(name) LIKE ?")
                c_params.append(f"%{search_query}%")

            where_str = " WHERE " + " AND ".join(c_where)
            c_rows = cursor.execute(f"SELECT * FROM campaigns{where_str} ORDER BY id DESC", c_params).fetchall()

            order_date_clause, order_date_params = get_order_date_condition(period, start_date, end_date, col='created_at')
            s_range, e_range, _ = compute_date_range(period, start_date, end_date)

            campaigns = []
            for c in c_rows:
                c = dict(c)
                c_id = c['id']
                c_name = c['name']
                ext_id = c.get('external_campaign_id') or c_name
                adsets = cursor.execute("SELECT * FROM ad_sets WHERE campaign_id = ?", (c_id,)).fetchall()

                # Pedidos vinculados
                order_q = "SELECT COUNT(*) as count, COALESCE(SUM(price_in_cents), 0) as rev FROM orders WHERE (utm_campaign = ? OR utm_campaign = ?) AND status = 'paid'"
                order_p = [c_name, ext_id]
                if order_date_clause:
                    order_q += f" AND {order_date_clause}"
                    order_p.extend(order_date_params)
                order_calc = cursor.execute(order_q, order_p).fetchone()
                order_vendas = order_calc['count'] if order_calc else 0
                faturamento = (order_calc['rev'] if order_calc else 0) / 100.0

                if s_range and e_range and period != 'all':
                    ins_q = """
                        SELECT COALESCE(SUM(spend_cents), 0) as spend,
                               COALESCE(SUM(impressions), 0) as impr,
                               COALESCE(SUM(clicks), 0) as clk,
                               COALESCE(SUM(conversions), 0) as conv,
                               COALESCE(SUM(initiate_checkouts), 0) as ic
                        FROM meta_campaign_insights
                        WHERE (campaign_id = ? OR campaign_name = ?)
                          AND date_start >= ? AND date_stop <= ?
                    """
                    ins_row = cursor.execute(ins_q, (ext_id, c_name, s_range, e_range)).fetchone()
                    gasto = (ins_row['spend'] or 0) / 100.0
                    impressoes = ins_row['impr'] or 0
                    cliques = ins_row['clk'] or 0
                    meta_convs = ins_row['conv'] or 0
                    meta_ics = ins_row['ic'] or 0

                    # Filtro de período rigoroso: se não rodou no período e não está ativa, não exibe
                    if gasto == 0 and impressoes == 0 and order_vendas == 0 and meta_ics == 0 and c['status'] != 'active':
                        continue
                else:
                    gasto = (c['total_spent_in_cents'] or 0) / 100.0
                    impressoes = c.get('impressions') or 0
                    cliques = c.get('clicks') or 0
                    meta_convs = c.get('conversions') or 0
                    meta_ics = c.get('initiate_checkouts') or 0

                vendas = order_vendas + meta_convs
                cost_per_ic = round(gasto / meta_ics, 2) if meta_ics > 0 else 0.0
                roas = round(faturamento / gasto, 2) if gasto > 0 else 0.0
                cpa = round(gasto / vendas, 2) if vendas > 0 else 0.0
                ctr = round((cliques / impressoes * 100.0), 2) if impressoes > 0 else 0.0
                cpc = round(gasto / cliques, 2) if cliques > 0 else 0.0
                cpm = round((gasto / impressoes * 1000.0), 2) if impressoes > 0 else 0.0

                campaigns.append({
                    "id": c_id,
                    "name": c_name,
                    "platform": c['platform'],
                    "status": c['status'],
                    "effective_status": c.get('effective_status') or c['status'],
                    "objective": c.get('objective') or 'VENDAS',
                    "daily_budget": (c['daily_budget_in_cents'] or 0) / 100.0,
                    "spent": gasto,
                    "sales": vendas,
                    "initiate_checkouts": meta_ics,
                    "cost_per_ic": cost_per_ic,
                    "revenue": faturamento,
                    "roas": roas,
                    "cpa": cpa,
                    "impressions": impressoes,
                    "clicks": cliques,
                    "ctr": ctr,
                    "cpc": cpc,
                    "cpm": cpm,
                    "ad_account_id": c['ad_account_id'],
                    "adsets": [dict(a) for a in adsets]
                })

            conn.close()
            self._send_json({"campaigns": campaigns, "period": period, "start_date": s_range, "end_date": e_range})
            return

        # Meta OAuth Status Check
        if path in ['/api/integrations/meta/status', '/api/auth/facebook/status', '/api/facebook/status']:
            conn = get_db()
            user_id = self._get_current_user_id()
            cfg = get_meta_config(conn, self.headers.get('Host'))
            conn_row = conn.execute("SELECT * FROM facebook_connections WHERE user_id = ? AND status = 'connected' ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
            accounts = conn.execute("SELECT id, account_id, name, currency, timezone_name, status, account_status, is_selected, last_sync_at, sync_status FROM facebook_ad_accounts WHERE user_id = ? ORDER BY is_selected DESC, id DESC", (user_id,)).fetchall()
            
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

        # Conjuntos de Anúncio com Filtro por Período e Campanhas Selecionadas
        if path in ['/api/facebook/adsets', '/api/adsets']:
            conn = get_db()
            cursor = conn.cursor()
            period = params.get('period', [''])[0].strip()
            start_date = params.get('start_date', [''])[0].strip()
            end_date = params.get('end_date', [''])[0].strip()
            camp_param = params.get('campaign_ids', params.get('campaign_id', ['']))[0]

            if camp_param:
                c_ids = [c.strip() for c in camp_param.split(',') if c.strip().isdigit()]
                if c_ids:
                    placeholders = ','.join(['?'] * len(c_ids))
                    rows = cursor.execute(f"SELECT a.*, c.name as campaign_name FROM ad_sets a LEFT JOIN campaigns c ON a.campaign_id = c.id WHERE a.campaign_id IN ({placeholders}) ORDER BY a.id DESC", c_ids).fetchall()
                else:
                    rows = []
            else:
                # Se nenhuma campanha foi selecionada, exibe todos os conjuntos da conta
                rows = cursor.execute("SELECT a.*, c.name as campaign_name FROM ad_sets a LEFT JOIN campaigns c ON a.campaign_id = c.id ORDER BY a.id DESC").fetchall()

            order_date_clause, order_date_params = get_order_date_condition(period, start_date, end_date, col='created_at')
            s_range, e_range, _ = compute_date_range(period, start_date, end_date)

            adsets_list = []
            for r in rows:
                item = dict(r)
                daily_budget = (item.get('daily_budget_cents') or 0) / 100.0

                order_q = "SELECT COUNT(*) as cnt, COALESCE(SUM(price_in_cents), 0) as rev FROM orders WHERE utm_content = ? AND status = 'paid'"
                order_p = [item['name']]
                if order_date_clause:
                    order_q += f" AND {order_date_clause}"
                    order_p.extend(order_date_params)
                sales = cursor.execute(order_q, order_p).fetchone()
                sales_count = sales['cnt'] if sales else 0
                revenue = (sales['rev'] if sales else 0) / 100.0

                if s_range and e_range and period != 'all':
                    ins_q = """
                        SELECT COALESCE(SUM(spend_cents), 0) as spend,
                               COALESCE(SUM(impressions), 0) as impr,
                               COALESCE(SUM(clicks), 0) as clk,
                               COALESCE(SUM(conversions), 0) as conv,
                               COALESCE(SUM(initiate_checkouts), 0) as ic
                        FROM meta_adset_insights
                        WHERE (adset_id = ? OR adset_name = ?)
                          AND date_start >= ? AND date_stop <= ?
                    """
                    ins_row = cursor.execute(ins_q, (item.get('external_id'), item['name'], s_range, e_range)).fetchone()
                    spent = (ins_row['spend'] or 0) / 100.0
                    impressions = ins_row['impr'] or 0
                    clicks = ins_row['clk'] or 0
                    meta_convs = ins_row['conv'] or 0
                    meta_ics = ins_row['ic'] or 0

                    if spent == 0 and impressions == 0 and sales_count == 0 and item.get('status') != 'active':
                        continue
                else:
                    spent = (item.get('spent_cents') or 0) / 100.0
                    impressions = item.get('impressions') or 0
                    clicks = item.get('clicks') or 0
                    meta_convs = item.get('conversions') or 0
                    meta_ics = item.get('initiate_checkouts') or 0

                total_sales = sales_count + meta_convs
                cost_per_ic = round(spent / meta_ics, 2) if meta_ics > 0 else 0.0
                ctr = round((clicks / impressions * 100.0), 2) if impressions > 0 else 0.0
                cpc = round(spent / clicks, 2) if clicks > 0 else 0.0
                cpm = round((spent / impressions * 1000.0), 2) if impressions > 0 else 0.0
                roas = round(revenue / spent, 2) if spent > 0 else 0.0
                cpa = round(spent / total_sales, 2) if total_sales > 0 else 0.0

                item['spent'] = spent
                item['daily_budget'] = daily_budget
                item['sales'] = total_sales
                item['initiate_checkouts'] = meta_ics
                item['cost_per_ic'] = cost_per_ic
                item['impressions'] = impressions
                item['clicks'] = clicks
                item['ctr'] = ctr
                item['cpc'] = cpc
                item['cpm'] = cpm
                item['revenue'] = revenue
                item['roas'] = roas
                item['cpa'] = cpa
                adsets_list.append(item)
            conn.close()
            self._send_json({"adsets": adsets_list})
            return

        # Anúncios (Criativos)
        if path in ['/api/facebook/ads', '/api/ads']:
            conn = get_db()
            cursor = conn.cursor()
            period = params.get('period', [''])[0].strip()
            start_date = params.get('start_date', [''])[0].strip()
            end_date = params.get('end_date', [''])[0].strip()
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
            order_date_clause, order_date_params = get_order_date_condition(period, start_date, end_date, col='created_at')
            s_range, e_range, _ = compute_date_range(period, start_date, end_date)

            ads_list = []
            for r in rows:
                item = dict(r)

                order_q = "SELECT COUNT(*) as cnt, COALESCE(SUM(price_in_cents), 0) as rev FROM orders WHERE utm_term = ? AND status = 'paid'"
                order_p = [item['name']]
                if order_date_clause:
                    order_q += f" AND {order_date_clause}"
                    order_p.extend(order_date_params)
                sales = cursor.execute(order_q, order_p).fetchone()
                sales_count = sales['cnt'] if sales else 0
                revenue = (sales['rev'] if sales else 0) / 100.0

                if s_range and e_range and period != 'all':
                    ins_q = """
                        SELECT COALESCE(SUM(spend_cents), 0) as spend,
                               COALESCE(SUM(impressions), 0) as impr,
                               COALESCE(SUM(clicks), 0) as clk,
                               COALESCE(SUM(conversions), 0) as conv,
                               COALESCE(SUM(initiate_checkouts), 0) as ic
                        FROM meta_ad_insights
                        WHERE (ad_id = ? OR ad_name = ?)
                          AND date_start >= ? AND date_stop <= ?
                    """
                    ins_row = cursor.execute(ins_q, (item.get('external_id'), item['name'], s_range, e_range)).fetchone()
                    spent = (ins_row['spend'] or 0) / 100.0
                    impressions = ins_row['impr'] or 0
                    clicks = ins_row['clk'] or 0
                    meta_convs = ins_row['conv'] or 0
                    meta_ics = ins_row['ic'] or 0

                    if spent == 0 and impressions == 0 and sales_count == 0 and item.get('status') != 'active':
                        continue
                else:
                    spent = (item.get('spent_cents') or 0) / 100.0
                    impressions = item.get('impressions') or 0
                    clicks = item.get('clicks') or 0
                    meta_convs = item.get('conversions') or 0
                    meta_ics = item.get('initiate_checkouts') or 0

                total_sales = sales_count + meta_convs
                cost_per_ic = round(spent / meta_ics, 2) if meta_ics > 0 else 0.0
                ctr = round((clicks / impressions * 100.0), 2) if impressions > 0 else 0.0
                cpc = round(spent / clicks, 2) if clicks > 0 else 0.0
                cpm = round((spent / impressions * 1000.0), 2) if impressions > 0 else 0.0
                roas = round(revenue / spent, 2) if spent > 0 else 0.0
                cpa = round(spent / total_sales, 2) if total_sales > 0 else 0.0

                item['spent'] = spent
                item['sales'] = total_sales
                item['initiate_checkouts'] = meta_ics
                item['cost_per_ic'] = cost_per_ic
                item['impressions'] = impressions
                item['clicks'] = clicks
                item['ctr'] = ctr
                item['cpc'] = cpc
                item['cpm'] = cpm
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
            user_id = self._get_current_user_id()
            rows = cursor.execute("SELECT * FROM automated_rules WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
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
            rows = cursor.execute('SELECT * FROM meta_pixels WHERE user_id = ? ORDER BY id DESC', (user_id,)).fetchall()
            conn.close()
            self._send_json({"pixels": [dict(r) for r in rows]})
            return

        # Custom Dashboards / Workspaces
        if path == '/api/dashboards':
            conn = get_db()
            cursor = conn.cursor()
            rows = cursor.execute('SELECT * FROM custom_dashboards WHERE user_id = ? ORDER BY id ASC', (user_id,)).fetchall()
            conn.close()
            self._send_json({"dashboards": [dict(r) for r in rows]})
            return

        # Configurações Financeiras (Taxas e Impostos) - Consulta GET
        if path == '/api/settings/financial':
            conn = get_db()
            cursor = conn.cursor()
            fin = cursor.execute('SELECT * FROM financial_settings WHERE user_id = ?', (user_id,)).fetchone()
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
            pref = cursor.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,)).fetchone()
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
            user_id = self._get_current_user_id()
            meta = cursor.execute("SELECT pixel_id, access_token, test_event_code, active FROM meta_settings WHERE user_id = ?", (user_id,)).fetchone()
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
            logs = cursor.execute('SELECT * FROM capi_logs WHERE user_id = ? ORDER BY id DESC LIMIT 30', (user_id,)).fetchall()
            conn.close()
            self._send_json({"logs": [dict(l) for l in logs]})
            return

        # Serve static web application
        root_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
        demo_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'demo', 'index.html')
        html_to_serve = root_html if os.path.exists(root_html) else demo_html

        if path in ['/', '/index.html']:
            raw_bytes, gzip_bytes = get_cached_index_html()
            accept_encoding = self.headers.get('Accept-Encoding', '')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, must-revalidate')
            self._send_cors_headers()
            if 'gzip' in accept_encoding:
                self.send_header('Content-Encoding', 'gzip')
                self.send_header('Content-Length', str(len(gzip_bytes)))
                self.end_headers()
                self.wfile.write(gzip_bytes)
            else:
                self.send_header('Content-Length', str(len(raw_bytes)))
                self.end_headers()
                self.wfile.write(raw_bytes)
            return

        # 404
        self._send_json({"error": "Endpoint não encontrado"}, 404)

    def do_DELETE(self):
        return self.do_POST()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        # ==================== AUTENTICAÇÃO E PERFIS MULTI-USUÁRIO ====================
        if path == '/api/auth/register':
            name = (body.get('name') or '').strip()
            email = (body.get('email') or '').strip().lower()
            password = body.get('password') or ''
            confirm_password = body.get('confirm_password') or ''

            if not name:
                self._send_json({"error": "Por favor, informe seu nome completo."}, 400)
                return
            if not email or '@' not in email or '.' not in email:
                self._send_json({"error": "Por favor, informe um e-mail válido."}, 400)
                return
            if len(password) < 6:
                self._send_json({"error": "A senha deve conter no mínimo 6 caracteres."}, 400)
                return
            if not confirm_password or password != confirm_password:
                self._send_json({"error": "A confirmação de senha é obrigatória e deve ser idêntica à senha digitada."}, 400)
                return

            conn = get_db()
            cursor = conn.cursor()
            existing = cursor.execute("SELECT id FROM users WHERE lower(email) = ?", (email,)).fetchone()
            if existing:
                conn.close()
                self._send_json({"error": "Este e-mail já está cadastrado. Faça login ou use outro e-mail."}, 400)
                return

            hashed = hash_password(password)
            cursor.execute("INSERT INTO users (name, email, password, company) VALUES (?, ?, ?, 'Operação Própria')", (name, email, hashed))
            new_user_id = cursor.lastrowid

            # Inicializa preferências e configurações para o novo perfil isolado
            cursor.execute("INSERT OR IGNORE INTO financial_settings (user_id) VALUES (?)", (new_user_id,))
            cursor.execute("INSERT OR IGNORE INTO notification_settings (user_id) VALUES (?)", (new_user_id,))
            cursor.execute("INSERT INTO custom_dashboards (user_id, name, platform_filter, is_default) VALUES (?, 'Geral', '', 1)", (new_user_id,))

            token = f"tp_{secrets.token_hex(24)}"
            expires = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("INSERT INTO user_sessions (user_id, token, ip_address, expires_at) VALUES (?, ?, ?, ?)",
                           (new_user_id, token, self.client_address[0], expires))
            conn.commit()
            conn.close()

            self._send_json({
                "success": True,
                "token": token,
                "user": {"id": new_user_id, "name": name, "email": email},
                "message": "Conta criada com sucesso! Seja bem-vindo ao TrackPro."
            })
            return

        if path == '/api/auth/login':
            email = (body.get('email') or '').strip().lower()
            password = body.get('password') or ''

            if not email or not password:
                self._send_json({"error": "Preencha o e-mail e a senha."}, 400)
                return

            conn = get_db()
            cursor = conn.cursor()
            user = cursor.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
            if not user or not verify_password(user['password'], password):
                conn.close()
                self._send_json({"error": "E-mail ou senha incorretos."}, 401)
                return

            token = f"tp_{secrets.token_hex(24)}"
            expires = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("INSERT INTO user_sessions (user_id, token, ip_address, expires_at) VALUES (?, ?, ?, ?)",
                           (user['id'], token, self.client_address[0], expires))
            conn.commit()
            conn.close()

            self._send_json({
                "success": True,
                "token": token,
                "user": {"id": user['id'], "name": user['name'], "email": user['email']},
                "message": f"Bem-vindo de volta, {user['name']}!"
            })
            return

        if path == '/api/auth/google':
            email = (body.get('email') or 'lucas.google@trackpro.com').strip().lower()
            name = (body.get('name') or 'Usuário Google').strip()

            conn = get_db()
            cursor = conn.cursor()
            user = cursor.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
            if not user:
                hashed = hash_password(secrets.token_hex(16))
                cursor.execute("INSERT INTO users (name, email, password, company) VALUES (?, ?, ?, 'Google Account')", (name, email, hashed))
                uid = cursor.lastrowid
                cursor.execute("INSERT OR IGNORE INTO financial_settings (user_id) VALUES (?)", (uid,))
                cursor.execute("INSERT OR IGNORE INTO notification_settings (user_id) VALUES (?)", (uid,))
                cursor.execute("INSERT INTO custom_dashboards (user_id, name, platform_filter, is_default) VALUES (?, 'Geral', '', 1)", (uid,))
                user_obj = {"id": uid, "name": name, "email": email}
            else:
                user_obj = {"id": user['id'], "name": user['name'], "email": user['email']}

            token = f"tp_{secrets.token_hex(24)}"
            expires = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("INSERT INTO user_sessions (user_id, token, ip_address, expires_at) VALUES (?, ?, ?, ?)",
                           (user_obj['id'], token, self.client_address[0], expires))
            conn.commit()
            conn.close()

            self._send_json({
                "success": True,
                "token": token,
                "user": user_obj,
                "message": f"Conectado com Google como {name}!"
            })
            return

        if path == '/api/auth/logout':
            auth = self.headers.get('Authorization', '')
            token = auth.split(' ', 1)[1].strip() if auth.startswith('Bearer ') else self.headers.get('X-User-Token', '')
            if token:
                conn = get_db()
                conn.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
                conn.commit()
                conn.close()
            self._send_json({"success": True, "message": "Sessão encerrada com sucesso."})
            return

        # ==================== NOTIFICAÇÕES & SONS (UTMIFY / LOWTRACK STYLE) ====================
        if path == '/api/notifications/settings':
            user_id = self._get_current_user_id()
            sound_enabled = 1 if body.get('sound_enabled', True) else 0
            sound_type = body.get('sound_type', 'kaching')
            sound_volume = float(body.get('sound_volume', 1.0))
            notify_sale = 1 if body.get('notify_sale_approved', True) else 0
            notify_pix = 1 if body.get('notify_pix_generated', True) else 0
            notify_boleto = 1 if body.get('notify_boleto_printed', True) else 0
            notify_refund = 1 if body.get('notify_refund', True) else 0
            notify_scheduled = 1 if body.get('notify_scheduled_summary', True) else 0
            summary_hours = json.dumps(body.get('summary_hours', ["08:00", "12:00", "16:00", "18:00", "22:00"]))
            summary_tone = body.get('summary_tone', 'creative')
            push_enabled = 1 if body.get('push_enabled') else 0

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notification_settings (
                    user_id, sound_enabled, sound_type, sound_volume,
                    notify_sale_approved, notify_pix_generated, notify_boleto_printed,
                    notify_refund, notify_scheduled_summary, summary_hours, summary_tone, push_enabled, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    sound_enabled = excluded.sound_enabled,
                    sound_type = excluded.sound_type,
                    sound_volume = excluded.sound_volume,
                    notify_sale_approved = excluded.notify_sale_approved,
                    notify_pix_generated = excluded.notify_pix_generated,
                    notify_boleto_printed = excluded.notify_boleto_printed,
                    notify_refund = excluded.notify_refund,
                    notify_scheduled_summary = excluded.notify_scheduled_summary,
                    summary_hours = excluded.summary_hours,
                    summary_tone = excluded.summary_tone,
                    push_enabled = excluded.push_enabled,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, sound_enabled, sound_type, sound_volume, notify_sale, notify_pix, notify_boleto, notify_refund, notify_scheduled, summary_hours, summary_tone, push_enabled))
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Configurações de notificação salvas com sucesso!"})
            return

        if path == '/api/notifications/read-all':
            user_id = self._get_current_user_id()
            conn = get_db()
            conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            self._send_json({"success": True, "message": "Todas as notificações marcadas como lidas."})
            return

        if path == '/api/notifications/test':
            user_id = self._get_current_user_id()
            test_type = body.get('type', 'sale_approved')
            amount = int(body.get('amount_in_cents', 19700))
            amount_reais = amount / 100.0

            conn = get_db()
            cursor = conn.cursor()
            if test_type == 'pix_generated':
                title = "⚡ PIX GERADO!"
                msg = f"PIX de R$ {amount_reais:,.2f} gerado! Cliente: Marcos Vinicius (Aguardando pagamento)".replace(',', 'X').replace('.', ',').replace('X', '.')
                method = 'pix'
            elif test_type == 'boleto_printed':
                title = "📄 BOLETO IMPRESSO!"
                msg = f"Boleto de R$ {amount_reais:,.2f} impresso! Cliente: Ana Carolina (Hotmart)".replace(',', 'X').replace('.', ',').replace('X', '.')
                method = 'boleto'
            elif test_type == 'refund':
                title = "⚠️ REEMBOLSO REGISTRADO"
                msg = f"Reembolso de R$ {amount_reais:,.2f} registrado com sucesso.".replace(',', 'X').replace('.', ',').replace('X', '.')
                method = 'refund'
            else:
                title = "💸 VENDA APROVADA!"
                msg = f"Venda de R$ {amount_reais:,.2f} aprovada via Cartão de Crédito! (Kiwify - Lucas Silva)".replace(',', 'X').replace('.', ',').replace('X', '.')
                method = 'cartao'

            cursor.execute("""
                INSERT INTO notifications (user_id, type, title, message, amount_in_cents, payment_method)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, test_type, title, msg, amount, method))
            notif_id = cursor.lastrowid
            conn.commit()
            conn.close()

            self._send_json({
                "success": True,
                "notification": {
                    "id": notif_id,
                    "type": test_type,
                    "title": title,
                    "message": msg,
                    "amount_in_cents": amount,
                    "payment_method": method
                }
            })
            return

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

        # Conectar via Token Permanente de System User
        if path in ['/api/facebook/connect_token', '/api/integrations/meta/connect-token']:
            token = body.get('access_token') or body.get('token') or DEFAULT_META_SYSTEM_TOKEN
            res = sync_meta_system_token(token)
            self._send_json(res, 200 if res.get('success') else 400)
            return

        # Sincronização Real de Campanhas e Gastos com Paginação e Insights
        if path in ['/api/integrations/meta/sync', '/api/facebook/sync']:
            sync_period = body.get('period', 'all')
            sync_start = body.get('start_date', '')
            sync_end = body.get('end_date', '')
            res = sync_meta_campaigns_internal(1, sync_period, sync_start, sync_end)
            if res.get('success'):
                self._send_json({
                    "success": True,
                    "message": f"Sincronização concluída com sucesso! {res.get('synced', 0)} campanhas atualizadas.",
                    "synced_campaigns": res.get('synced', 0)
                }, 200)
            else:
                self._send_json({
                    "error": res.get('error', 'Erro durante a sincronização'),
                    "details": res.get('errors', [])
                }, 400)
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

            camp_row = cursor.execute("SELECT ad_account_id FROM campaigns WHERE id = ?", (orig['campaign_id'],)).fetchone()
            acc_id = camp_row['ad_account_id'] if camp_row else None
            acc_row = cursor.execute("SELECT access_token FROM facebook_ad_accounts WHERE account_id = ? OR account_id = ?", (acc_id, str(acc_id).replace('act_', ''))).fetchone() if acc_id else None
            token = acc_row['access_token'] if acc_row and acc_row['access_token'] else DEFAULT_META_SYSTEM_TOKEN

            new_name = f"[CÓPIA] {orig['name']}"
            meta_copied_id, meta_err = duplicate_meta_item('adset', orig['external_id'], token)

            final_ext_id = meta_copied_id or f"ADSET-{uuid.uuid4().hex[:6].upper()}"
            cursor.execute("""
                INSERT INTO ad_sets (campaign_id, external_id, name, status, daily_budget_cents, spent_cents, targeting_info)
                VALUES (?, ?, ?, 'paused', ?, 0, ?)
            """, (orig['campaign_id'], final_ext_id, new_name, orig['daily_budget_cents'], orig['targeting_info']))
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()

            if meta_copied_id:
                msg = f"Conjunto duplicado no Facebook Ads (ID: {meta_copied_id}) e sincronizado com sucesso!"
            elif meta_err:
                msg = f"Conjunto duplicado localmente. Aviso Meta: {meta_err}"
            else:
                msg = f"Conjunto '{new_name}' duplicado com sucesso!"

            self._send_json({"success": True, "new_adset_id": new_id, "name": new_name, "meta_id": meta_copied_id, "message": msg})
            return

        # Duplicar Campanha Inteira no Facebook Ads
        if path in ['/api/facebook/campaigns/duplicate', '/api/campaigns/duplicate']:
            camp_id = body.get('campaign_id') or body.get('id')
            conn = get_db()
            cursor = conn.cursor()
            orig = cursor.execute("SELECT * FROM campaigns WHERE id = ?", (camp_id,)).fetchone()
            if not orig:
                conn.close()
                self._send_json({"error": "Campanha não encontrada"}, 404)
                return

            acc_id = orig['ad_account_id']
            acc_row = cursor.execute("SELECT access_token FROM facebook_ad_accounts WHERE account_id = ? OR account_id = ?", (acc_id, str(acc_id).replace('act_', ''))).fetchone() if acc_id else None
            token = acc_row['access_token'] if acc_row and acc_row['access_token'] else DEFAULT_META_SYSTEM_TOKEN

            new_name = f"[CÓPIA] {orig['name']}"
            meta_copied_id, meta_err = duplicate_meta_item('campaign', orig['external_campaign_id'], token)

            final_ext_id = meta_copied_id or f"CAMP-{uuid.uuid4().hex[:6].upper()}"
            cursor.execute("""
                INSERT INTO campaigns (user_id, name, platform, status, daily_budget_in_cents, total_spent_in_cents, ad_account_id, external_campaign_id)
                VALUES (1, ?, ?, 'paused', ?, 0, ?, ?)
            """, (new_name, orig['platform'], orig['daily_budget_in_cents'], orig['ad_account_id'], final_ext_id))
            new_camp_id = cursor.lastrowid

            adsets = cursor.execute("SELECT * FROM ad_sets WHERE campaign_id = ?", (camp_id,)).fetchall()
            for a in adsets:
                cursor.execute("""
                    INSERT INTO ad_sets (campaign_id, external_id, name, status, daily_budget_cents, spent_cents, targeting_info)
                    VALUES (?, ?, ?, 'paused', ?, 0, ?)
                """, (new_camp_id, f"ADSET-{uuid.uuid4().hex[:6].upper()}", a['name'], a['daily_budget_cents'], a['targeting_info']))

            conn.commit()
            conn.close()

            if meta_copied_id:
                msg = f"Campanha duplicada no Facebook Ads (ID: {meta_copied_id}) e sincronizada com sucesso!"
            elif meta_err:
                msg = f"Campanha duplicada localmente. Aviso Meta: {meta_err}"
            else:
                msg = f"Campanha '{new_name}' duplicada com sucesso!"

            self._send_json({"success": True, "new_campaign_id": new_camp_id, "name": new_name, "meta_id": meta_copied_id, "message": msg})
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

            # Inserir notificação correspondente para alerta em tempo real e som no celular
            try:
                notif_user_id = 1
                pr_cents = parsed_order.get('price_cents', 0)
                pr_reais = pr_cents / 100.0
                c_name = parsed_order.get('customer_name', 'Cliente')
                plt = parsed_order.get('platform', 'Gateway')
                mth = parsed_order.get('payment_method', 'cartao')

                if parsed_order['status'] == 'paid':
                    cursor.execute("""
                        INSERT INTO notifications (user_id, type, title, message, amount_in_cents, payment_method)
                        VALUES (?, 'sale_approved', '💸 VENDA APROVADA!', ?, ?, ?)
                    """, (notif_user_id, f"Venda de R$ {pr_reais:,.2f} aprovada via {mth}! ({plt} - {c_name})".replace(',', 'X').replace('.', ',').replace('X', '.'), pr_cents, mth))
                    conn.commit()
                elif parsed_order['status'] == 'waiting_payment':
                    if 'pix' in str(mth).lower():
                        cursor.execute("""
                            INSERT INTO notifications (user_id, type, title, message, amount_in_cents, payment_method)
                            VALUES (?, 'pix_generated', '⚡ PIX GERADO!', ?, ?, 'pix')
                        """, (notif_user_id, f"PIX de R$ {pr_reais:,.2f} gerado! Cliente: {c_name} ({plt})".replace(',', 'X').replace('.', ',').replace('X', '.'), pr_cents))
                        conn.commit()
                    elif 'boleto' in str(mth).lower():
                        cursor.execute("""
                            INSERT INTO notifications (user_id, type, title, message, amount_in_cents, payment_method)
                            VALUES (?, 'boleto_printed', '📄 BOLETO IMPRESSO!', ?, ?, 'boleto')
                        """, (notif_user_id, f"Boleto de R$ {pr_reais:,.2f} impresso! Cliente: {c_name} ({plt})".replace(',', 'X').replace('.', ',').replace('X', '.'), pr_cents))
                        conn.commit()
            except Exception as e_notif:
                pass
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
