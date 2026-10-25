const express = require('express');
const { authenticate } = require('../middleware/auth');
const { ProductModel } = require('../models');

const router = express.Router();

/**
 * GET /api/products
 * List all products for the authenticated user
 */
router.get('/', authenticate, (req, res) => {
  try {
    const products = ProductModel.findByUserId(req.user.id);
    return res.json({ products });
  } catch (err) {
    console.error('List products error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * GET /api/products/:id
 * Get a single product
 */
router.get('/:id', authenticate, (req, res) => {
  try {
    const product = ProductModel.findById(parseInt(req.params.id), req.user.id);
    if (!product) {
      return res.status(404).json({ error: 'Product not found.' });
    }
    return res.json({ product });
  } catch (err) {
    console.error('Get product error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * POST /api/products
 * Create a new product
 */
router.post('/', authenticate, (req, res) => {
  try {
    const { name, platform, cost_in_cents } = req.body;

    if (!name) {
      return res.status(400).json({ error: 'Product name is required.' });
    }

    const product = ProductModel.create({
      userId: req.user.id,
      name,
      platform,
      costInCents: cost_in_cents || 0
    });

    return res.status(201).json({ message: 'Product created.', product });
  } catch (err) {
    console.error('Create product error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * PUT /api/products/:id
 * Update a product
 */
router.put('/:id', authenticate, (req, res) => {
  try {
    const productId = parseInt(req.params.id);
    const existing = ProductModel.findById(productId, req.user.id);
    if (!existing) {
      return res.status(404).json({ error: 'Product not found.' });
    }

    const { name, platform, cost_in_cents, active } = req.body;

    const product = ProductModel.update(productId, req.user.id, {
      name,
      platform,
      costInCents: cost_in_cents,
      active
    });

    return res.json({ message: 'Product updated.', product });
  } catch (err) {
    console.error('Update product error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * DELETE /api/products/:id
 * Delete a product
 */
router.delete('/:id', authenticate, (req, res) => {
  try {
    const productId = parseInt(req.params.id);
    const existing = ProductModel.findById(productId, req.user.id);
    if (!existing) {
      return res.status(404).json({ error: 'Product not found.' });
    }

    ProductModel.delete(productId, req.user.id);
    return res.json({ message: 'Product deleted.' });
  } catch (err) {
    console.error('Delete product error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

module.exports = router;
