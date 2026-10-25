const express = require('express');
const { v4: uuidv4 } = require('uuid');
const { authenticate } = require('../middleware/auth');
const { ApiCredentialModel } = require('../models');
const { getTrackingScript } = require('../services/tracking');

const router = express.Router();

/**
 * GET /api/integrations
 * List all API credentials for the authenticated user
 */
router.get('/', authenticate, (req, res) => {
  try {
    const credentials = ApiCredentialModel.findByUserId(req.user.id);
    return res.json({ credentials });
  } catch (err) {
    console.error('List integrations error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * POST /api/integrations
 * Create a new API credential (generates UUID token)
 */
router.post('/', authenticate, (req, res) => {
  try {
    const { name } = req.body;

    if (!name) {
      return res.status(400).json({ error: 'Credential name is required.' });
    }

    const token = uuidv4();
    const credential = ApiCredentialModel.create({
      userId: req.user.id,
      name,
      token
    });

    return res.status(201).json({
      message: 'API credential created.',
      credential
    });
  } catch (err) {
    console.error('Create integration error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * PUT /api/integrations/:id
 * Update an API credential (name, active status)
 */
router.put('/:id', authenticate, (req, res) => {
  try {
    const credId = parseInt(req.params.id);
    const existing = ApiCredentialModel.findById(credId, req.user.id);
    if (!existing) {
      return res.status(404).json({ error: 'Credential not found.' });
    }

    const { name, active } = req.body;
    const credential = ApiCredentialModel.update(credId, req.user.id, { name, active });

    return res.json({ message: 'Credential updated.', credential });
  } catch (err) {
    console.error('Update integration error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * DELETE /api/integrations/:id
 * Delete an API credential
 */
router.delete('/:id', authenticate, (req, res) => {
  try {
    const credId = parseInt(req.params.id);
    const existing = ApiCredentialModel.findById(credId, req.user.id);
    if (!existing) {
      return res.status(404).json({ error: 'Credential not found.' });
    }

    ApiCredentialModel.delete(credId, req.user.id);
    return res.json({ message: 'Credential deleted.' });
  } catch (err) {
    console.error('Delete integration error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * GET /api/integrations/tracking-script
 * Return the JS tracking pixel code for the user's first active API token
 */
router.get('/tracking-script', authenticate, (req, res) => {
  try {
    const credentials = ApiCredentialModel.findByUserId(req.user.id);
    const activeCred = credentials.find(c => c.active);

    if (!activeCred) {
      return res.status(404).json({ error: 'No active API credential found. Create one first.' });
    }

    const protocol = req.protocol;
    const host = req.get('host');
    const baseUrl = `${protocol}://${host}`;

    const script = getTrackingScript(baseUrl, activeCred.token);

    return res.json({
      token: activeCred.token,
      script,
      embed_code: `<script src="${baseUrl}/tracking/pixel.js?token=${activeCred.token}"></script>`,
      manual_embed: `<script>\n${script}\n</script>`
    });
  } catch (err) {
    console.error('Tracking script error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

module.exports = router;
