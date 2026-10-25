const { getDb } = require('../config/database');
const { parseDateRange, calculateROAS, calculateROI, calculateCPA } = require('../utils/helpers');

/**
 * Get dashboard overview KPIs
 */
function getDashboardOverview(userId, filters = {}) {
  const db = getDb();
  const { startDate, endDate } = parseDateRange(filters.startDate, filters.endDate);

  let orderWhere = 'o.user_id = ? AND o.created_at >= ? AND o.created_at <= ?';
  const orderParams = [userId, startDate, endDate];

  if (filters.productId) {
    orderWhere += ' AND o.product_id = ?';
    orderParams.push(filters.productId);
  }
  if (filters.platform) {
    orderWhere += ' AND o.platform = ?';
    orderParams.push(filters.platform);
  }

  // Revenue and order counts
  const revenueResult = db.prepare(`
    SELECT
      COALESCE(SUM(CASE WHEN status = 'paid' THEN price_in_cents ELSE 0 END), 0) as total_revenue,
      COALESCE(SUM(CASE WHEN status = 'paid' THEN gateway_fee_in_cents ELSE 0 END), 0) as total_fees,
      COALESCE(SUM(CASE WHEN status = 'paid' THEN net_amount_in_cents ELSE 0 END), 0) as total_net,
      COUNT(*) as total_orders,
      SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_orders,
      SUM(CASE WHEN status = 'refunded' THEN 1 ELSE 0 END) as refunded_orders,
      SUM(CASE WHEN status = 'chargedback' THEN 1 ELSE 0 END) as chargedback_orders,
      SUM(CASE WHEN status = 'waiting_payment' THEN 1 ELSE 0 END) as waiting_orders,
      SUM(CASE WHEN status = 'refused' THEN 1 ELSE 0 END) as refused_orders
    FROM orders o
    WHERE ${orderWhere}
  `).get(...orderParams);

  // Today's stats
  const today = new Date().toISOString().split('T')[0];
  const todayParams = [userId, today + ' 00:00:00', today + ' 23:59:59'];
  if (filters.productId) todayParams.push(filters.productId);
  if (filters.platform) todayParams.push(filters.platform);

  let todayWhere = 'o.user_id = ? AND o.created_at >= ? AND o.created_at <= ?';
  if (filters.productId) todayWhere += ' AND o.product_id = ?';
  if (filters.platform) todayWhere += ' AND o.platform = ?';

  const todayResult = db.prepare(`
    SELECT
      COALESCE(SUM(CASE WHEN status = 'paid' THEN price_in_cents ELSE 0 END), 0) as revenue_today,
      COUNT(*) as orders_today,
      SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_orders_today
    FROM orders o
    WHERE ${todayWhere}
  `).get(...todayParams);

  // Total ad spend in range
  let spendWhere = 'c.user_id = ? AND s.date >= ? AND s.date <= ?';
  const spendParams = [userId, startDate.split(' ')[0], endDate.split(' ')[0]];

  const spendResult = db.prepare(`
    SELECT COALESCE(SUM(s.spent_in_cents), 0) as total_spent
    FROM ad_spend s
    JOIN campaigns c ON s.campaign_id = c.id
    WHERE ${spendWhere}
  `).get(...spendParams);

  const totalRevenue = revenueResult.total_revenue;
  const totalSpent = spendResult.total_spent;
  const paidOrders = revenueResult.paid_orders;

  return {
    total_revenue: totalRevenue,
    total_net_revenue: revenueResult.total_net,
    total_fees: revenueResult.total_fees,
    total_spent: totalSpent,
    total_orders: revenueResult.total_orders,
    paid_orders: paidOrders,
    refunded_orders: revenueResult.refunded_orders,
    chargedback_orders: revenueResult.chargedback_orders,
    waiting_orders: revenueResult.waiting_orders,
    refused_orders: revenueResult.refused_orders,
    roi: calculateROI(totalRevenue, totalSpent),
    roas: calculateROAS(totalRevenue, totalSpent),
    cpa: calculateCPA(totalSpent, paidOrders),
    orders_today: todayResult.orders_today,
    paid_orders_today: todayResult.paid_orders_today,
    revenue_today: todayResult.revenue_today,
    profit: totalRevenue - totalSpent - revenueResult.total_fees,
    date_range: { start_date: startDate, end_date: endDate }
  };
}

/**
 * Get revenue grouped by UTM source
 */
function getRevenueBySource(userId, startDate, endDate) {
  const db = getDb();
  const { startDate: sd, endDate: ed } = parseDateRange(startDate, endDate);

  return db.prepare(`
    SELECT
      te.utm_source,
      COUNT(DISTINCT te.order_id) as total_orders,
      COALESCE(SUM(o.price_in_cents), 0) as total_revenue,
      COUNT(DISTINCT te.session_id) as total_sessions,
      COUNT(DISTINCT CASE WHEN te.event_type = 'pageview' THEN te.id END) as total_pageviews,
      COUNT(DISTINCT CASE WHEN te.event_type = 'click' THEN te.id END) as total_clicks
    FROM tracking_events te
    LEFT JOIN orders o ON te.order_id = o.id AND o.status = 'paid'
    WHERE te.user_id = ? AND te.created_at >= ? AND te.created_at <= ?
    GROUP BY te.utm_source
    ORDER BY total_revenue DESC
  `).all(userId, sd, ed);
}

/**
 * Get revenue grouped by UTM campaign
 */
function getRevenueByCampaign(userId, startDate, endDate) {
  const db = getDb();
  const { startDate: sd, endDate: ed } = parseDateRange(startDate, endDate);

  return db.prepare(`
    SELECT
      te.utm_campaign,
      te.utm_source,
      COUNT(DISTINCT te.order_id) as total_orders,
      COALESCE(SUM(o.price_in_cents), 0) as total_revenue,
      COUNT(DISTINCT te.session_id) as total_sessions,
      COUNT(DISTINCT CASE WHEN te.event_type = 'click' THEN te.id END) as total_clicks
    FROM tracking_events te
    LEFT JOIN orders o ON te.order_id = o.id AND o.status = 'paid'
    WHERE te.user_id = ? AND te.created_at >= ? AND te.created_at <= ?
    GROUP BY te.utm_campaign, te.utm_source
    ORDER BY total_revenue DESC
  `).all(userId, sd, ed);
}

/**
 * Get revenue grouped by UTM medium
 */
function getRevenueByMedium(userId, startDate, endDate) {
  const db = getDb();
  const { startDate: sd, endDate: ed } = parseDateRange(startDate, endDate);

  return db.prepare(`
    SELECT
      te.utm_medium,
      COUNT(DISTINCT te.order_id) as total_orders,
      COALESCE(SUM(o.price_in_cents), 0) as total_revenue,
      COUNT(DISTINCT te.session_id) as total_sessions,
      COUNT(DISTINCT CASE WHEN te.event_type = 'click' THEN te.id END) as total_clicks
    FROM tracking_events te
    LEFT JOIN orders o ON te.order_id = o.id AND o.status = 'paid'
    WHERE te.user_id = ? AND te.created_at >= ? AND te.created_at <= ?
    GROUP BY te.utm_medium
    ORDER BY total_revenue DESC
  `).all(userId, sd, ed);
}

/**
 * Get revenue grouped by product
 */
function getRevenueByProduct(userId, startDate, endDate) {
  const db = getDb();
  const { startDate: sd, endDate: ed } = parseDateRange(startDate, endDate);

  return db.prepare(`
    SELECT
      p.id as product_id,
      p.name as product_name,
      p.platform,
      COUNT(o.id) as total_orders,
      SUM(CASE WHEN o.status = 'paid' THEN 1 ELSE 0 END) as paid_orders,
      COALESCE(SUM(CASE WHEN o.status = 'paid' THEN o.price_in_cents ELSE 0 END), 0) as total_revenue,
      COALESCE(SUM(CASE WHEN o.status = 'paid' THEN o.gateway_fee_in_cents ELSE 0 END), 0) as total_fees,
      COALESCE(SUM(CASE WHEN o.status = 'paid' THEN o.net_amount_in_cents ELSE 0 END), 0) as total_net,
      SUM(CASE WHEN o.status = 'refunded' THEN 1 ELSE 0 END) as refunded_orders
    FROM products p
    LEFT JOIN orders o ON p.id = o.product_id AND o.created_at >= ? AND o.created_at <= ?
    WHERE p.user_id = ?
    GROUP BY p.id
    ORDER BY total_revenue DESC
  `).all(sd, ed, userId);
}

/**
 * Get daily revenue/orders over time
 */
function getRevenueByDay(userId, startDate, endDate) {
  const db = getDb();
  const { startDate: sd, endDate: ed } = parseDateRange(startDate, endDate);

  return db.prepare(`
    SELECT
      date(o.created_at) as date,
      COUNT(*) as total_orders,
      SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_orders,
      COALESCE(SUM(CASE WHEN status = 'paid' THEN price_in_cents ELSE 0 END), 0) as revenue,
      COALESCE(SUM(CASE WHEN status = 'paid' THEN net_amount_in_cents ELSE 0 END), 0) as net_revenue,
      SUM(CASE WHEN status = 'refunded' THEN 1 ELSE 0 END) as refunded_orders
    FROM orders o
    WHERE o.user_id = ? AND o.created_at >= ? AND o.created_at <= ?
    GROUP BY date(o.created_at)
    ORDER BY date ASC
  `).all(userId, sd, ed);
}

/**
 * Get financial report with costs, fees, net profit
 */
function getFinancialReport(userId, startDate, endDate) {
  const db = getDb();
  const { startDate: sd, endDate: ed } = parseDateRange(startDate, endDate);

  const revenue = db.prepare(`
    SELECT
      COALESCE(SUM(CASE WHEN status = 'paid' THEN price_in_cents ELSE 0 END), 0) as gross_revenue,
      COALESCE(SUM(CASE WHEN status = 'paid' THEN gateway_fee_in_cents ELSE 0 END), 0) as gateway_fees,
      COALESCE(SUM(CASE WHEN status = 'paid' THEN net_amount_in_cents ELSE 0 END), 0) as net_revenue,
      COALESCE(SUM(CASE WHEN status = 'refunded' THEN price_in_cents ELSE 0 END), 0) as refunded_amount,
      SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_count,
      SUM(CASE WHEN status = 'refunded' THEN 1 ELSE 0 END) as refund_count,
      COUNT(*) as total_orders
    FROM orders
    WHERE user_id = ? AND created_at >= ? AND created_at <= ?
  `).get(userId, sd, ed);

  const adSpend = db.prepare(`
    SELECT COALESCE(SUM(s.spent_in_cents), 0) as total_ad_spend
    FROM ad_spend s
    JOIN campaigns c ON s.campaign_id = c.id
    WHERE c.user_id = ? AND s.date >= ? AND s.date <= ?
  `).get(userId, sd.split(' ')[0], ed.split(' ')[0]);

  const productCosts = db.prepare(`
    SELECT COALESCE(SUM(p.cost_in_cents), 0) as total_product_costs
    FROM orders o
    JOIN products p ON o.product_id = p.id
    WHERE o.user_id = ? AND o.status = 'paid' AND o.created_at >= ? AND o.created_at <= ?
  `).get(userId, sd, ed);

  const grossRevenue = revenue.gross_revenue;
  const totalCosts = adSpend.total_ad_spend + revenue.gateway_fees + productCosts.total_product_costs;
  const netProfit = grossRevenue - totalCosts - revenue.refunded_amount;

  return {
    gross_revenue: grossRevenue,
    gateway_fees: revenue.gateway_fees,
    net_revenue: revenue.net_revenue,
    refunded_amount: revenue.refunded_amount,
    ad_spend: adSpend.total_ad_spend,
    product_costs: productCosts.total_product_costs,
    total_costs: totalCosts,
    net_profit: netProfit,
    profit_margin: grossRevenue > 0 ? parseFloat(((netProfit / grossRevenue) * 100).toFixed(2)) : 0,
    roi: calculateROI(grossRevenue, totalCosts),
    roas: calculateROAS(grossRevenue, adSpend.total_ad_spend),
    cpa: calculateCPA(adSpend.total_ad_spend, revenue.paid_count),
    order_stats: {
      total: revenue.total_orders,
      paid: revenue.paid_count,
      refunded: revenue.refund_count
    },
    date_range: { start_date: sd, end_date: ed }
  };
}

/**
 * Get campaign performance with attribution
 */
function getCampaignPerformance(userId, startDate, endDate) {
  const db = getDb();
  const { startDate: sd, endDate: ed } = parseDateRange(startDate, endDate);

  const campaigns = db.prepare('SELECT * FROM campaigns WHERE user_id = ?').all(userId);

  return campaigns.map(campaign => {
    const spend = db.prepare(`
      SELECT
        COALESCE(SUM(spent_in_cents), 0) as total_spent,
        COALESCE(SUM(impressions), 0) as total_impressions,
        COALESCE(SUM(clicks), 0) as total_clicks
      FROM ad_spend
      WHERE campaign_id = ? AND date >= ? AND date <= ?
    `).get(campaign.id, sd.split(' ')[0], ed.split(' ')[0]);

    // Attribution: find orders linked through tracking events matching this campaign
    const attribution = db.prepare(`
      SELECT
        COUNT(DISTINCT o.id) as attributed_orders,
        COALESCE(SUM(o.price_in_cents), 0) as attributed_revenue
      FROM tracking_events te
      JOIN orders o ON te.order_id = o.id AND o.status = 'paid'
      WHERE te.user_id = ? AND te.utm_campaign = ?
      AND te.created_at >= ? AND te.created_at <= ?
    `).get(userId, campaign.campaign_external_id, sd, ed);

    const totalSpent = spend.total_spent;
    const attributedRevenue = attribution.attributed_revenue;
    const attributedOrders = attribution.attributed_orders;

    return {
      ...campaign,
      spend: {
        total_spent: totalSpent,
        total_impressions: spend.total_impressions,
        total_clicks: spend.total_clicks,
        cpc: spend.total_clicks > 0 ? Math.round(totalSpent / spend.total_clicks) : 0,
        cpm: spend.total_impressions > 0 ? Math.round((totalSpent / spend.total_impressions) * 1000) : 0
      },
      attribution: {
        attributed_orders: attributedOrders,
        attributed_revenue: attributedRevenue,
        roas: calculateROAS(attributedRevenue, totalSpent),
        roi: calculateROI(attributedRevenue, totalSpent),
        cpa: calculateCPA(totalSpent, attributedOrders)
      }
    };
  });
}

module.exports = {
  getDashboardOverview,
  getRevenueBySource,
  getRevenueByCampaign,
  getRevenueByMedium,
  getRevenueByProduct,
  getRevenueByDay,
  getFinancialReport,
  getCampaignPerformance
};
