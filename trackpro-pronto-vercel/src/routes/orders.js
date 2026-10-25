const express = require('express');
const { authenticate, authenticateApiToken } = require('../middleware/auth');
const { OrderModel, TrackingEventModel, ProductModel } = require('../models');
const { recordPurchase, attributeOrder } = require('../services/tracking');
const { paginate, parseDateRange } = require('../utils/helpers');

const router = express.Router();

/**
 * POST /api/webhook/orders
 * Receive orders from external checkouts (Hotmart, Eduzz, Monetizze, etc.)
 * Authenticated via x-api-token header
 *
 * Accepts UTMify-compatible JSON format
 */
router.post('/webhook/orders', authenticateApiToken, (req, res) => {
  try {
    const userId = req.user.id;
    const body = req.body;

    // Validate required fields
    if (!body.order_id && !body.transaction_id) {
      return res.status(400).json({ error: 'order_id or transaction_id is required.' });
    }

    const externalId = body.order_id || body.transaction_id;

    // Check for duplicate
    const existingOrder = OrderModel.findByExternalId(externalId, userId);
    if (existingOrder) {
      // Update status if changed
      if (body.status && body.status !== existingOrder.status) {
        const updated = OrderModel.updateStatus(existingOrder.id, userId, body.status);
        return res.json({ message: 'Order status updated.', order: updated });
      }
      return res.json({ message: 'Order already exists.', order: existingOrder });
    }

    // Find or match product
    let productId = null;
    if (body.product_id) {
      const product = ProductModel.findById(parseInt(body.product_id), userId);
      if (product) productId = product.id;
    } else if (body.product_name) {
      const { getDb } = require('../config/database');
      const db = getDb();
      const product = db.prepare('SELECT id FROM products WHERE user_id = ? AND name = ?').get(userId, body.product_name);
      if (product) productId = product.id;
    }

    // Calculate net amount
    const priceInCents = body.price_in_cents || body.value || Math.round((body.price || 0) * 100);
    const gatewayFee = body.gateway_fee_in_cents || Math.round((body.gateway_fee || 0) * 100) || Math.round(priceInCents * 0.05);
    const netAmount = body.net_amount_in_cents || (priceInCents - gatewayFee);

    const order = OrderModel.create({
      userId,
      orderExternalId: externalId,
      productId,
      platform: body.platform || body.source || null,
      paymentMethod: body.payment_method || body.payment_type || null,
      status: body.status || 'waiting_payment',
      customerName: body.customer_name || body.buyer_name || (body.customer && body.customer.name) || null,
      customerEmail: body.customer_email || body.buyer_email || (body.customer && body.customer.email) || null,
      customerPhone: body.customer_phone || body.buyer_phone || (body.customer && body.customer.phone) || null,
      customerDocument: body.customer_document || body.buyer_document || (body.customer && body.customer.document) || null,
      customerIp: body.customer_ip || req.ip || null,
      priceInCents,
      gatewayFeeInCents: gatewayFee,
      netAmountInCents: netAmount,
      currency: body.currency || 'BRL',
      isTest: body.is_test || false
    });

    // If UTM data is provided, create a purchase tracking event
    if (body.utm_source || body.session_id || body.src) {
      recordPurchase({
        userId,
        orderId: order.id,
        sessionId: body.session_id || null,
        utmSource: body.utm_source || null,
        utmMedium: body.utm_medium || null,
        utmCampaign: body.utm_campaign || null,
        utmContent: body.utm_content || null,
        utmTerm: body.utm_term || null,
        src: body.src || null,
        sck: body.sck || null,
        pageUrl: body.page_url || null,
        referrer: body.referrer || null,
        userAgent: req.get('User-Agent'),
        ipAddress: body.customer_ip || req.ip
      });
    }

    return res.status(201).json({ message: 'Order created successfully.', order });
  } catch (err) {
    console.error('Webhook order error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * GET /api/orders
 * List orders with filters
 *
 * Query params:
 *  - status: Filter by status
 *  - product_id: Filter by product
 *  - payment_method: Filter by payment method
 *  - platform: Filter by platform
 *  - start_date: YYYY-MM-DD
 *  - end_date: YYYY-MM-DD
 *  - search: Search by name, email, or order ID
 *  - page: Page number (default 1)
 *  - limit: Results per page (default 20, max 100)
 */
router.get('/', authenticate, (req, res) => {
  try {
    const { status, product_id, payment_method, platform, start_date, end_date, search, page, limit } = req.query;
    const pagination = paginate(page, limit);
    const { startDate, endDate } = parseDateRange(start_date, end_date);

    const result = OrderModel.list(req.user.id, {
      status,
      productId: product_id ? parseInt(product_id) : null,
      paymentMethod: payment_method,
      platform,
      startDate,
      endDate,
      search,
      limit: pagination.limit,
      offset: pagination.offset
    });

    return res.json({
      orders: result.orders,
      pagination: {
        total: result.total,
        page: Math.floor(pagination.offset / pagination.limit) + 1,
        limit: pagination.limit,
        total_pages: Math.ceil(result.total / pagination.limit)
      }
    });
  } catch (err) {
    console.error('List orders error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * GET /api/orders/:id
 * Get order details with tracking info
 */
router.get('/:id', authenticate, (req, res) => {
  try {
    const orderId = parseInt(req.params.id);
    const attribution = attributeOrder(orderId, req.user.id);

    if (!attribution || !attribution.order) {
      return res.status(404).json({ error: 'Order not found.' });
    }

    return res.json(attribution);
  } catch (err) {
    console.error('Get order error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * PATCH /api/orders/:id/status
 * Update order status
 */
router.patch('/:id/status', authenticate, (req, res) => {
  try {
    const orderId = parseInt(req.params.id);
    const { status } = req.body;

    const validStatuses = ['waiting_payment', 'paid', 'refused', 'refunded', 'chargedback'];
    if (!status || !validStatuses.includes(status)) {
      return res.status(400).json({ error: `Status must be one of: ${validStatuses.join(', ')}` });
    }

    const existing = OrderModel.findById(orderId, req.user.id);
    if (!existing) {
      return res.status(404).json({ error: 'Order not found.' });
    }

    const order = OrderModel.updateStatus(orderId, req.user.id, status);
    return res.json({ message: 'Order status updated.', order });
  } catch (err) {
    console.error('Update order status error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

module.exports = router;
