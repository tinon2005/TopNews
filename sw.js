// GlobalPulse Service Worker
// 每天自動清除舊緩存，確保內容是最新的

const CACHE_NAME = 'globalpulse-v1';
const TODAY = new Date().toISOString().split('T')[0];
const CACHE_KEY = `globalpulse-${TODAY}`;

const ASSETS = [
  '/TopNews/',
  '/TopNews/index.html',
  '/TopNews/manifest.json',
];

// 安裝：緩存核心資源
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_KEY).then(cache => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

// 激活：清除昨天的舊緩存
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key.startsWith('globalpulse-') && key !== CACHE_KEY)
          .map(key => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// 攔截請求：網絡優先，失敗時用緩存（確保每天都拿到最新新聞）
self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request)
      .then(response => {
        // 成功拿到最新內容，更新緩存
        const clone = response.clone();
        caches.open(CACHE_KEY).then(cache => cache.put(event.request, clone));
        return response;
      })
      .catch(() =>
        // 離線時回退到緩存
        caches.match(event.request)
      )
  );
});
