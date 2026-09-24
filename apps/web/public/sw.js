// Questboard service worker: shows Web Push notifications sent by the runner and opens the
// matching screen on tap. Payload: {kind, title, body, target, persona}.

function targetToPath(target) {
  const m = /^questboard:\/\/([a-z]+)(?:\/([\w-]+))?$/.exec(target || "");
  if (!m) return "/today";
  const kind = m[1];
  const id = m[2];
  if (kind === "week" || kind === "month" || kind === "today") return "/" + kind;
  if (kind === "quest" && id) return "/today?quest=" + encodeURIComponent(id);
  return "/today";
}

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }
  const persona = data.persona || null;
  event.waitUntil(
    self.registration.showNotification(data.title || "Questboard", {
      body: data.body || "",
      icon: persona ? "/personas/" + persona + "/portrait.png" : "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      tag: (data.kind || "note") + ":" + (data.target || ""),
      data: { path: targetToPath(data.target) },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const path = (event.notification.data && event.notification.data.path) || "/today";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if ("focus" in w) {
          w.navigate(path);
          return w.focus();
        }
      }
      return self.clients.openWindow(path);
    }),
  );
});
