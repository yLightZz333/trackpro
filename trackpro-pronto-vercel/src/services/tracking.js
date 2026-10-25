const { getDb } = require('../config/database');
const { TrackingEventModel, OrderModel } = require('../models');
const { v4: uuidv4 } = require('uuid');

/**
 * Record a tracking event
 */
function recordEvent(data) {
  return TrackingEventModel.create(data);
}

/**
 * Record a pageview event from the tracking pixel
 */
function recordPageview({ userId, sessionId, utmSource, utmMedium, utmCampaign, utmContent, utmTerm, src, sck, pageUrl, referrer, userAgent, ipAddress }) {
  return TrackingEventModel.create({
    userId,
    sessionId: sessionId || uuidv4(),
    eventType: 'pageview',
    utmSource,
    utmMedium,
    utmCampaign,
    utmContent,
    utmTerm,
    src,
    sck,
    pageUrl,
    referrer,
    userAgent,
    ipAddress
  });
}

/**
 * Record a click event
 */
function recordClick(data) {
  return TrackingEventModel.create({
    ...data,
    eventType: 'click',
    sessionId: data.sessionId || uuidv4()
  });
}

/**
 * Record a purchase event and link to an order
 */
function recordPurchase({ userId, orderId, sessionId, utmSource, utmMedium, utmCampaign, utmContent, utmTerm, src, sck, pageUrl, referrer, userAgent, ipAddress }) {
  return TrackingEventModel.create({
    userId,
    orderId,
    sessionId,
    eventType: 'purchase',
    utmSource,
    utmMedium,
    utmCampaign,
    utmContent,
    utmTerm,
    src,
    sck,
    pageUrl,
    referrer,
    userAgent,
    ipAddress
  });
}

/**
 * Attribute an order to tracking data by session or IP matching
 */
function attributeOrder(orderId, userId) {
  const db = getDb();
  const order = OrderModel.findById(orderId, userId);
  if (!order) return null;

  // Try to find tracking events for this order by session_id in purchase events
  let trackingEvents = TrackingEventModel.findByOrderId(orderId);
  if (trackingEvents.length > 0) {
    return {
      order,
      trackingEvents,
      attribution: extractAttribution(trackingEvents)
    };
  }

  // Try to find by customer IP if no direct link
  if (order.customer_ip) {
    const events = db.prepare(`
      SELECT * FROM tracking_events
      WHERE user_id = ? AND ip_address = ?
      AND created_at <= ? AND created_at >= datetime(?, '-7 days')
      ORDER BY created_at DESC
      LIMIT 20
    `).all(userId, order.customer_ip, order.created_at, order.created_at);

    if (events.length > 0) {
      return {
        order,
        trackingEvents: events,
        attribution: extractAttribution(events)
      };
    }
  }

  return {
    order,
    trackingEvents: [],
    attribution: null
  };
}

/**
 * Extract attribution data from tracking events (last-click model)
 */
function extractAttribution(events) {
  if (!events || events.length === 0) return null;

  // Last-click attribution: use the most recent event with UTM data
  const eventsWithUtm = events.filter(e => e.utm_source || e.utm_medium || e.utm_campaign);
  const lastEvent = eventsWithUtm.length > 0 ? eventsWithUtm[eventsWithUtm.length - 1] : events[events.length - 1];

  return {
    utm_source: lastEvent.utm_source,
    utm_medium: lastEvent.utm_medium,
    utm_campaign: lastEvent.utm_campaign,
    utm_content: lastEvent.utm_content,
    utm_term: lastEvent.utm_term,
    src: lastEvent.src,
    sck: lastEvent.sck,
    first_event_at: events[0].created_at,
    last_event_at: events[events.length - 1].created_at,
    total_events: events.length,
    attribution_model: 'last_click'
  };
}

/**
 * Get the tracking script content for embedding
 */
function getTrackingScript(baseUrl, apiToken) {
  return `
(function() {
  'use strict';

  var TRACKPRO_API = '${baseUrl}';
  var TRACKPRO_TOKEN = '${apiToken}';
  var SESSION_KEY = '_tp_sid';
  var UTM_KEY = '_tp_utm';
  var COOKIE_DAYS = 30;

  // ========== Cookie Helpers ==========
  function setCookie(name, value, days) {
    var expires = '';
    if (days) {
      var date = new Date();
      date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
      expires = '; expires=' + date.toUTCString();
    }
    document.cookie = name + '=' + encodeURIComponent(value) + expires + '; path=/; SameSite=Lax';
  }

  function getCookie(name) {
    var nameEQ = name + '=';
    var ca = document.cookie.split(';');
    for (var i = 0; i < ca.length; i++) {
      var c = ca[i].trim();
      if (c.indexOf(nameEQ) === 0) return decodeURIComponent(c.substring(nameEQ.length));
    }
    return null;
  }

  // ========== UUID Generator ==========
  function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      var r = Math.random() * 16 | 0;
      var v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  // ========== URL Parameter Parser ==========
  function getUrlParams() {
    var params = {};
    var search = window.location.search.substring(1);
    if (!search) return params;
    var pairs = search.split('&');
    for (var i = 0; i < pairs.length; i++) {
      var pair = pairs[i].split('=');
      if (pair.length === 2) {
        params[decodeURIComponent(pair[0])] = decodeURIComponent(pair[1]);
      }
    }
    return params;
  }

  // ========== Session Management ==========
  function getSessionId() {
    var sessionId = getCookie(SESSION_KEY);
    if (!sessionId) {
      sessionId = generateUUID();
      setCookie(SESSION_KEY, sessionId, COOKIE_DAYS);
    }
    return sessionId;
  }

  // ========== UTM Storage ==========
  function storeUtmParams(params) {
    var utmData = {
      utm_source: params.utm_source || null,
      utm_medium: params.utm_medium || null,
      utm_campaign: params.utm_campaign || null,
      utm_content: params.utm_content || null,
      utm_term: params.utm_term || null,
      src: params.src || null,
      sck: params.sck || null
    };

    var hasUtm = Object.keys(utmData).some(function(key) { return utmData[key] !== null; });

    if (hasUtm) {
      setCookie(UTM_KEY, JSON.stringify(utmData), COOKIE_DAYS);
      try {
        localStorage.setItem(UTM_KEY, JSON.stringify(utmData));
      } catch (e) {}
    }

    return utmData;
  }

  function getStoredUtms() {
    var stored = getCookie(UTM_KEY);
    if (stored) {
      try { return JSON.parse(stored); } catch (e) {}
    }
    try {
      var ls = localStorage.getItem(UTM_KEY);
      if (ls) return JSON.parse(ls);
    } catch (e) {}
    return {};
  }

  // ========== API Communication ==========
  function sendEvent(eventType, extraData) {
    var utms = getStoredUtms();
    var payload = {
      session_id: getSessionId(),
      event_type: eventType,
      utm_source: utms.utm_source || null,
      utm_medium: utms.utm_medium || null,
      utm_campaign: utms.utm_campaign || null,
      utm_content: utms.utm_content || null,
      utm_term: utms.utm_term || null,
      src: utms.src || null,
      sck: utms.sck || null,
      page_url: window.location.href,
      referrer: document.referrer || null
    };

    if (extraData) {
      for (var key in extraData) {
        if (extraData.hasOwnProperty(key)) {
          payload[key] = extraData[key];
        }
      }
    }

    var xhr = new XMLHttpRequest();
    xhr.open('POST', TRACKPRO_API + '/api/tracking/event', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.setRequestHeader('x-api-token', TRACKPRO_TOKEN);
    xhr.send(JSON.stringify(payload));
  }

  // ========== Initialize ==========
  function init() {
    var params = getUrlParams();
    storeUtmParams(params);

    // Auto-send pageview
    sendEvent('pageview');
  }

  // ========== Public API ==========
  window.TrackPro = {
    track: function(eventType, data) {
      sendEvent(eventType, data);
    },

    trackPurchase: function(orderData) {
      sendEvent('purchase', {
        order_id: orderData.order_id || null,
        value: orderData.value || null,
        product: orderData.product || null
      });
    },

    getSessionId: function() {
      return getSessionId();
    },

    getUtmParams: function() {
      return getStoredUtms();
    },

    identify: function(email) {
      sendEvent('identify', { customer_email: email });
    }
  };

  // Auto-initialize on load
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    init();
  } else {
    document.addEventListener('DOMContentLoaded', init);
  }
})();
`;
}

module.exports = {
  recordEvent,
  recordPageview,
  recordClick,
  recordPurchase,
  attributeOrder,
  extractAttribution,
  getTrackingScript
};
