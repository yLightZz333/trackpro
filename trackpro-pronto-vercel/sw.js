// TrackPro PWA Service Worker v2.6 - Notificações em Tempo Real & Auto Purge Cache
const CACHE_NAME = 'trackpro-v2-6-nocache';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(keys.map((key) => caches.delete(key)));
    })
  );
  if (self.clients && self.clients.claim) {
    self.clients.claim();
  }
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request, { cache: 'no-cache' })
      .then((networkResponse) => {
        return networkResponse;
      })
      .catch(() => caches.match(event.request))
  );
});

// Manipulador de Notificações Push no Celular
self.addEventListener('push', (event) => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { title: 'TrackPro Alerta', body: event.data.text() };
    }
  }
  const title = data.title || '💸 Venda Aprovada - TrackPro';
  const options = {
    body: data.body || 'Nova notificação da sua operação!',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    vibrate: [250, 100, 250, 100, 250],
    data: data.data || { url: '/' },
    tag: data.tag || 'trackpro-sale-alert',
    renotify: true,
    requireInteraction: true
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// Clique na notificação abre o app no celular
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const urlToOpen = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (let client of windowClients) {
        if (client.url.includes(urlToOpen) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});
