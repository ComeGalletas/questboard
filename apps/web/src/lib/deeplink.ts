// questboard:// targets (notifications, Tauri deep links) -> app paths.

export function targetToPath(target: string): string {
  // A trailing slash is allowed: Windows hands deep links to the desktop shell as
  // "questboard://week/".
  const m = /^questboard:\/\/([a-z]+)(?:\/([\w-]+))?\/?$/.exec(target);
  if (!m) return "/today";
  const [, kind, id] = m;
  if (kind === "week" || kind === "month" || kind === "today") return `/${kind}`;
  if (kind === "quest" && id) return `/today?quest=${encodeURIComponent(id)}`;
  return "/today";
}
