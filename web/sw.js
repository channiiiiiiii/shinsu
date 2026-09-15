const CACHE = "shisu-v0.1.0";
const ASSETS = ["/", "/assets/styles.css", "/assets/app.js", "/assets/manifest.webmanifest"];
self.addEventListener("install", event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS))));
self.addEventListener("fetch", event => {
  if (event.request.method === "GET" && !event.request.url.includes("/api/")) {
    event.respondWith(caches.match(event.request).then(hit => hit || fetch(event.request)));
  }
});

