// Version bump forces cache refresh - increment on each deployment
const CACHE_VERSION = 'v2';
const CACHE_NAME = `haven-ui-cache-${CACHE_VERSION}`;

// Static assets that rarely change
const STATIC_ASSETS = [
  '/haven-ui/icon.svg',
  '/haven-ui/favicon.svg'
];

// Install: cache only static assets, skip JS/HTML (they change frequently)
self.addEventListener('install', (e) => {
  // Force immediate activation (don't wait for old SW to finish)
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
});

// Activate: delete old caches
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter(key => key !== CACHE_NAME)
            .map(key => caches.delete(key))
      );
    }).then(() => {
      // Claim all clients immediately
      return self.clients.claim();
    })
  );
});

// Fetch: Network-first for HTML/JS, cache-first only for static assets
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  // Only handle same-origin requests
  if (url.origin !== location.origin) return;

  // For HTML and JS files: always try network first (ensures fresh code)
  if (e.request.destination === 'document' ||
      url.pathname.endsWith('.js') ||
      url.pathname.endsWith('.html') ||
      url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(e.request)
        .catch(() => caches.match(e.request)) // Only use cache if offline
    );
    return;
  }

  // For static assets (images, icons): cache-first for performance
  e.respondWith(
    caches.match(e.request).then((cached) => cached || fetch(e.request))
  );
});
