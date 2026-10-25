const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'trackpro-default-secret-change-me';
const JWT_EXPIRY = '7d';

function generateToken(payload) {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: JWT_EXPIRY });
}

function verifyToken(token) {
  try {
    return jwt.verify(token, JWT_SECRET);
  } catch (err) {
    return null;
  }
}

module.exports = { generateToken, verifyToken, JWT_SECRET };
