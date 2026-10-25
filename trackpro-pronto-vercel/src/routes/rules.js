const express = require('express');
const { authenticate } = require('../middleware/auth');
const { RuleModel } = require('../models');
const { executeRule } = require('../services/rules-engine');

const router = express.Router();

/**
 * GET /api/rules
 * List all automated rules
 */
router.get('/', authenticate, (req, res) => {
  try {
    const rules = RuleModel.findByUserId(req.user.id);
    return res.json({ rules });
  } catch (err) {
    console.error('List rules error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * GET /api/rules/:id
 * Get a single rule
 */
router.get('/:id', authenticate, (req, res) => {
  try {
    const rule = RuleModel.findById(parseInt(req.params.id), req.user.id);
    if (!rule) {
      return res.status(404).json({ error: 'Rule not found.' });
    }
    return res.json({ rule });
  } catch (err) {
    console.error('Get rule error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * POST /api/rules
 * Create a new automated rule
 */
router.post('/', authenticate, (req, res) => {
  try {
    const {
      name, active, condition_metric, condition_operator, condition_value,
      action_type, target_type, check_interval_minutes
    } = req.body;

    if (!name || !condition_metric || !condition_operator || condition_value === undefined || !action_type || !target_type) {
      return res.status(400).json({ error: 'Required fields: name, condition_metric, condition_operator, condition_value, action_type, target_type.' });
    }

    const validMetrics = ['cpa', 'roas', 'roi', 'spend'];
    const validOperators = ['gt', 'lt', 'eq', 'gte', 'lte'];
    const validActions = ['pause', 'activate', 'notify'];
    const validTargets = ['campaign', 'ad_set', 'ad'];

    if (!validMetrics.includes(condition_metric)) {
      return res.status(400).json({ error: `condition_metric must be one of: ${validMetrics.join(', ')}` });
    }
    if (!validOperators.includes(condition_operator)) {
      return res.status(400).json({ error: `condition_operator must be one of: ${validOperators.join(', ')}` });
    }
    if (!validActions.includes(action_type)) {
      return res.status(400).json({ error: `action_type must be one of: ${validActions.join(', ')}` });
    }
    if (!validTargets.includes(target_type)) {
      return res.status(400).json({ error: `target_type must be one of: ${validTargets.join(', ')}` });
    }

    const rule = RuleModel.create({
      userId: req.user.id,
      name,
      active,
      conditionMetric: condition_metric,
      conditionOperator: condition_operator,
      conditionValue: condition_value,
      actionType: action_type,
      targetType: target_type,
      checkIntervalMinutes: check_interval_minutes
    });

    return res.status(201).json({ message: 'Rule created.', rule });
  } catch (err) {
    console.error('Create rule error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * PUT /api/rules/:id
 * Update a rule
 */
router.put('/:id', authenticate, (req, res) => {
  try {
    const ruleId = parseInt(req.params.id);
    const existing = RuleModel.findById(ruleId, req.user.id);
    if (!existing) {
      return res.status(404).json({ error: 'Rule not found.' });
    }

    const {
      name, active, condition_metric, condition_operator, condition_value,
      action_type, target_type, check_interval_minutes
    } = req.body;

    const rule = RuleModel.update(ruleId, req.user.id, {
      name,
      active,
      conditionMetric: condition_metric,
      conditionOperator: condition_operator,
      conditionValue: condition_value,
      actionType: action_type,
      targetType: target_type,
      checkIntervalMinutes: check_interval_minutes
    });

    return res.json({ message: 'Rule updated.', rule });
  } catch (err) {
    console.error('Update rule error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * DELETE /api/rules/:id
 * Delete a rule
 */
router.delete('/:id', authenticate, (req, res) => {
  try {
    const ruleId = parseInt(req.params.id);
    const existing = RuleModel.findById(ruleId, req.user.id);
    if (!existing) {
      return res.status(404).json({ error: 'Rule not found.' });
    }

    RuleModel.delete(ruleId, req.user.id);
    return res.json({ message: 'Rule deleted.' });
  } catch (err) {
    console.error('Delete rule error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * POST /api/rules/:id/execute
 * Manually execute a rule
 */
router.post('/:id/execute', authenticate, (req, res) => {
  try {
    const ruleId = parseInt(req.params.id);
    const existing = RuleModel.findById(ruleId, req.user.id);
    if (!existing) {
      return res.status(404).json({ error: 'Rule not found.' });
    }

    const result = executeRule(ruleId, req.user.id);
    return res.json(result);
  } catch (err) {
    console.error('Execute rule error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

module.exports = router;
