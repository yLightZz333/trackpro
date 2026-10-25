const { verifyToken } = require('../utils/jwt');
const { getDb } = require('../config/database');

/**
 * JWT authentication middleware
 * Verifies the Bearer token from the Authorization header
 */
function authenticate(req, res, next) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Authentication required. Provide a Bearer token.' });
  }

  const token = authHeader.split(' ')[1];
  const decoded = verifyToken(token);

  if (!decoded) {
    return res.status(401).json({ error: 'Invalid or expired token.' });
  }

  const db = getDb();
  const user = db.prepare('SELECT id, name, email, company, created_at FROM users WHERE id = ?').get(decoded.userId);

  if (!user) {
    return res.status(401).json({ error: 'User not found.' });
  }

  req.user = user;
  next();
}

/**
 * API token authentication middleware
 * Verifies the x-api-token header against api_credentials table
 */
function authenticateApiToken(req, res, next) {
  const apiToken = req.headers['x-api-token'];
  if (!apiToken) {
    return res.status(401).json({ error: 'API token required. Provide x-api-token header.' });
  }

  const db = getDb();
  const credential = db.prepare('SELECT ac.id, ac.user_id, ac.name, ac.active FROM api_credentials ac WHERE ac.token = ?').get(apiToken);

  if (!credential) {
    return res.status(401).json({ error: 'Invalid API token.' });
  }

  if (!credential.active) {
    return res.status(403).json({ error: 'API token is deactivated.' });
  }

  const user = db.prepare('SELECT id, name, email, company FROM users WHERE id = ?').get(credential.user_id);
  if (!user) {
    return res.status(401).json({ error: 'User associated with this token not found.' });
  }

  req.user = user;
  req.apiCredential = credential;
  next();
}

module.exports = { authenticate, authenticateApiToken };
