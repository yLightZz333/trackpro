const express = require('express');
const { authenticate } = require('../middleware/auth');
const { getDashboardOverview } = require('../services/analytics');

const router = express.Router();

/**
 * GET /api/dashboard/overview
 * Get dashboard KPIs and overview stats
 *
 * Query params:
 *  - start_date: YYYY-MM-DD (default: 30 days ago)
 *  - end_date: YYYY-MM-DD (default: today)
 *  - product_id: Filter by product
 *  - platform: Filter by platform
 */
router.get(['/', '/overview'], authenticate, (req, res) => {
  try {
    const { start_date, end_date, product_id, platform } = req.query;

    const overview = getDashboardOverview(req.user.id, {
      startDate: start_date,
      endDate: end_date,
      productId: product_id ? parseInt(product_id) : null,
      platform: platform || null
    });

    return res.json(overview);
  } catch (err) {
    console.error('Dashboard overview error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

module.exports = router;
