const { getDb } = require('../config/database');
const { RuleModel, CampaignModel, AdSetModel, AdModel } = require('../models');
const { calculateROAS, calculateROI, calculateCPA } = require('../utils/helpers');

/**
 * Evaluate a rule's condition against a metric value
 */
function evaluateCondition(operator, metricValue, conditionValue) {
  switch (operator) {
    case 'gt': return metricValue > conditionValue;
    case 'lt': return metricValue < conditionValue;
    case 'eq': return metricValue === conditionValue;
    case 'gte': return metricValue >= conditionValue;
    case 'lte': return metricValue <= conditionValue;
    default: return false;
  }
}

/**
 * Get the current metric value for a target
 */
function getMetricValue(userId, metric, targetType, targetId) {
  const db = getDb();

  // Get recent spend data (last 7 days)
  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
  const startDate = sevenDaysAgo.toISOString().split('T')[0];
  const endDate = new Date().toISOString().split('T')[0];

  let totalSpent = 0;
  let totalRevenue = 0;
  let totalOrders = 0;

  if (targetType === 'campaign') {
    const spendResult = db.prepare(`
      SELECT COALESCE(SUM(spent_in_cents), 0) as total
      FROM ad_spend WHERE campaign_id = ? AND date >= ? AND date <= ?
    `).get(targetId, startDate, endDate);
    totalSpent = spendResult.total;

    const revenueResult = db.prepare(`
      SELECT COUNT(DISTINCT o.id) as orders, COALESCE(SUM(o.price_in_cents), 0) as revenue
      FROM tracking_events te
      JOIN orders o ON te.order_id = o.id AND o.status = 'paid'
      JOIN campaigns c ON c.id = ?
      WHERE te.user_id = ? AND te.utm_campaign = c.campaign_external_id
      AND te.created_at >= ? AND te.created_at <= ?
    `).get(targetId, userId, startDate + ' 00:00:00', endDate + ' 23:59:59');
    totalRevenue = revenueResult.revenue;
    totalOrders = revenueResult.orders;
  } else if (targetType === 'ad_set') {
    const spendResult = db.prepare(`
      SELECT COALESCE(SUM(spent_in_cents), 0) as total
      FROM ad_spend WHERE ad_set_id = ? AND date >= ? AND date <= ?
    `).get(targetId, startDate, endDate);
    totalSpent = spendResult.total;
  } else if (targetType === 'ad') {
    const spendResult = db.prepare(`
      SELECT COALESCE(SUM(spent_in_cents), 0) as total
      FROM ad_spend WHERE ad_id = ? AND date >= ? AND date <= ?
    `).get(targetId, startDate, endDate);
    totalSpent = spendResult.total;
  }

  switch (metric) {
    case 'cpa': return calculateCPA(totalSpent, totalOrders);
    case 'roas': return calculateROAS(totalRevenue, totalSpent);
    case 'roi': return calculateROI(totalRevenue, totalSpent);
    case 'spend': return totalSpent;
    default: return 0;
  }
}

/**
 * Get all targets for a given rule's target type
 */
function getTargets(userId, targetType) {
  const db = getDb();
  switch (targetType) {
    case 'campaign':
      return db.prepare('SELECT id, name, status FROM campaigns WHERE user_id = ? AND status = ?').all(userId, 'active');
    case 'ad_set':
      return db.prepare(`
        SELECT ads.id, ads.name, ads.status
        FROM ad_sets ads
        JOIN campaigns c ON ads.campaign_id = c.id
        WHERE c.user_id = ? AND ads.status = ?
      `).all(userId, 'active');
    case 'ad':
      return db.prepare(`
        SELECT a.id, a.name, a.status
        FROM ads a
        JOIN ad_sets ads ON a.ad_set_id = ads.id
        JOIN campaigns c ON ads.campaign_id = c.id
        WHERE c.user_id = ? AND a.status = ?
      `).all(userId, 'active');
    default:
      return [];
  }
}

/**
 * Execute a single rule
 */
function executeRule(ruleId, userId) {
  const rule = RuleModel.findById(ruleId, userId);
  if (!rule) {
    return { success: false, error: 'Rule not found' };
  }

  const targets = getTargets(userId, rule.target_type);
  const results = [];

  for (const target of targets) {
    const metricValue = getMetricValue(userId, rule.condition_metric, rule.target_type, target.id);
    const conditionMet = evaluateCondition(rule.condition_operator, metricValue, rule.condition_value);

    if (conditionMet) {
      let actionResult = null;

      switch (rule.action_type) {
        case 'pause':
          actionResult = applyAction(rule.target_type, target.id, 'paused');
          break;
        case 'activate':
          actionResult = applyAction(rule.target_type, target.id, 'active');
          break;
        case 'notify':
          actionResult = {
            notification: `Rule "${rule.name}" triggered for ${rule.target_type} "${target.name}": ${rule.condition_metric} = ${metricValue} ${rule.condition_operator} ${rule.condition_value}`
          };
          break;
      }

      results.push({
        target_id: target.id,
        target_name: target.name,
        metric_value: metricValue,
        condition_met: true,
        action_type: rule.action_type,
        action_result: actionResult
      });
    } else {
      results.push({
        target_id: target.id,
        target_name: target.name,
        metric_value: metricValue,
        condition_met: false,
        action_type: null,
        action_result: null
      });
    }
  }

  // Update last executed timestamp
  RuleModel.updateLastExecuted(ruleId);

  return {
    success: true,
    rule: {
      id: rule.id,
      name: rule.name,
      condition: `${rule.condition_metric} ${rule.condition_operator} ${rule.condition_value}`,
      action_type: rule.action_type,
      target_type: rule.target_type
    },
    targets_evaluated: targets.length,
    actions_triggered: results.filter(r => r.condition_met).length,
    results
  };
}

/**
 * Apply a status change action to a target
 */
function applyAction(targetType, targetId, newStatus) {
  const db = getDb();
  switch (targetType) {
    case 'campaign':
      db.prepare("UPDATE campaigns SET status = ?, updated_at = datetime('now') WHERE id = ?").run(newStatus, targetId);
      return { new_status: newStatus };
    case 'ad_set':
      db.prepare('UPDATE ad_sets SET status = ? WHERE id = ?').run(newStatus, targetId);
      return { new_status: newStatus };
    case 'ad':
      db.prepare('UPDATE ads SET status = ? WHERE id = ?').run(newStatus, targetId);
      return { new_status: newStatus };
    default:
      return null;
  }
}

module.exports = {
  executeRule,
  evaluateCondition,
  getMetricValue,
  getTargets
};
