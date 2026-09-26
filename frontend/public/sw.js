/* «Маршрут» offline support: the app shell and the last loaded route stay available
   without a connection (a queue at the МФЦ, the metro). Writes always need the network. */
const CACHE = "marshrut-v1";
const API_CACHEABLE = [
  /^\/api\/v1\/routes\/current$/,
  /^\/api\/v1\/routes\/[^/]+\/steps\/[^/]+$/,
  /^\/api\/v1\/routes\/[^/]+\/checklist$/,
  /^\/api\/v1\/(profile|help|regions|universities|config)$/,
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.add("/")));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

async function networkFirst(request, cacheKey) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(cacheKey, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(cacheKey);
    if (!cached) throw error;
    // Tell the app it is looking at a saved copy.
    const headers = new Headers(cached.headers);
    headers.set("X-Offline", "1");
    return new Response(await cached.blob(), { status: cached.status, headers });
  }
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/assets/")) {
    // Hashed file names: cache forever.
    event.respondWith(
      caches.open(CACHE).then(async (cache) => {
        const cached = await cache.match(request);
        if (cached) return cached;
        const response = await fetch(request);
        if (response.ok) await cache.put(request, response.clone());
        return response;
      }),
    );
    return;
  }
  if (API_CACHEABLE.some((pattern) => pattern.test(url.pathname))) {
    // The language is part of the key: Russian and English copies are kept apart.
    const key = `${url.pathname}${url.search}#${request.headers.get("Accept-Language") || "ru"}`;
    event.respondWith(networkFirst(request, key));
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request, "/"));
  }
});
