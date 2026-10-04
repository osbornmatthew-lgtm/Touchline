const C = 'touchline-' + 'bcfa' + '-v3';
self.addEventListener('install', e => { self.skipWaiting(); e.waitUntil(caches.open(C).then(c => c.addAll(['./', 'manifest.json', 'icon-192.png', 'apple-touch-icon.png']))); });
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  // Only pages and files directly in this site's folder (not calendar feeds, not another league's folder).
  if (r.method !== 'GET' || u.origin !== location.origin || u.pathname.includes('/cal/') || u.pathname.slice(new URL(self.registration.scope).pathname.length).includes('/')) return;
  const fromCache = () => caches.match(r, { ignoreSearch: true }).then(m => m || caches.match('./'));
  e.respondWith(new Promise(resolve => {
    let done = false; const finish = x => { if (!done && x) { done = true; resolve(x); } };
    const t = setTimeout(() => fromCache().then(finish), 3500);
    fetch(r).then(res => { clearTimeout(t); if (res.ok) { const cp = res.clone(); caches.open(C).then(c => c.put(r, cp)); } if (!done) { done = true; resolve(res); } })
      .catch(() => { clearTimeout(t); fromCache().then(m => { if (!done) { done = true; resolve(m || Response.error()); } }); });
  }));
});
