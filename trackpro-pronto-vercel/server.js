require('dotenv').config();
const express = require('express');
const helmet = require('helmet');
const morgan = require('morgan');
const path = require('path');
const corsMiddleware = require('./src/middleware/cors');
const { getDb } = require('./src/config/database');
const { authenticateApiToken } = require('./src/middleware/auth');
const { recordEvent, getTrackingScript } = require('./src/services/tracking');
const { ApiCredentialModel } = require('./src/models');

// Initialize database & seed demo data
getDb();

const app = express();
const PORT = process.env.PORT || 3001;

// Global Middleware
app.use(helmet({
  contentSecurityPolicy: false,
  crossOriginResourcePolicy: false
}));
app.use(corsMiddleware);
app.use(morgan('dev'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Tracking Pixel JS Endpoint (served to client landing pages / checkouts)
app.get('/tracking/pixel.js', (req, res) => {
  const token = req.query.token || '';
  const protocol = req.protocol;
  const host = req.get('host');
  const baseUrl = `${protocol}://${host}`;

  const script = getTrackingScript(baseUrl, token);
  res.setHeader('Content-Type', 'application/javascript; charset=utf-8');
  res.setHeader('Cache-Control', 'public, max-age=3600');
  res.send(script);
});

// Tracking Event Ingestion Endpoint
app.post('/api/tracking/event', authenticateApiToken, (req, res) => {
  try {
    const {
      session_id, event_type, utm_source, utm_medium,
      utm_campaign, utm_content, utm_term, src, sck,
      page_url, referrer, order_id
    } = req.body;

    const ipAddress = req.headers['x-forwarded-for'] || req.socket.remoteAddress || req.ip;
    const userAgent = req.headers['user-agent'] || null;

    const eventId = recordEvent({
      userId: req.user.id,
      orderId: order_id || null,
      sessionId: session_id || null,
      eventType: event_type || 'pageview',
      utmSource: utm_source || null,
      utmMedium: utm_medium || null,
      utmCampaign: utm_campaign || null,
      utmContent: utm_content || null,
      utmTerm: utm_term || null,
      src: src || null,
      sck: sck || null,
      pageUrl: page_url || null,
      referrer: referrer || null,
      userAgent,
      ipAddress
    });

    return res.status(201).json({ success: true, eventId: eventId.id });
  } catch (err) {
    console.error('Track event error:', err);
    return res.status(500).json({ error: 'Failed to record tracking event.' });
  }
});

// API Routes
app.use('/api/auth', require('./src/routes/auth'));
app.use('/api/dashboard', require('./src/routes/dashboard'));
app.use('/api/orders', require('./src/routes/orders'));
app.use('/api', require('./src/routes/orders')); // Mounts /api/webhook/orders
app.use('/api/campaigns', require('./src/routes/campaigns'));
app.use('/api/products', require('./src/routes/products'));
app.use('/api/reports', require('./src/routes/reports'));
app.use('/api/integrations', require('./src/routes/integrations'));
app.use('/api/rules', require('./src/routes/rules'));

// Health check
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    platform: 'TrackPro - UTMify Clone',
    timestamp: new Date().toISOString()
  });
});

// 404 Handler
app.use((req, res) => {
  res.status(404).json({ error: 'Endpoint not found.' });
});

// Error Handler
app.use((err, req, res, next) => {
  console.error('Server error:', err);
  res.status(500).json({ error: 'Internal server error.' });
});

app.listen(PORT, () => {
  console.log(`🚀 TrackPro Server running on http://localhost:${PORT}`);
  console.log(`📡 Tracking Pixel available at http://localhost:${PORT}/tracking/pixel.js`);
});
