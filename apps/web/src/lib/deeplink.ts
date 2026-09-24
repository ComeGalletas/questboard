// questboard:// targets (notifications, Tauri deep links) -> app paths.

export function targetToPath(target: string): string {
  const m = /^questboard:\/\/([a-z]+)(?:\/([\w-]+))?$/.exec(target);
  if (!m) return "/today";
  const [, kind, id] = m;
  if (kind === "week" || kind === "month" || kind === "today") return `/${kind}`;
  if (kind === "quest" && id) return `/today?quest=${encodeURIComponent(id)}`;
  return "/today";
}
