const express = require('express');
const cors = require('cors');
const crypto = require('crypto');
const https = require('https');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(cors({ origin: true, credentials: true }));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Estado de Produção Limpo (Sem saldo falso, sem vendas falsas)
const memoryStore = {
  metaSettings: {
    pixel_id: process.env.META_PIXEL_ID || '',
    access_token: process.env.META_ACCESS_TOKEN || '',
    test_event_code: process.env.META_TEST_EVENT_CODE || '',
    active: 1
  },
  orders: [],
  campaigns: [],
  capiLogs: []
};

// ==================== DISPARO META ADS CAPI ====================
function sendMetaCapi(orderData) {
  return new Promise((resolve) => {
    const meta = memoryStore.metaSettings;
    if (!meta || !meta.pixel_id || !meta.access_token) {
      return resolve({ status: 'skipped', message: 'Meta CAPI não configurado. Adicione seu Pixel ID e Token CAPI no painel.' });
    }

    const sha256 = (val) => {
      if (!val) return null;
      return crypto.createHash('sha256').update(String(val).trim().toLowerCase()).digest('hex');
    };

    const userData = {};
    if (orderData.customer_email) userData.em = [sha256(orderData.customer_email)];
    if (orderData.customer_phone) {
      let ph = String(orderData.customer_phone).replace(/\D/g, '');
      if (ph && !ph.startsWith('55') && (ph.length === 10 || ph.length === 11)) ph = '55' + ph;
      userData.ph = [sha256(ph)];
    }
    if (orderData.customer_name) {
      const parts = orderData.customer_name.trim().split(' ');
      userData.fn = [sha256(parts[0])];
      if (parts.length > 1) userData.ln = [sha256(parts.slice(1).join(' '))];
    }
    if (orderData.customer_ip) userData.client_ip_address = orderData.customer_ip;
    if (orderData.fbp) userData.fbp = orderData.fbp;
    if (orderData.fbc) userData.fbc = orderData.fbc;

    const eventPayload = {
      event_name: 'Purchase',
      event_time: Math.floor(Date.now() / 1000),
      event_id: String(orderData.order_id),
      action_source: 'website',
      user_data: userData,
      custom_data: {
        currency: 'BRL',
        value: Number(orderData.price_cents || 0) / 100.0,
        content_name: orderData.product_name || 'Produto',
        content_type: 'product'
      }
    };

    const payload = { data: [eventPayload] };
    if (meta.test_event_code) payload.test_event_code = meta.test_event_code;

    const postData = JSON.stringify(payload);
    const options = {
      hostname: 'graph.facebook.com',
      port: 443,
      path: `/v19.0/${meta.pixel_id}/events?access_token=${meta.access_token}`,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      }
    };

    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', (d) => { body += d; });
      res.on('end', () => {
        const log = {
          id: memoryStore.capiLogs.length + 1,
          order_id: String(orderData.order_id),
          event_name: 'Purchase',
          pixel_id: meta.pixel_id,
          status: res.statusCode === 200 ? 'success' : 'error',
          response_code: res.statusCode,
          response_body: body,
          created_at: new Date().toISOString()
        };
        memoryStore.capiLogs.unshift(log);
        try {
          resolve({ status: log.status, code: res.statusCode, response: JSON.parse(body) });
        } catch {
          resolve({ status: log.status, code: res.statusCode, response: body });
        }
      });
    });

    req.on('error', (e) => {
      resolve({ status: 'error', code: 500, response: e.message });
    });

    req.write(postData);
    req.end();
  });
}

// ==================== PARSER DE WEBHOOKS ====================
function parseWebhook(headers, body) {
  let platform = 'Universal';
  let order_id = body.orderId || body.order_id || body.id || `ORD-${Date.now().toString(36).toUpperCase()}`;
  let status = 'paid';
  let customer_name = 'Comprador';
  let customer_email = '';
  let customer_phone = '';
  let price_cents = 0;
  let tracking = {};
  let fbc = null;
  let fbp = null;

  // Kiwify
  if (body.order_status || body.TrackingParameters || body.sale_type) {
    platform = 'Kiwify';
    order_id = body.order_id || body.order_ref || order_id;
    const st = String(body.order_status || '').toLowerCase();
    status = st.includes('paid') || st.includes('approved') ? 'paid' : (st.includes('refund') ? 'refunded' : 'waiting_payment');
    customer_name = body.Customer?.full_name || 'Comprador Kiwify';
    customer_email = body.Customer?.email || '';
    customer_phone = body.Customer?.mobile || '';
    price_cents = parseInt(body.Commissions?.charge_amount || body.Commissions?.product_base_price || 0, 10);
    const tp = body.TrackingParameters || {};
    tracking = {
      utm_source: tp.utm_source,
      utm_medium: tp.utm_medium,
      utm_campaign: tp.utm_campaign,
      utm_content: tp.utm_content,
      src: tp.src,
      sck: tp.sck
    };
  }
  // Hotmart
  else if (headers['x-hotmart-hottok'] || body.hottok || body.data?.purchase) {
    platform = 'Hotmart';
    const p = body.data?.purchase || {};
    const b = body.data?.buyer || {};
    order_id = p.transaction || order_id;
    const st = String(p.status || '').toUpperCase();
    status = st === 'APPROVED' || st === 'COMPLETE' ? 'paid' : (st === 'REFUNDED' ? 'refunded' : 'waiting_payment');
    customer_name = b.name || 'Comprador Hotmart';
    customer_email = b.email || '';
    price_cents = Math.round(Number(p.price?.value || 0) * 100);
    const tr = p.tracking || {};
    tracking = {
      utm_source: tr.source !== 'HOTMART' ? tr.source : 'hotmart',
      utm_campaign: tr.external_code || 'campanha_hotmart',
      utm_content: tr.source_sck,
      src: tr.external_code,
      sck: tr.source_sck
    };
  }
  // Greenn
  else if (headers['x-webhook-token'] || body.event?.startsWith('sale') || body.data?.transaction) {
    platform = 'Greenn';
    const tr = body.data?.transaction || {};
    const cu = body.data?.customer || {};
    order_id = tr.id || order_id;
    const ev = String(body.event || tr.status || '').toLowerCase();
    status = ev.includes('paid') ? 'paid' : (ev.includes('refund') ? 'refunded' : 'waiting_payment');
    customer_name = cu.name || 'Comprador Greenn';
    customer_email = cu.email || '';
    customer_phone = cu.phone || '';
    price_cents = parseInt(tr.amount || 0, 10);
    const tk = body.data?.tracking || {};
    tracking = { ...tk };
  }
  // Cakto
  else if (headers['x-cakto-signature'] || body.event?.startsWith('purchase_') || body.data?.offer_type) {
    platform = 'Cakto';
    const dt = body.data || {};
    order_id = dt.id || order_id;
    const ev = String(body.event || dt.status || '').toLowerCase();
    status = ev.includes('approved') || ev.includes('paid') ? 'paid' : 'waiting_payment';
    customer_name = dt.customer?.name || 'Comprador Cakto';
    customer_email = dt.customer?.email || '';
    price_cents = Math.round(Number(dt.amount || 0) * 100);
    tracking = {
      utm_source: dt.utm_source,
      utm_medium: dt.utm_medium,
      utm_campaign: dt.utm_campaign,
      utm_content: dt.utm_content,
      src: dt.src,
      sck: dt.sck
    };
  }
  // Wiapy
  else if (body.payment && (body.customer || body.tracking)) {
    platform = 'Wiapy';
    order_id = body.payment.id || order_id;
    const st = String(body.payment.status || '').toLowerCase();
    status = st.includes('approved') || st.includes('paid') ? 'paid' : 'waiting_payment';
    customer_name = body.customer?.name || 'Comprador Wiapy';
    customer_email = body.customer?.email || '';
    price_cents = parseInt(body.payment.amount || 0, 10);
    const tk = body.tracking || {};
    tracking = { ...tk };
    fbc = tk.fbc;
    fbp = tk.fbp;
  }
  // Universal
  else {
    customer_name = body.customer?.name || 'Comprador';
    customer_email = body.customer?.email || '';
    price_cents = body.priceInCents || Math.round(Number(body.value || 0) * 100);
    const tp = body.trackingParameters || {};
    tracking = { ...tp };
    fbc = tp.fbc;
    fbp = tp.fbp;
  }

  return {
    platform,
    order_id: String(order_id),
    status,
    customer_name,
    customer_email,
    customer_phone,
    price_cents,
    tracking,
    fbc,
    fbp
  };
}

// ==================== ROTAS DE API ====================
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', app: 'TrackPro Engine', version: '2.0.0', capi: true });
});

app.get('/api/dashboard/overview', (req, res) => {
  const paid = memoryStore.orders.filter(o => o.status === 'paid');
  const totRev = paid.reduce((acc, o) => acc + (o.amount || 0), 0);
  const totSpent = memoryStore.campaigns.reduce((acc, c) => acc + (c.spent || 0), 0);
  const roas = totSpent > 0 ? (totRev / totSpent).toFixed(2) : 0;
  const cpa = paid.length > 0 ? (totSpent / paid.length).toFixed(2) : 0;

  res.json({
    kpis: {
      faturamento: totRev,
      gastoAds: totSpent,
      roas: Number(roas),
      cpa: Number(cpa),
      vendasHoje: paid.length
    },
    recentOrders: memoryStore.orders.slice(0, 15)
  });
});

app.get('/api/orders', (req, res) => {
  res.json({ orders: memoryStore.orders });
});

app.get('/api/campaigns', (req, res) => {
  res.json({ campaigns: memoryStore.campaigns });
});

app.get('/api/meta/settings', (req, res) => {
  res.json(memoryStore.metaSettings);
});

app.post('/api/meta/settings', (req, res) => {
  const { pixel_id, access_token, test_event_code } = req.body;
  if (pixel_id !== undefined) memoryStore.metaSettings.pixel_id = String(pixel_id).trim();
  if (access_token !== undefined) memoryStore.metaSettings.access_token = String(access_token).trim();
  if (test_event_code !== undefined) memoryStore.metaSettings.test_event_code = String(test_event_code).trim();
  res.json({ success: true, message: 'Configurações de Meta CAPI salvas!' });
});

app.get('/api/meta/logs', (req, res) => {
  res.json({ logs: memoryStore.capiLogs });
});

app.post('/api/meta/test', async (req, res) => {
  const testOrder = {
    order_id: `TEST-${Date.now().toString(36).toUpperCase()}`,
    customer_name: 'Cliente Teste Meta',
    customer_email: 'teste@exemplo.com',
    customer_phone: '11999998888',
    price_cents: 19700,
    product_name: 'Teste Conversions API'
  };
  const result = await sendMetaCapi(testOrder);
  res.json(result);
});

// Tracking Pixel JS com Injeção Automática de UTMs para Kiwify, Hotmart, Greenn, Cakto, Wiapy
app.get(['/tracking/pixel.js', '/tracking/pixel'], (req, res) => {
  const token = req.query.token || '';
  const script = `(function(){
  'use strict';
  var TOKEN = '${token}';
  var API = window.location.origin;

  function getQueryParam(name) {
    var search = window.location.search.substring(1);
    var vars = search.split('&');
    for (var i = 0; i < vars.length; i++) {
      var pair = vars[i].split('=');
      if (decodeURIComponent(pair[0]) === name) return decodeURIComponent(pair[1] || '');
    }
    return null;
  }

  var currentUtms = {
    utm_source: getQueryParam('utm_source'),
    utm_medium: getQueryParam('utm_medium'),
    utm_campaign: getQueryParam('utm_campaign'),
    utm_content: getQueryParam('utm_content'),
    utm_term: getQueryParam('utm_term'),
    src: getQueryParam('src'),
    sck: getQueryParam('sck')
  };

  var fbclid = getQueryParam('fbclid');

  function getCookie(n) {
    var v = document.cookie.match('(^|;) ?' + n + '=([^;]*)(;|$)');
    return v ? decodeURIComponent(v[2]) : null;
  }
  function setCookie(n, v, days) {
    var d = new Date();
    d.setTime(d.getTime() + (days * 86400000));
    document.cookie = n + '=' + encodeURIComponent(v) + '; path=/; expires=' + d.toUTCString();
  }

  var fbp = getCookie('_fbp');
  if (!fbp) {
    fbp = 'fb.1.' + (+new Date()) + '.' + Math.floor(Math.random() * 1000000000);
    setCookie('_fbp', fbp, 90);
  }

  var fbc = getCookie('_fbc');
  if (fbclid) {
    fbc = 'fb.1.' + (+new Date()) + '.' + fbclid;
    setCookie('_fbc', fbc, 90);
  }

  var hasUtm = false;
  for (var k in currentUtms) {
    if (currentUtms[k]) { hasUtm = true; break; }
  }

  if (hasUtm) {
    currentUtms.fbp = fbp;
    if (fbc) currentUtms.fbc = fbc;
    try {
      localStorage.setItem('_trackpro_utms', JSON.stringify(currentUtms));
      setCookie('_trackpro_utms', JSON.stringify(currentUtms), 30);
    } catch(e){}
  }

  var stored = {};
  try {
    stored = JSON.parse(localStorage.getItem('_trackpro_utms') || '{}');
  } catch(e){}
  if (!stored.fbp) stored.fbp = fbp;
  if (fbc && !stored.fbc) stored.fbc = fbc;

  fetch(API + '/api/tracking/event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-api-token': TOKEN },
    body: JSON.stringify({
      event_type: 'pageview',
      utm_source: stored.utm_source,
      utm_medium: stored.utm_medium,
      utm_campaign: stored.utm_campaign,
      utm_content: stored.utm_content,
      utm_term: stored.utm_term,
      src: stored.src,
      sck: stored.sck,
      fbc: stored.fbc,
      fbp: stored.fbp,
      page_url: window.location.href,
      referrer: document.referrer
    })
  }).catch(function(){});

  function decorateCheckoutLinks() {
    var links = document.querySelectorAll('a[href]');
    var checkouts = ['kiwify.com.br', 'hotmart.com', 'greenn.com.br', 'cakto.com.br', 'wiapy.com'];
    
    links.forEach(function(link) {
      var href = link.getAttribute('href');
      if (!href) return;
      var isCheckout = checkouts.some(function(domain) { return href.indexOf(domain) !== -1; });
      if (isCheckout) {
        var separator = href.indexOf('?') !== -1 ? '&' : '?';
        var params = [];
        if (stored.utm_source) params.push('utm_source=' + encodeURIComponent(stored.utm_source));
        if (stored.utm_medium) params.push('utm_medium=' + encodeURIComponent(stored.utm_medium));
        if (stored.utm_campaign) params.push('utm_campaign=' + encodeURIComponent(stored.utm_campaign));
        if (stored.utm_content) params.push('utm_content=' + encodeURIComponent(stored.utm_content));
        if (stored.utm_term) params.push('utm_term=' + encodeURIComponent(stored.utm_term));
        if (stored.src) params.push('src=' + encodeURIComponent(stored.src));
        if (stored.sck) params.push('sck=' + encodeURIComponent(stored.sck));
        if (stored.fbc) params.push('fbc=' + encodeURIComponent(stored.fbc));
        if (stored.fbp) params.push('fbp=' + encodeURIComponent(stored.fbp));

        if (params.length > 0) {
          link.setAttribute('href', href + separator + params.join('&'));
        }
      }
    });
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    decorateCheckoutLinks();
  } else {
    document.addEventListener('DOMContentLoaded', decorateCheckoutLinks);
  }

  window.TrackPro = {
    getUtms: function() { return stored; },
    getFbp: function() { return fbp; },
    getFbc: function() { return fbc; }
  };
})();`;
  res.setHeader('Content-Type', 'application/javascript; charset=utf-8');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.send(script);
});

// Evento de Pageview / Tracking
app.post('/api/tracking/event', (req, res) => {
  res.status(200).json({ success: true });
});

// Rotas de Webhook para as plataformas
const webhookHandler = async (req, res) => {
  const parsed = parseWebhook(req.headers, req.body);
  const path = req.path.toLowerCase();
  if (path.includes('kiwify')) parsed.platform = 'Kiwify';
  else if (path.includes('hotmart')) parsed.platform = 'Hotmart';
  else if (path.includes('greenn')) parsed.platform = 'Greenn';
  else if (path.includes('cakto')) parsed.platform = 'Cakto';
  else if (path.includes('wiapy')) parsed.platform = 'Wiapy';

  const newOrder = {
    id: parsed.order_id,
    platform: parsed.platform,
    customer: parsed.customer_name,
    email: parsed.customer_email,
    amount: parsed.price_cents / 100.0,
    status: parsed.status,
    utm_source: parsed.tracking.utm_source || 'direto',
    utm_campaign: parsed.tracking.utm_campaign || 'campanha_padrao',
    utm_content: parsed.tracking.utm_content || '-',
    date: new Date().toISOString()
  };

  memoryStore.orders.unshift(newOrder);

  let capiResult = null;
  if (parsed.status === 'paid') {
    capiResult = await sendMetaCapi(parsed);
  }

  res.status(200).json({
    success: true,
    message: `Venda ${parsed.order_id} da ${parsed.platform} recebida e atribuída!`,
    platform: parsed.platform,
    orderId: parsed.order_id,
    metaCapi: capiResult
  });
};

app.post('/api/webhook/kiwify', webhookHandler);
app.post('/api/webhook/hotmart', webhookHandler);
app.post('/api/webhook/greenn', webhookHandler);
app.post('/api/webhook/cakto', webhookHandler);
app.post('/api/webhook/wiapy', webhookHandler);
app.post('/api/webhook/orders', webhookHandler);

// Fallback para servir o Frontend HTML em qualquer rota (quando roteado pelo Vercel)
app.get('*', (req, res) => {
  const candidates = [
    path.join(__dirname, '..', 'public', 'index.html'),
    path.join(__dirname, '..', 'index.html'),
    path.join(process.cwd(), 'public', 'index.html'),
    path.join(process.cwd(), 'index.html')
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) {
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      return res.sendFile(p);
    }
  }
  res.status(404).send('TrackPro Dashboard HTML not found');
});

module.exports = app;
