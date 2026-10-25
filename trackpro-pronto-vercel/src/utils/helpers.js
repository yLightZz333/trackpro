/**
 * Format cents to currency string
 * @param {number} cents
 * @returns {string}
 */
function formatCurrency(cents) {
  return (cents / 100).toFixed(2);
}

/**
 * Parse a date string or return default range
 * @param {string} startDate
 * @param {string} endDate
 * @returns {{ startDate: string, endDate: string }}
 */
function parseDateRange(startDate, endDate) {
  const now = new Date();
  if (!endDate) {
    endDate = now.toISOString().split('T')[0] + ' 23:59:59';
  } else {
    endDate = endDate + ' 23:59:59';
  }
  if (!startDate) {
    const thirtyDaysAgo = new Date(now);
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    startDate = thirtyDaysAgo.toISOString().split('T')[0] + ' 00:00:00';
  } else {
    startDate = startDate + ' 00:00:00';
  }
  return { startDate, endDate };
}

/**
 * Build WHERE clause fragments from filters
 * @param {object} filters
 * @returns {{ clauses: string[], params: any[] }}
 */
function buildFilterClauses(filters) {
  const clauses = [];
  const params = [];

  if (filters.userId !== undefined) {
    clauses.push('user_id = ?');
    params.push(filters.userId);
  }
  if (filters.status) {
    clauses.push('status = ?');
    params.push(filters.status);
  }
  if (filters.productId) {
    clauses.push('product_id = ?');
    params.push(filters.productId);
  }
  if (filters.platform) {
    clauses.push('platform = ?');
    params.push(filters.platform);
  }
  if (filters.paymentMethod) {
    clauses.push('payment_method = ?');
    params.push(filters.paymentMethod);
  }
  if (filters.startDate) {
    clauses.push('created_at >= ?');
    params.push(filters.startDate);
  }
  if (filters.endDate) {
    clauses.push('created_at <= ?');
    params.push(filters.endDate);
  }

  return { clauses, params };
}

/**
 * Paginate results
 * @param {number} page
 * @param {number} limit
 * @returns {{ offset: number, limit: number }}
 */
function paginate(page, limit) {
  const p = Math.max(1, parseInt(page) || 1);
  const l = Math.min(100, Math.max(1, parseInt(limit) || 20));
  return { offset: (p - 1) * l, limit: l };
}

/**
 * Calculate ROAS (Return On Ad Spend)
 * @param {number} revenue - Revenue in cents
 * @param {number} spent - Spend in cents
 * @returns {number}
 */
function calculateROAS(revenue, spent) {
  if (!spent || spent === 0) return 0;
  return parseFloat((revenue / spent).toFixed(2));
}

/**
 * Calculate ROI (Return On Investment)
 * @param {number} revenue - Revenue in cents
 * @param {number} spent - Spend in cents
 * @returns {number}
 */
function calculateROI(revenue, spent) {
  if (!spent || spent === 0) return 0;
  return parseFloat((((revenue - spent) / spent) * 100).toFixed(2));
}

/**
 * Calculate CPA (Cost Per Acquisition)
 * @param {number} spent - Spend in cents
 * @param {number} conversions - Number of conversions
 * @returns {number}
 */
function calculateCPA(spent, conversions) {
  if (!conversions || conversions === 0) return 0;
  return Math.round(spent / conversions);
}

module.exports = {
  formatCurrency,
  parseDateRange,
  buildFilterClauses,
  paginate,
  calculateROAS,
  calculateROI,
  calculateCPA
};
