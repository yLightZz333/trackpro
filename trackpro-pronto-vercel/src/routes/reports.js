const express = require('express');
const { authenticate } = require('../middleware/auth');
const {
  getRevenueBySource,
  getRevenueByCampaign,
  getRevenueByMedium,
  getRevenueByProduct,
  getRevenueByDay,
  getFinancialReport
} = require('../services/analytics');

const router = express.Router();

/**
 * GET /api/reports/by-source
 * Revenue/orders grouped by utm_source
 */
router.get('/by-source', authenticate, (req, res) => {
  try {
    const { start_date, end_date } = req.query;
    const data = getRevenueBySource(req.user.id, start_date, end_date);
    return res.json({ report: 'by_source', data });
  } catch (err) {
    console.error('Report by source error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * GET /api/reports/by-campaign
 * Revenue/orders grouped by utm_campaign
 */
router.get('/by-campaign', authenticate, (req, res) => {
  try {
    const { start_date, end_date } = req.query;
    const data = getRevenueByCampaign(req.user.id, start_date, end_date);
    return res.json({ report: 'by_campaign', data });
  } catch (err) {
    console.error('Report by campaign error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * GET /api/reports/by-medium
 * Revenue/orders grouped by utm_medium
 */
router.get('/by-medium', authenticate, (req, res) => {
  try {
    const { start_date, end_date } = req.query;
    const data = getRevenueByMedium(req.user.id, start_date, end_date);
    return res.json({ report: 'by_medium', data });
  } catch (err) {
    console.error('Report by medium error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * GET /api/reports/by-product
 * Revenue/orders grouped by product
 */
router.get('/by-product', authenticate, (req, res) => {
  try {
    const { start_date, end_date } = req.query;
    const data = getRevenueByProduct(req.user.id, start_date, end_date);
    return res.json({ report: 'by_product', data });
  } catch (err) {
    console.error('Report by product error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * GET /api/reports/by-day
 * Daily revenue/orders over time
 */
router.get('/by-day', authenticate, (req, res) => {
  try {
    const { start_date, end_date } = req.query;
    const data = getRevenueByDay(req.user.id, start_date, end_date);
    return res.json({ report: 'by_day', data });
  } catch (err) {
    console.error('Report by day error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * GET /api/reports/financial
 * Financial report with costs, fees, net profit
 */
router.get('/financial', authenticate, (req, res) => {
  try {
    const { start_date, end_date } = req.query;
    const data = getFinancialReport(req.user.id, start_date, end_date);
    return res.json({ report: 'financial', data });
  } catch (err) {
    console.error('Financial report error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

module.exports = router;
