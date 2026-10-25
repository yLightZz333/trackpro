/**
 * TrackPro Client-Side Tracking Pixel
 * Compatible with UTMify pixel specs
 */
(function() {
  'use strict';

  var COOKIE_DAYS = 30;
  var SESSION_KEY = '_trackpro_sid';
  var UTM_KEY = '_trackpro_utms';

  // Extract token from script tag src if present
  var scripts = document.getElementsByTagName('script');
  var currentScript = scripts[scripts.length - 1];
  var scriptSrc = currentScript ? currentScript.src : '';
  var scriptUrl = new URL(scriptSrc, window.location.href);
  var TRACKPRO_TOKEN = scriptUrl.searchParams.get('token') || window.TRACKPRO_TOKEN || '';
  var TRACKPRO_API = scriptUrl.origin || window.TRACKPRO_API || '';

  function setCookie(name, value, days) {
    var expires = '';
    if (days) {
      var date = new Date();
      date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
      expires = '; expires=' + date.toUTCString();
    }
    document.cookie = name + '=' + (encodeURIComponent(value) || '') + expires + '; path=/; SameSite=Lax';
  }

  function getCookie(name) {
    var nameEQ = name + '=';
    var ca = document.cookie.split(';');
    for (var i = 0; i < ca.length; i++) {
      var c = ca[i];
      while (c.charAt(0) === ' ') c = c.substring(1, c.length);
      if (c.indexOf(nameEQ) === 0) return decodeURIComponent(c.substring(nameEQ.length, c.length));
    }
    return null;
  }

  function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  function getUrlParams() {
    var params = {};
    var search = window.location.search.substring(1);
    if (!search) return params;
    var pairs = search.split('&');
    for (var i = 0; i < pairs.length; i++) {
      var pair = pairs[i].split('=');
      var key = decodeURIComponent(pair[0]);
      var value = decodeURIComponent(pair[1] || '');
      params[key] = value;
    }
    return params;
  }

  function getSessionId() {
    var sessionId = getCookie(SESSION_KEY);
    if (!sessionId) {
      sessionId = generateUUID();
      setCookie(SESSION_KEY, sessionId, COOKIE_DAYS);
    }
    return sessionId;
  }

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
    xhr.open('POST', (TRACKPRO_API || '') + '/api/tracking/event', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    if (TRACKPRO_TOKEN) {
      xhr.setRequestHeader('x-api-token', TRACKPRO_TOKEN);
    }
    xhr.send(JSON.stringify(payload));
  }

  function init() {
    var params = getUrlParams();
    storeUtmParams(params);
    sendEvent('pageview');
  }

  window.TrackPro = {
    track: function(eventType, data) {
      sendEvent(eventType, data);
    },
    trackPurchase: function(orderData) {
      sendEvent('purchase', orderData);
    },
    getSessionId: function() {
      return getSessionId();
    },
    getUtmParams: function() {
      return getStoredUtms();
    }
  };

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    init();
  } else {
    document.addEventListener('DOMContentLoaded', init);
  }
})();
