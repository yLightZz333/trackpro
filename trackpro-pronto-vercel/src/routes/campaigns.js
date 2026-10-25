const express = require('express');
const { authenticate } = require('../middleware/auth');
const { CampaignModel, AdSetModel, AdModel, AdSpendModel } = require('../models');
const { getCampaignPerformance } = require('../services/analytics');

const router = express.Router();

// ==================== CAMPAIGNS ====================

/**
 * GET /api/campaigns
 * List all campaigns for the authenticated user
 */
router.get('/', authenticate, (req, res) => {
  try {
    const campaigns = CampaignModel.findByUserId(req.user.id);
    return res.json({ campaigns });
  } catch (err) {
    console.error('List campaigns error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * GET /api/campaigns/performance
 * Get campaign performance with attribution data
 */
router.get('/performance', authenticate, (req, res) => {
  try {
    const { start_date, end_date } = req.query;
    const performance = getCampaignPerformance(req.user.id, start_date, end_date);
    return res.json({ campaigns: performance });
  } catch (err) {
    console.error('Campaign performance error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * GET /api/campaigns/:id
 * Get a single campaign with its ad sets and ads
 */
router.get('/:id', authenticate, (req, res) => {
  try {
    const campaign = CampaignModel.findById(parseInt(req.params.id), req.user.id);
    if (!campaign) {
      return res.status(404).json({ error: 'Campaign not found.' });
    }

    const adSets = AdSetModel.findByCampaignId(campaign.id);
    const adSetsWithAds = adSets.map(adSet => ({
      ...adSet,
      ads: AdModel.findByAdSetId(adSet.id)
    }));

    return res.json({
      campaign,
      ad_sets: adSetsWithAds
    });
  } catch (err) {
    console.error('Get campaign error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * POST /api/campaigns
 * Create a new campaign
 */
router.post('/', authenticate, (req, res) => {
  try {
    const { name, platform, ad_account_id, campaign_external_id, status, daily_budget_in_cents } = req.body;

    if (!name) {
      return res.status(400).json({ error: 'Campaign name is required.' });
    }

    const validPlatforms = ['meta', 'google', 'tiktok', 'kwai', 'taboola'];
    if (platform && !validPlatforms.includes(platform)) {
      return res.status(400).json({ error: `Platform must be one of: ${validPlatforms.join(', ')}` });
    }

    const campaign = CampaignModel.create({
      userId: req.user.id,
      name,
      platform,
      adAccountId: ad_account_id,
      campaignExternalId: campaign_external_id,
      status,
      dailyBudgetInCents: daily_budget_in_cents
    });

    return res.status(201).json({ message: 'Campaign created.', campaign });
  } catch (err) {
    console.error('Create campaign error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * PUT /api/campaigns/:id
 * Update a campaign
 */
router.put('/:id', authenticate, (req, res) => {
  try {
    const campaignId = parseInt(req.params.id);
    const existing = CampaignModel.findById(campaignId, req.user.id);
    if (!existing) {
      return res.status(404).json({ error: 'Campaign not found.' });
    }

    const { name, platform, ad_account_id, campaign_external_id, status, daily_budget_in_cents } = req.body;

    const campaign = CampaignModel.update(campaignId, req.user.id, {
      name,
      platform,
      adAccountId: ad_account_id,
      campaignExternalId: campaign_external_id,
      status,
      dailyBudgetInCents: daily_budget_in_cents
    });

    return res.json({ message: 'Campaign updated.', campaign });
  } catch (err) {
    console.error('Update campaign error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * DELETE /api/campaigns/:id
 * Delete a campaign and its ad sets/ads (cascade)
 */
router.delete('/:id', authenticate, (req, res) => {
  try {
    const campaignId = parseInt(req.params.id);
    const existing = CampaignModel.findById(campaignId, req.user.id);
    if (!existing) {
      return res.status(404).json({ error: 'Campaign not found.' });
    }

    CampaignModel.delete(campaignId, req.user.id);
    return res.json({ message: 'Campaign deleted.' });
  } catch (err) {
    console.error('Delete campaign error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * POST /api/campaigns/:id/spend
 * Register ad spend for a campaign
 */
router.post('/:id/spend', authenticate, (req, res) => {
  try {
    const campaignId = parseInt(req.params.id);
    const campaign = CampaignModel.findById(campaignId, req.user.id);
    if (!campaign) {
      return res.status(404).json({ error: 'Campaign not found.' });
    }

    const { date, spent_in_cents, impressions, clicks, ad_set_id, ad_id } = req.body;

    if (!date || spent_in_cents === undefined) {
      return res.status(400).json({ error: 'Date and spent_in_cents are required.' });
    }

    const spend = AdSpendModel.create({
      campaignId,
      adSetId: ad_set_id || null,
      adId: ad_id || null,
      date,
      spentInCents: spent_in_cents,
      impressions: impressions || 0,
      clicks: clicks || 0
    });

    // Update campaign total spent
    CampaignModel.updateSpent(campaignId, spent_in_cents);

    return res.status(201).json({ message: 'Ad spend recorded.', spend });
  } catch (err) {
    console.error('Record spend error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

// ==================== AD SETS ====================

/**
 * GET /api/campaigns/:campaignId/ad-sets
 * List ad sets for a campaign
 */
router.get('/:campaignId/ad-sets', authenticate, (req, res) => {
  try {
    const campaignId = parseInt(req.params.campaignId);
    const campaign = CampaignModel.findById(campaignId, req.user.id);
    if (!campaign) {
      return res.status(404).json({ error: 'Campaign not found.' });
    }

    const adSets = AdSetModel.findByCampaignId(campaignId);
    return res.json({ ad_sets: adSets });
  } catch (err) {
    console.error('List ad sets error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * POST /api/campaigns/:campaignId/ad-sets
 * Create an ad set
 */
router.post('/:campaignId/ad-sets', authenticate, (req, res) => {
  try {
    const campaignId = parseInt(req.params.campaignId);
    const campaign = CampaignModel.findById(campaignId, req.user.id);
    if (!campaign) {
      return res.status(404).json({ error: 'Campaign not found.' });
    }

    const { name, external_id, status } = req.body;
    if (!name) {
      return res.status(400).json({ error: 'Ad set name is required.' });
    }

    const adSet = AdSetModel.create({
      campaignId,
      name,
      externalId: external_id,
      status
    });

    return res.status(201).json({ message: 'Ad set created.', ad_set: adSet });
  } catch (err) {
    console.error('Create ad set error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * PUT /api/campaigns/:campaignId/ad-sets/:adSetId
 * Update an ad set
 */
router.put('/:campaignId/ad-sets/:adSetId', authenticate, (req, res) => {
  try {
    const adSetId = parseInt(req.params.adSetId);
    const existing = AdSetModel.findById(adSetId);
    if (!existing) {
      return res.status(404).json({ error: 'Ad set not found.' });
    }

    const { name, external_id, status } = req.body;
    const adSet = AdSetModel.update(adSetId, { name, externalId: external_id, status });

    return res.json({ message: 'Ad set updated.', ad_set: adSet });
  } catch (err) {
    console.error('Update ad set error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * DELETE /api/campaigns/:campaignId/ad-sets/:adSetId
 * Delete an ad set
 */
router.delete('/:campaignId/ad-sets/:adSetId', authenticate, (req, res) => {
  try {
    const adSetId = parseInt(req.params.adSetId);
    const existing = AdSetModel.findById(adSetId);
    if (!existing) {
      return res.status(404).json({ error: 'Ad set not found.' });
    }

    AdSetModel.delete(adSetId);
    return res.json({ message: 'Ad set deleted.' });
  } catch (err) {
    console.error('Delete ad set error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

// ==================== ADS ====================

/**
 * GET /api/campaigns/:campaignId/ad-sets/:adSetId/ads
 * List ads for an ad set
 */
router.get('/:campaignId/ad-sets/:adSetId/ads', authenticate, (req, res) => {
  try {
    const adSetId = parseInt(req.params.adSetId);
    const existing = AdSetModel.findById(adSetId);
    if (!existing) {
      return res.status(404).json({ error: 'Ad set not found.' });
    }

    const ads = AdModel.findByAdSetId(adSetId);
    return res.json({ ads });
  } catch (err) {
    console.error('List ads error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * POST /api/campaigns/:campaignId/ad-sets/:adSetId/ads
 * Create an ad
 */
router.post('/:campaignId/ad-sets/:adSetId/ads', authenticate, (req, res) => {
  try {
    const adSetId = parseInt(req.params.adSetId);
    const existing = AdSetModel.findById(adSetId);
    if (!existing) {
      return res.status(404).json({ error: 'Ad set not found.' });
    }

    const { name, external_id, creative_url, status } = req.body;
    if (!name) {
      return res.status(400).json({ error: 'Ad name is required.' });
    }

    const ad = AdModel.create({
      adSetId,
      name,
      externalId: external_id,
      creativeUrl: creative_url,
      status
    });

    return res.status(201).json({ message: 'Ad created.', ad });
  } catch (err) {
    console.error('Create ad error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * PUT /api/campaigns/:campaignId/ad-sets/:adSetId/ads/:adId
 * Update an ad
 */
router.put('/:campaignId/ad-sets/:adSetId/ads/:adId', authenticate, (req, res) => {
  try {
    const adId = parseInt(req.params.adId);
    const existing = AdModel.findById(adId);
    if (!existing) {
      return res.status(404).json({ error: 'Ad not found.' });
    }

    const { name, external_id, creative_url, status } = req.body;
    const ad = AdModel.update(adId, { name, externalId: external_id, creativeUrl: creative_url, status });

    return res.json({ message: 'Ad updated.', ad });
  } catch (err) {
    console.error('Update ad error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

/**
 * DELETE /api/campaigns/:campaignId/ad-sets/:adSetId/ads/:adId
 * Delete an ad
 */
router.delete('/:campaignId/ad-sets/:adSetId/ads/:adId', authenticate, (req, res) => {
  try {
    const adId = parseInt(req.params.adId);
    const existing = AdModel.findById(adId);
    if (!existing) {
      return res.status(404).json({ error: 'Ad not found.' });
    }

    AdModel.delete(adId);
    return res.json({ message: 'Ad deleted.' });
  } catch (err) {
    console.error('Delete ad error:', err);
    return res.status(500).json({ error: 'Internal server error.' });
  }
});

module.exports = router;
