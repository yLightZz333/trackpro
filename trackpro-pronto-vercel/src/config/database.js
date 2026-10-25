const Database = require('better-sqlite3');
const path = require('path');
const bcrypt = require('bcryptjs');
const { v4: uuidv4 } = require('uuid');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, '..', '..', 'trackpro.db');

let db;

function getDb() {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
    initializeTables();
    seedDemoData();
  }
  return db;
}

function initializeTables() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      company TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS api_credentials (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      token TEXT NOT NULL UNIQUE,
      active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS products (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      platform TEXT,
      cost_in_cents INTEGER NOT NULL DEFAULT 0,
      active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      order_external_id TEXT,
      product_id INTEGER,
      platform TEXT,
      payment_method TEXT CHECK(payment_method IN ('credit_card','boleto','pix','paypal')),
      status TEXT NOT NULL DEFAULT 'waiting_payment' CHECK(status IN ('waiting_payment','paid','refused','refunded','chargedback')),
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
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      approved_at TEXT,
      refunded_at TEXT,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
      FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS tracking_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      order_id INTEGER,
      session_id TEXT,
      event_type TEXT NOT NULL CHECK(event_type IN ('click','pageview','purchase')),
      utm_source TEXT,
      utm_medium TEXT,
      utm_campaign TEXT,
      utm_content TEXT,
      utm_term TEXT,
      src TEXT,
      sck TEXT,
      page_url TEXT,
      referrer TEXT,
      user_agent TEXT,
      ip_address TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
      FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS campaigns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      platform TEXT CHECK(platform IN ('meta','google','tiktok','kwai','taboola')),
      ad_account_id TEXT,
      campaign_external_id TEXT,
      status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused')),
      daily_budget_in_cents INTEGER NOT NULL DEFAULT 0,
      total_spent_in_cents INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS ad_sets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      external_id TEXT,
      status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused')),
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS ads (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ad_set_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      external_id TEXT,
      creative_url TEXT,
      status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused')),
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (ad_set_id) REFERENCES ad_sets(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS ad_spend (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id INTEGER NOT NULL,
      ad_set_id INTEGER,
      ad_id INTEGER,
      date TEXT NOT NULL,
      spent_in_cents INTEGER NOT NULL DEFAULT 0,
      impressions INTEGER NOT NULL DEFAULT 0,
      clicks INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
      FOREIGN KEY (ad_set_id) REFERENCES ad_sets(id) ON DELETE SET NULL,
      FOREIGN KEY (ad_id) REFERENCES ads(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS automated_rules (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      active INTEGER NOT NULL DEFAULT 1,
      condition_metric TEXT NOT NULL CHECK(condition_metric IN ('cpa','roas','roi','spend')),
      condition_operator TEXT NOT NULL CHECK(condition_operator IN ('gt','lt','eq','gte','lte')),
      condition_value REAL NOT NULL,
      action_type TEXT NOT NULL CHECK(action_type IN ('pause','activate','notify')),
      target_type TEXT NOT NULL CHECK(target_type IN ('campaign','ad_set','ad')),
      check_interval_minutes INTEGER NOT NULL DEFAULT 60,
      last_executed_at TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS dashboards (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      is_default INTEGER NOT NULL DEFAULT 0,
      filters_json TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
    CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
    CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
    CREATE INDEX IF NOT EXISTS idx_orders_product_id ON orders(product_id);
    CREATE INDEX IF NOT EXISTS idx_tracking_events_user_id ON tracking_events(user_id);
    CREATE INDEX IF NOT EXISTS idx_tracking_events_order_id ON tracking_events(order_id);
    CREATE INDEX IF NOT EXISTS idx_tracking_events_session_id ON tracking_events(session_id);
    CREATE INDEX IF NOT EXISTS idx_tracking_events_utm_source ON tracking_events(utm_source);
    CREATE INDEX IF NOT EXISTS idx_tracking_events_created_at ON tracking_events(created_at);
    CREATE INDEX IF NOT EXISTS idx_campaigns_user_id ON campaigns(user_id);
    CREATE INDEX IF NOT EXISTS idx_ad_spend_campaign_id ON ad_spend(campaign_id);
    CREATE INDEX IF NOT EXISTS idx_ad_spend_date ON ad_spend(date);
    CREATE INDEX IF NOT EXISTS idx_api_credentials_token ON api_credentials(token);
  `);
}

function seedDemoData() {
  const existingUser = db.prepare('SELECT id FROM users WHERE email = ?').get('demo@trackpro.com');
  if (existingUser) return;

  const passwordHash = bcrypt.hashSync('demo123', 10);

  const insertUser = db.prepare('INSERT INTO users (name, email, password_hash, company) VALUES (?, ?, ?, ?)');
  const result = insertUser.run('Demo User', 'demo@trackpro.com', passwordHash, 'TrackPro Demo Inc.');
  const userId = result.lastInsertRowid;

  // API credential
  const apiToken = uuidv4();
  db.prepare('INSERT INTO api_credentials (user_id, name, token) VALUES (?, ?, ?)').run(userId, 'Default API Key', apiToken);

  // Products
  const insertProduct = db.prepare('INSERT INTO products (user_id, name, platform, cost_in_cents) VALUES (?, ?, ?, ?)');
  const prod1 = insertProduct.run(userId, 'Curso Marketing Digital', 'hotmart', 9900);
  const prod2 = insertProduct.run(userId, 'E-book SEO Avançado', 'hotmart', 4900);
  const prod3 = insertProduct.run(userId, 'Mentoria Growth Hacking', 'eduzz', 29900);
  const prod4 = insertProduct.run(userId, 'Plugin WP Turbo', 'monetizze', 14900);

  const productIds = [prod1.lastInsertRowid, prod2.lastInsertRowid, prod3.lastInsertRowid, prod4.lastInsertRowid];
  const productPrices = [19700, 9700, 59700, 29700];

  // Campaigns
  const insertCampaign = db.prepare('INSERT INTO campaigns (user_id, name, platform, ad_account_id, campaign_external_id, status, daily_budget_in_cents, total_spent_in_cents, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)');
  const camp1 = insertCampaign.run(userId, 'Meta - Curso MKT Digital - Conversão', 'meta', 'act_123456', 'camp_meta_001', 'active', 5000, 150000, '2024-01-01 10:00:00');
  const camp2 = insertCampaign.run(userId, 'Google - SEO Ebook - Search', 'google', 'acc_789012', 'camp_google_001', 'active', 3000, 90000, '2024-01-05 10:00:00');
  const camp3 = insertCampaign.run(userId, 'Meta - Mentoria Growth - Lookalike', 'meta', 'act_123456', 'camp_meta_002', 'active', 8000, 240000, '2024-01-10 10:00:00');
  const camp4 = insertCampaign.run(userId, 'TikTok - Plugin WP - Alcance', 'tiktok', 'tkt_345678', 'camp_tiktok_001', 'paused', 4000, 60000, '2024-01-15 10:00:00');

  const campaignIds = [camp1.lastInsertRowid, camp2.lastInsertRowid, camp3.lastInsertRowid, camp4.lastInsertRowid];

  // Ad Sets
  const insertAdSet = db.prepare('INSERT INTO ad_sets (campaign_id, name, external_id, status) VALUES (?, ?, ?, ?)');
  const adSet1 = insertAdSet.run(campaignIds[0], 'Interesse Marketing', 'adset_001', 'active');
  const adSet2 = insertAdSet.run(campaignIds[0], 'Lookalike 1%', 'adset_002', 'active');
  const adSet3 = insertAdSet.run(campaignIds[1], 'Keywords SEO', 'adset_003', 'active');
  const adSet4 = insertAdSet.run(campaignIds[2], 'LAL Compradores', 'adset_004', 'active');
  const adSet5 = insertAdSet.run(campaignIds[3], 'Broad TikTok', 'adset_005', 'paused');

  const adSetIds = [adSet1.lastInsertRowid, adSet2.lastInsertRowid, adSet3.lastInsertRowid, adSet4.lastInsertRowid, adSet5.lastInsertRowid];

  // Ads
  const insertAd = db.prepare('INSERT INTO ads (ad_set_id, name, external_id, creative_url, status) VALUES (?, ?, ?, ?, ?)');
  insertAd.run(adSetIds[0], 'Video Depoimento', 'ad_001', 'https://creative.example.com/video1.mp4', 'active');
  insertAd.run(adSetIds[0], 'Carrossel Resultados', 'ad_002', 'https://creative.example.com/carousel1.jpg', 'active');
  insertAd.run(adSetIds[1], 'Imagem Oferta', 'ad_003', 'https://creative.example.com/offer1.jpg', 'active');
  insertAd.run(adSetIds[2], 'Responsive Search Ad', 'ad_004', null, 'active');
  insertAd.run(adSetIds[3], 'Video Mentoria', 'ad_005', 'https://creative.example.com/mentoria.mp4', 'active');
  insertAd.run(adSetIds[4], 'TikTok Native', 'ad_006', 'https://creative.example.com/tiktok1.mp4', 'paused');

  // Ad Spend (last 30 days)
  const insertSpend = db.prepare('INSERT INTO ad_spend (campaign_id, ad_set_id, date, spent_in_cents, impressions, clicks) VALUES (?, ?, ?, ?, ?, ?)');
  for (let i = 30; i >= 0; i--) {
    const date = new Date();
    date.setDate(date.getDate() - i);
    const dateStr = date.toISOString().split('T')[0];

    insertSpend.run(campaignIds[0], adSetIds[0], dateStr, 2500 + Math.floor(Math.random() * 1500), 5000 + Math.floor(Math.random() * 3000), 80 + Math.floor(Math.random() * 60));
    insertSpend.run(campaignIds[1], adSetIds[2], dateStr, 1500 + Math.floor(Math.random() * 1000), 3000 + Math.floor(Math.random() * 2000), 60 + Math.floor(Math.random() * 40));
    insertSpend.run(campaignIds[2], adSetIds[3], dateStr, 4000 + Math.floor(Math.random() * 2000), 8000 + Math.floor(Math.random() * 4000), 120 + Math.floor(Math.random() * 80));
    if (i > 10) {
      insertSpend.run(campaignIds[3], adSetIds[4], dateStr, 2000 + Math.floor(Math.random() * 1000), 10000 + Math.floor(Math.random() * 5000), 150 + Math.floor(Math.random() * 100));
    }
  }

  // Orders (last 30 days, varied UTMs)
  const utmSources = ['facebook', 'google', 'tiktok', 'instagram', 'organic', 'email'];
  const utmMediums = ['cpc', 'cpm', 'organic', 'email', 'social'];
  const utmCampaigns = ['curso-mkt-conv', 'ebook-seo-search', 'mentoria-growth-lal', 'plugin-wp-alcance', 'remarketing-geral', 'email-lancamento'];
  const paymentMethods = ['credit_card', 'pix', 'boleto', 'paypal'];
  const statuses = ['paid', 'paid', 'paid', 'paid', 'waiting_payment', 'refused', 'refunded'];
  const firstNames = ['João', 'Maria', 'Pedro', 'Ana', 'Carlos', 'Juliana', 'Lucas', 'Fernanda', 'Rafael', 'Camila', 'Bruno', 'Larissa', 'Diego', 'Amanda', 'Gabriel'];
  const lastNames = ['Silva', 'Santos', 'Oliveira', 'Souza', 'Rodrigues', 'Ferreira', 'Almeida', 'Nascimento', 'Lima', 'Araújo'];

  const insertOrder = db.prepare('INSERT INTO orders (user_id, order_external_id, product_id, platform, payment_method, status, customer_name, customer_email, customer_phone, customer_document, customer_ip, price_in_cents, gateway_fee_in_cents, net_amount_in_cents, currency, is_test, created_at, approved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
  const insertEvent = db.prepare('INSERT INTO tracking_events (user_id, order_id, session_id, event_type, utm_source, utm_medium, utm_campaign, utm_content, utm_term, page_url, referrer, user_agent, ip_address, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');

  for (let i = 0; i < 120; i++) {
    const daysAgo = Math.floor(Math.random() * 30);
    const hoursAgo = Math.floor(Math.random() * 24);
    const date = new Date();
    date.setDate(date.getDate() - daysAgo);
    date.setHours(hoursAgo, Math.floor(Math.random() * 60), Math.floor(Math.random() * 60));
    const dateStr = date.toISOString().replace('T', ' ').substring(0, 19);

    const prodIdx = Math.floor(Math.random() * productIds.length);
    const productId = productIds[prodIdx];
    const price = productPrices[prodIdx];
    const gatewayFee = Math.floor(price * 0.05);
    const netAmount = price - gatewayFee;
    const status = statuses[Math.floor(Math.random() * statuses.length)];
    const paymentMethod = paymentMethods[Math.floor(Math.random() * paymentMethods.length)];
    const firstName = firstNames[Math.floor(Math.random() * firstNames.length)];
    const lastName = lastNames[Math.floor(Math.random() * lastNames.length)];
    const customerName = `${firstName} ${lastName}`;
    const customerEmail = `${firstName.toLowerCase()}.${lastName.toLowerCase()}${i}@email.com`;
    const ip = `${100 + Math.floor(Math.random() * 155)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${1 + Math.floor(Math.random() * 254)}`;
    const utmSource = utmSources[Math.floor(Math.random() * utmSources.length)];
    const utmMedium = utmMediums[Math.floor(Math.random() * utmMediums.length)];
    const utmCampaign = utmCampaigns[Math.floor(Math.random() * utmCampaigns.length)];

    const approvedAt = status === 'paid' ? dateStr : null;
    const platforms = ['hotmart', 'eduzz', 'monetizze'];

    const orderResult = insertOrder.run(
      userId,
      `ORD-${1000 + i}`,
      productId,
      platforms[prodIdx % platforms.length],
      paymentMethod,
      status,
      customerName,
      customerEmail,
      `+5511${90000000 + Math.floor(Math.random() * 9999999)}`,
      `${100 + Math.floor(Math.random() * 899)}.${100 + Math.floor(Math.random() * 899)}.${100 + Math.floor(Math.random() * 899)}-${10 + Math.floor(Math.random() * 89)}`,
      ip,
      price,
      gatewayFee,
      netAmount,
      'BRL',
      0,
      dateStr,
      approvedAt
    );

    const orderId = orderResult.lastInsertRowid;
    const sessionId = uuidv4();

    // Click event (before purchase)
    const clickDate = new Date(date);
    clickDate.setMinutes(clickDate.getMinutes() - Math.floor(Math.random() * 120) - 10);
    const clickDateStr = clickDate.toISOString().replace('T', ' ').substring(0, 19);

    insertEvent.run(
      userId, null, sessionId, 'click',
      utmSource, utmMedium, utmCampaign, `ad_${Math.floor(Math.random() * 10)}`, `keyword_${Math.floor(Math.random() * 5)}`,
      `https://example.com/sales?utm_source=${utmSource}&utm_medium=${utmMedium}&utm_campaign=${utmCampaign}`,
      `https://${utmSource}.com`,
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      ip,
      clickDateStr
    );

    // Pageview event
    const pvDate = new Date(clickDate);
    pvDate.setSeconds(pvDate.getSeconds() + Math.floor(Math.random() * 30) + 5);
    const pvDateStr = pvDate.toISOString().replace('T', ' ').substring(0, 19);

    insertEvent.run(
      userId, null, sessionId, 'pageview',
      utmSource, utmMedium, utmCampaign, `ad_${Math.floor(Math.random() * 10)}`, `keyword_${Math.floor(Math.random() * 5)}`,
      'https://example.com/sales',
      `https://${utmSource}.com`,
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      ip,
      pvDateStr
    );

    // Purchase event (if paid)
    if (status === 'paid') {
      insertEvent.run(
        userId, orderId, sessionId, 'purchase',
        utmSource, utmMedium, utmCampaign, `ad_${Math.floor(Math.random() * 10)}`, `keyword_${Math.floor(Math.random() * 5)}`,
        'https://example.com/checkout/thank-you',
        'https://example.com/sales',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        ip,
        dateStr
      );
    }
  }

  // Extra pageview events without orders
  for (let i = 0; i < 200; i++) {
    const daysAgo = Math.floor(Math.random() * 30);
    const date = new Date();
    date.setDate(date.getDate() - daysAgo);
    date.setHours(Math.floor(Math.random() * 24), Math.floor(Math.random() * 60));
    const dateStr = date.toISOString().replace('T', ' ').substring(0, 19);
    const utmSource = utmSources[Math.floor(Math.random() * utmSources.length)];
    const utmMedium = utmMediums[Math.floor(Math.random() * utmMediums.length)];
    const utmCampaign = utmCampaigns[Math.floor(Math.random() * utmCampaigns.length)];
    const ip = `${100 + Math.floor(Math.random() * 155)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${1 + Math.floor(Math.random() * 254)}`;

    insertEvent.run(
      userId, null, uuidv4(), 'pageview',
      utmSource, utmMedium, utmCampaign, null, null,
      'https://example.com/sales',
      `https://${utmSource}.com`,
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      ip,
      dateStr
    );
  }

  // Automated rules
  const insertRule = db.prepare('INSERT INTO automated_rules (user_id, name, active, condition_metric, condition_operator, condition_value, action_type, target_type, check_interval_minutes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)');
  insertRule.run(userId, 'Pause campaigns with CPA > R$50', 1, 'cpa', 'gt', 5000, 'pause', 'campaign', 60);
  insertRule.run(userId, 'Notify when ROAS < 2', 1, 'roas', 'lt', 2, 'notify', 'campaign', 120);
  insertRule.run(userId, 'Pause ads with spend > R$100 and no sale', 1, 'spend', 'gt', 10000, 'pause', 'ad', 30);

  // Default dashboard
  db.prepare('INSERT INTO dashboards (user_id, name, is_default, filters_json) VALUES (?, ?, ?, ?)').run(userId, 'Main Dashboard', 1, JSON.stringify({ date_range: 'last_30_days' }));

  console.log(`[Seed] Demo data created. API Token: ${apiToken}`);
}

module.exports = { getDb };
