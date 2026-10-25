const { getDb } = require('../config/database');

// ==================== USERS ====================

const UserModel = {
  findByEmail(email) {
    const db = getDb();
    return db.prepare('SELECT * FROM users WHERE email = ?').get(email);
  },

  findById(id) {
    const db = getDb();
    return db.prepare('SELECT id, name, email, company, created_at FROM users WHERE id = ?').get(id);
  },

  create({ name, email, passwordHash, company }) {
    const db = getDb();
    const result = db.prepare('INSERT INTO users (name, email, password_hash, company) VALUES (?, ?, ?, ?)').run(name, email, passwordHash, company || null);
    return { id: result.lastInsertRowid, name, email, company };
  }
};

// ==================== API CREDENTIALS ====================

const ApiCredentialModel = {
  findByUserId(userId) {
    const db = getDb();
    return db.prepare('SELECT id, user_id, name, token, active, created_at FROM api_credentials WHERE user_id = ? ORDER BY created_at DESC').all(userId);
  },

  findByToken(token) {
    const db = getDb();
    return db.prepare('SELECT * FROM api_credentials WHERE token = ?').get(token);
  },

  findById(id, userId) {
    const db = getDb();
    return db.prepare('SELECT * FROM api_credentials WHERE id = ? AND user_id = ?').get(id, userId);
  },

  create({ userId, name, token }) {
    const db = getDb();
    const result = db.prepare('INSERT INTO api_credentials (user_id, name, token) VALUES (?, ?, ?)').run(userId, name, token);
    return { id: result.lastInsertRowid, user_id: userId, name, token, active: 1 };
  },

  update(id, userId, { name, active }) {
    const db = getDb();
    const fields = [];
    const params = [];
    if (name !== undefined) { fields.push('name = ?'); params.push(name); }
    if (active !== undefined) { fields.push('active = ?'); params.push(active ? 1 : 0); }
    if (fields.length === 0) return null;
    params.push(id, userId);
    db.prepare(`UPDATE api_credentials SET ${fields.join(', ')} WHERE id = ? AND user_id = ?`).run(...params);
    return this.findById(id, userId);
  },

  delete(id, userId) {
    const db = getDb();
    return db.prepare('DELETE FROM api_credentials WHERE id = ? AND user_id = ?').run(id, userId);
  }
};

// ==================== PRODUCTS ====================

const ProductModel = {
  findByUserId(userId) {
    const db = getDb();
    return db.prepare('SELECT * FROM products WHERE user_id = ? ORDER BY created_at DESC').all(userId);
  },

  findById(id, userId) {
    const db = getDb();
    return db.prepare('SELECT * FROM products WHERE id = ? AND user_id = ?').get(id, userId);
  },

  create({ userId, name, platform, costInCents }) {
    const db = getDb();
    const result = db.prepare('INSERT INTO products (user_id, name, platform, cost_in_cents) VALUES (?, ?, ?, ?)').run(userId, name, platform || null, costInCents || 0);
    return this.findById(result.lastInsertRowid, userId);
  },

  update(id, userId, data) {
    const db = getDb();
    const fields = [];
    const params = [];
    if (data.name !== undefined) { fields.push('name = ?'); params.push(data.name); }
    if (data.platform !== undefined) { fields.push('platform = ?'); params.push(data.platform); }
    if (data.costInCents !== undefined) { fields.push('cost_in_cents = ?'); params.push(data.costInCents); }
    if (data.active !== undefined) { fields.push('active = ?'); params.push(data.active ? 1 : 0); }
    if (fields.length === 0) return null;
    params.push(id, userId);
    db.prepare(`UPDATE products SET ${fields.join(', ')} WHERE id = ? AND user_id = ?`).run(...params);
    return this.findById(id, userId);
  },

  delete(id, userId) {
    const db = getDb();
    return db.prepare('DELETE FROM products WHERE id = ? AND user_id = ?').run(id, userId);
  }
};

// ==================== ORDERS ====================

const OrderModel = {
  findById(id, userId) {
    const db = getDb();
    return db.prepare(`
      SELECT o.*, p.name as product_name
      FROM orders o
      LEFT JOIN products p ON o.product_id = p.id
      WHERE o.id = ? AND o.user_id = ?
    `).get(id, userId);
  },

  findByExternalId(externalId, userId) {
    const db = getDb();
    return db.prepare('SELECT * FROM orders WHERE order_external_id = ? AND user_id = ?').get(externalId, userId);
  },

  list(userId, filters = {}) {
    const db = getDb();
    let sql = `
      SELECT o.*, p.name as product_name
      FROM orders o
      LEFT JOIN products p ON o.product_id = p.id
      WHERE o.user_id = ?
    `;
    const params = [userId];

    if (filters.status) {
      sql += ' AND o.status = ?';
      params.push(filters.status);
    }
    if (filters.productId) {
      sql += ' AND o.product_id = ?';
      params.push(filters.productId);
    }
    if (filters.paymentMethod) {
      sql += ' AND o.payment_method = ?';
      params.push(filters.paymentMethod);
    }
    if (filters.platform) {
      sql += ' AND o.platform = ?';
      params.push(filters.platform);
    }
    if (filters.startDate) {
      sql += ' AND o.created_at >= ?';
      params.push(filters.startDate);
    }
    if (filters.endDate) {
      sql += ' AND o.created_at <= ?';
      params.push(filters.endDate);
    }
    if (filters.search) {
      sql += ' AND (o.customer_name LIKE ? OR o.customer_email LIKE ? OR o.order_external_id LIKE ?)';
      const searchTerm = `%${filters.search}%`;
      params.push(searchTerm, searchTerm, searchTerm);
    }

    // Count total
    const countSql = sql.replace(/SELECT o\.\*, p\.name as product_name/, 'SELECT COUNT(*) as total');
    const countResult = db.prepare(countSql).get(...params);

    sql += ' ORDER BY o.created_at DESC';

    if (filters.limit) {
      sql += ' LIMIT ?';
      params.push(filters.limit);
    }
    if (filters.offset !== undefined) {
      sql += ' OFFSET ?';
      params.push(filters.offset);
    }

    const rows = db.prepare(sql).all(...params);
    return { orders: rows, total: countResult.total };
  },

  create(data) {
    const db = getDb();
    const result = db.prepare(`
      INSERT INTO orders (user_id, order_external_id, product_id, platform, payment_method, status,
        customer_name, customer_email, customer_phone, customer_document, customer_ip,
        price_in_cents, gateway_fee_in_cents, net_amount_in_cents, currency, is_test, approved_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      data.userId, data.orderExternalId || null, data.productId || null, data.platform || null,
      data.paymentMethod || null, data.status || 'waiting_payment',
      data.customerName || null, data.customerEmail || null, data.customerPhone || null,
      data.customerDocument || null, data.customerIp || null,
      data.priceInCents || 0, data.gatewayFeeInCents || 0, data.netAmountInCents || 0,
      data.currency || 'BRL', data.isTest ? 1 : 0,
      data.status === 'paid' ? new Date().toISOString().replace('T', ' ').substring(0, 19) : null
    );
    return this.findById(result.lastInsertRowid, data.userId);
  },

  updateStatus(id, userId, status) {
    const db = getDb();
    const updates = { status };
    if (status === 'paid') {
      db.prepare('UPDATE orders SET status = ?, approved_at = datetime(\'now\') WHERE id = ? AND user_id = ?').run(status, id, userId);
    } else if (status === 'refunded') {
      db.prepare('UPDATE orders SET status = ?, refunded_at = datetime(\'now\') WHERE id = ? AND user_id = ?').run(status, id, userId);
    } else {
      db.prepare('UPDATE orders SET status = ? WHERE id = ? AND user_id = ?').run(status, id, userId);
    }
    return this.findById(id, userId);
  }
};

// ==================== TRACKING EVENTS ====================

const TrackingEventModel = {
  create(data) {
    const db = getDb();
    const result = db.prepare(`
      INSERT INTO tracking_events (user_id, order_id, session_id, event_type,
        utm_source, utm_medium, utm_campaign, utm_content, utm_term,
        src, sck, page_url, referrer, user_agent, ip_address)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      data.userId, data.orderId || null, data.sessionId || null, data.eventType,
      data.utmSource || null, data.utmMedium || null, data.utmCampaign || null,
      data.utmContent || null, data.utmTerm || null,
      data.src || null, data.sck || null,
      data.pageUrl || null, data.referrer || null,
      data.userAgent || null, data.ipAddress || null
    );
    return { id: result.lastInsertRowid };
  },

  findByOrderId(orderId) {
    const db = getDb();
    return db.prepare('SELECT * FROM tracking_events WHERE order_id = ? ORDER BY created_at ASC').all(orderId);
  },

  findBySessionId(sessionId) {
    const db = getDb();
    return db.prepare('SELECT * FROM tracking_events WHERE session_id = ? ORDER BY created_at ASC').all(sessionId);
  }
};

// ==================== CAMPAIGNS ====================

const CampaignModel = {
  findByUserId(userId) {
    const db = getDb();
    return db.prepare('SELECT * FROM campaigns WHERE user_id = ? ORDER BY created_at DESC').all(userId);
  },

  findById(id, userId) {
    const db = getDb();
    return db.prepare('SELECT * FROM campaigns WHERE id = ? AND user_id = ?').get(id, userId);
  },

  create(data) {
    const db = getDb();
    const result = db.prepare(`
      INSERT INTO campaigns (user_id, name, platform, ad_account_id, campaign_external_id, status, daily_budget_in_cents)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(data.userId, data.name, data.platform || null, data.adAccountId || null, data.campaignExternalId || null, data.status || 'active', data.dailyBudgetInCents || 0);
    return this.findById(result.lastInsertRowid, data.userId);
  },

  update(id, userId, data) {
    const db = getDb();
    const fields = [];
    const params = [];
    if (data.name !== undefined) { fields.push('name = ?'); params.push(data.name); }
    if (data.platform !== undefined) { fields.push('platform = ?'); params.push(data.platform); }
    if (data.adAccountId !== undefined) { fields.push('ad_account_id = ?'); params.push(data.adAccountId); }
    if (data.campaignExternalId !== undefined) { fields.push('campaign_external_id = ?'); params.push(data.campaignExternalId); }
    if (data.status !== undefined) { fields.push('status = ?'); params.push(data.status); }
    if (data.dailyBudgetInCents !== undefined) { fields.push('daily_budget_in_cents = ?'); params.push(data.dailyBudgetInCents); }
    fields.push("updated_at = datetime('now')");
    if (fields.length === 1) return null;
    params.push(id, userId);
    db.prepare(`UPDATE campaigns SET ${fields.join(', ')} WHERE id = ? AND user_id = ?`).run(...params);
    return this.findById(id, userId);
  },

  delete(id, userId) {
    const db = getDb();
    return db.prepare('DELETE FROM campaigns WHERE id = ? AND user_id = ?').run(id, userId);
  },

  updateSpent(id, spentInCents) {
    const db = getDb();
    db.prepare('UPDATE campaigns SET total_spent_in_cents = total_spent_in_cents + ? WHERE id = ?').run(spentInCents, id);
  }
};

// ==================== AD SETS ====================

const AdSetModel = {
  findByCampaignId(campaignId) {
    const db = getDb();
    return db.prepare('SELECT * FROM ad_sets WHERE campaign_id = ? ORDER BY created_at DESC').all(campaignId);
  },

  findById(id) {
    const db = getDb();
    return db.prepare('SELECT * FROM ad_sets WHERE id = ?').get(id);
  },

  create(data) {
    const db = getDb();
    const result = db.prepare('INSERT INTO ad_sets (campaign_id, name, external_id, status) VALUES (?, ?, ?, ?)').run(data.campaignId, data.name, data.externalId || null, data.status || 'active');
    return this.findById(result.lastInsertRowid);
  },

  update(id, data) {
    const db = getDb();
    const fields = [];
    const params = [];
    if (data.name !== undefined) { fields.push('name = ?'); params.push(data.name); }
    if (data.externalId !== undefined) { fields.push('external_id = ?'); params.push(data.externalId); }
    if (data.status !== undefined) { fields.push('status = ?'); params.push(data.status); }
    if (fields.length === 0) return null;
    params.push(id);
    db.prepare(`UPDATE ad_sets SET ${fields.join(', ')} WHERE id = ?`).run(...params);
    return this.findById(id);
  },

  delete(id) {
    const db = getDb();
    return db.prepare('DELETE FROM ad_sets WHERE id = ?').run(id);
  }
};

// ==================== ADS ====================

const AdModel = {
  findByAdSetId(adSetId) {
    const db = getDb();
    return db.prepare('SELECT * FROM ads WHERE ad_set_id = ? ORDER BY created_at DESC').all(adSetId);
  },

  findById(id) {
    const db = getDb();
    return db.prepare('SELECT * FROM ads WHERE id = ?').get(id);
  },

  create(data) {
    const db = getDb();
    const result = db.prepare('INSERT INTO ads (ad_set_id, name, external_id, creative_url, status) VALUES (?, ?, ?, ?, ?)').run(data.adSetId, data.name, data.externalId || null, data.creativeUrl || null, data.status || 'active');
    return this.findById(result.lastInsertRowid);
  },

  update(id, data) {
    const db = getDb();
    const fields = [];
    const params = [];
    if (data.name !== undefined) { fields.push('name = ?'); params.push(data.name); }
    if (data.externalId !== undefined) { fields.push('external_id = ?'); params.push(data.externalId); }
    if (data.creativeUrl !== undefined) { fields.push('creative_url = ?'); params.push(data.creativeUrl); }
    if (data.status !== undefined) { fields.push('status = ?'); params.push(data.status); }
    if (fields.length === 0) return null;
    params.push(id);
    db.prepare(`UPDATE ads SET ${fields.join(', ')} WHERE id = ?`).run(...params);
    return this.findById(id);
  },

  delete(id) {
    const db = getDb();
    return db.prepare('DELETE FROM ads WHERE id = ?').run(id);
  }
};

// ==================== AD SPEND ====================

const AdSpendModel = {
  create(data) {
    const db = getDb();
    const result = db.prepare(`
      INSERT INTO ad_spend (campaign_id, ad_set_id, ad_id, date, spent_in_cents, impressions, clicks)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(data.campaignId, data.adSetId || null, data.adId || null, data.date, data.spentInCents || 0, data.impressions || 0, data.clicks || 0);
    return { id: result.lastInsertRowid };
  },

  getByCampaign(campaignId, startDate, endDate) {
    const db = getDb();
    let sql = 'SELECT * FROM ad_spend WHERE campaign_id = ?';
    const params = [campaignId];
    if (startDate) { sql += ' AND date >= ?'; params.push(startDate); }
    if (endDate) { sql += ' AND date <= ?'; params.push(endDate); }
    sql += ' ORDER BY date DESC';
    return db.prepare(sql).all(...params);
  },

  getTotalSpent(campaignId, startDate, endDate) {
    const db = getDb();
    let sql = 'SELECT COALESCE(SUM(spent_in_cents), 0) as total FROM ad_spend WHERE campaign_id = ?';
    const params = [campaignId];
    if (startDate) { sql += ' AND date >= ?'; params.push(startDate); }
    if (endDate) { sql += ' AND date <= ?'; params.push(endDate); }
    return db.prepare(sql).get(...params).total;
  }
};

// ==================== AUTOMATED RULES ====================

const RuleModel = {
  findByUserId(userId) {
    const db = getDb();
    return db.prepare('SELECT * FROM automated_rules WHERE user_id = ? ORDER BY created_at DESC').all(userId);
  },

  findById(id, userId) {
    const db = getDb();
    return db.prepare('SELECT * FROM automated_rules WHERE id = ? AND user_id = ?').get(id, userId);
  },

  create(data) {
    const db = getDb();
    const result = db.prepare(`
      INSERT INTO automated_rules (user_id, name, active, condition_metric, condition_operator, condition_value, action_type, target_type, check_interval_minutes)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(data.userId, data.name, data.active !== undefined ? (data.active ? 1 : 0) : 1, data.conditionMetric, data.conditionOperator, data.conditionValue, data.actionType, data.targetType, data.checkIntervalMinutes || 60);
    return this.findById(result.lastInsertRowid, data.userId);
  },

  update(id, userId, data) {
    const db = getDb();
    const fields = [];
    const params = [];
    if (data.name !== undefined) { fields.push('name = ?'); params.push(data.name); }
    if (data.active !== undefined) { fields.push('active = ?'); params.push(data.active ? 1 : 0); }
    if (data.conditionMetric !== undefined) { fields.push('condition_metric = ?'); params.push(data.conditionMetric); }
    if (data.conditionOperator !== undefined) { fields.push('condition_operator = ?'); params.push(data.conditionOperator); }
    if (data.conditionValue !== undefined) { fields.push('condition_value = ?'); params.push(data.conditionValue); }
    if (data.actionType !== undefined) { fields.push('action_type = ?'); params.push(data.actionType); }
    if (data.targetType !== undefined) { fields.push('target_type = ?'); params.push(data.targetType); }
    if (data.checkIntervalMinutes !== undefined) { fields.push('check_interval_minutes = ?'); params.push(data.checkIntervalMinutes); }
    if (fields.length === 0) return null;
    params.push(id, userId);
    db.prepare(`UPDATE automated_rules SET ${fields.join(', ')} WHERE id = ? AND user_id = ?`).run(...params);
    return this.findById(id, userId);
  },

  updateLastExecuted(id) {
    const db = getDb();
    db.prepare("UPDATE automated_rules SET last_executed_at = datetime('now') WHERE id = ?").run(id);
  },

  delete(id, userId) {
    const db = getDb();
    return db.prepare('DELETE FROM automated_rules WHERE id = ? AND user_id = ?').run(id, userId);
  }
};

// ==================== DASHBOARDS ====================

const DashboardModel = {
  findByUserId(userId) {
    const db = getDb();
    return db.prepare('SELECT * FROM dashboards WHERE user_id = ? ORDER BY is_default DESC, created_at DESC').all(userId);
  },

  findById(id, userId) {
    const db = getDb();
    return db.prepare('SELECT * FROM dashboards WHERE id = ? AND user_id = ?').get(id, userId);
  }
};

module.exports = {
  UserModel,
  ApiCredentialModel,
  ProductModel,
  OrderModel,
  TrackingEventModel,
  CampaignModel,
  AdSetModel,
  AdModel,
  AdSpendModel,
  RuleModel,
  DashboardModel
};
