// Deterministic voice grammar (P2, on-device, es/en). Mirrors runner/runner/voice/grammar.py;
// both are locked to packages/schema/fixtures/voice.json. The output is only ever shown on a
// confirmation card: voice never writes by itself (invariant 8).
//
// Dates are parsed here rather than with chrono-node: it drops "at ten" / "a las diez" and
// "pasado mañana", and the runner needs the exact same results in Python anyway.

import type { VoiceCommand } from "@questboard/schema";

export type Lang = VoiceCommand["lang"];

type Tok = { raw: string; norm: string };
type When = { date?: string; time?: string };

// -- lexicon -------------------------------------------------------------------------------------

const WEEKDAYS: Record<Lang, string[]> = {
  en: ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
  es: ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"],
};

const MONTHS: Record<Lang, string[]> = {
  en: "january february march april may june july august september october november december".split(
    " ",
  ),
  es: "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(
    " ",
  ),
};

const UNITS: Record<Lang, Record<string, number>> = {
  en: {
    a: 1,
    an: 1,
    one: 1,
    two: 2,
    three: 3,
    four: 4,
    five: 5,
    six: 6,
    seven: 7,
    eight: 8,
    nine: 9,
    ten: 10,
    eleven: 11,
    twelve: 12,
    thirteen: 13,
    fourteen: 14,
    fifteen: 15,
    sixteen: 16,
    seventeen: 17,
    eighteen: 18,
    nineteen: 19,
    twenty: 20,
    thirty: 30,
    forty: 40,
    fifty: 50,
    sixty: 60,
    ninety: 90,
  },
  es: {
    un: 1,
    una: 1,
    uno: 1,
    dos: 2,
    tres: 3,
    cuatro: 4,
    cinco: 5,
    seis: 6,
    siete: 7,
    ocho: 8,
    nueve: 9,
    diez: 10,
    once: 11,
    doce: 12,
    trece: 13,
    catorce: 14,
    quince: 15,
    dieciseis: 16,
    diecisiete: 17,
    dieciocho: 18,
    diecinueve: 19,
    veinte: 20,
    veintiuno: 21,
    veintidos: 22,
    veintitres: 23,
    veinticuatro: 24,
    veinticinco: 25,
    veintiseis: 26,
    veintisiete: 27,
    veintiocho: 28,
    veintinueve: 29,
    treinta: 30,
    cuarenta: 40,
    cincuenta: 50,
    sesenta: 60,
    noventa: 90,
  },
};

type Phrase = string[];
const p = (...alts: string[]): Phrase[] => alts.map((a) => a.split(" "));

type Grammar = {
  create: Phrase[];
  createFiller: Phrase[][]; // optional groups after the verb, in order
  complete: Phrase[];
  completeTail: Phrase[];
  snoozeOnly: Phrase[];
  deferOnly: Phrase[];
  either: Phrase[]; // postpone: snooze without a day, defer with one
  whatsNext: Phrase[];
  confirm: Phrase[];
  cancel: Phrase[];
  datePrefix: Phrase[]; // before a date piece
  durationPrefix: Phrase[];
  connectors: string[]; // dropped from the end of a title / quest name
  articles: string[]; // dropped from the start of a quest name
  polite: Phrase[];
};

const GRAMMAR: Record<Lang, Grammar> = {
  en: {
    create: p("create", "add", "new", "make"),
    createFiller: [p("a", "an", "new"), p("task", "quest", "todo", "to do"), p("to")],
    complete: p(
      "complete",
      "completed",
      "finish",
      "finished",
      "done with",
      "done",
      "mark",
      "check off",
      "i finished",
      "i completed",
      "i did",
      "im done with",
      "i am done with",
    ),
    completeTail: p("as done", "as complete", "as completed", "as finished", "done"),
    snoozeOnly: p("snooze", "remind me about"),
    deferOnly: p("defer", "move", "push", "reschedule"),
    either: p("postpone"),
    whatsNext: p(
      "whats next",
      "what is next",
      "what now",
      "what should i do",
      "what should i do next",
      "what should i do now",
      "next quest",
      "next task",
      "whats my next quest",
      "whats my next task",
    ),
    confirm: p(
      "confirm",
      "confirmed",
      "yes",
      "yeah",
      "yep",
      "do it",
      "ok",
      "okay",
      "sure",
      "go ahead",
    ),
    cancel: p("cancel", "no", "stop", "never mind", "nevermind", "forget it"),
    datePrefix: p("on", "for", "by"),
    durationPrefix: p("for", "in"),
    connectors: ["on", "for", "by", "at", "to", "until", "till"],
    articles: ["the", "my"],
    polite: p("please"),
  },
  es: {
    create: p(
      "crear",
      "crea",
      "agregar",
      "agrega",
      "anadir",
      "anade",
      "nueva",
      "nuevo",
      "anota",
      "anotar",
    ),
    createFiller: [
      p("una", "un", "la", "el", "nueva"),
      p("tarea", "mision", "quest", "pendiente"),
      p("de", "para"),
    ],
    complete: p(
      "completar",
      "completa",
      "complete",
      "terminar",
      "termina",
      "termine",
      "ya termine",
      "ya hice",
      "hice",
      "marcar",
      "marca",
    ),
    completeTail: p(
      "como hecha",
      "como hecho",
      "como completada",
      "como completado",
      "como terminada",
      "como terminado",
    ),
    snoozeOnly: p("recuerdame"),
    deferOnly: p(
      "aplazar",
      "aplaza",
      "pasar",
      "pasa",
      "mover",
      "mueve",
      "reprogramar",
      "reprograma",
    ),
    either: p("posponer", "pospon"),
    whatsNext: p(
      "que sigue",
      "que hago",
      "que hago ahora",
      "que debo hacer",
      "que debo hacer ahora",
      "siguiente",
      "siguiente tarea",
      "siguiente mision",
      "que es lo siguiente",
      "lo siguiente",
      "cual es la siguiente tarea",
    ),
    confirm: p(
      "confirmar",
      "confirmo",
      "confirma",
      "si",
      "dale",
      "hazlo",
      "vale",
      "ok",
      "de acuerdo",
      "listo",
    ),
    cancel: p("cancelar", "cancela", "no", "olvidalo", "detente"),
    datePrefix: p("para el", "hasta el", "el", "al", "para", "hasta"),
    durationPrefix: p("por", "durante", "en"),
    connectors: ["el", "para", "a", "al", "hasta", "de", "por", "en"],
    articles: ["el", "la", "los", "las", "mi", "mis"],
    polite: p("por favor"),
  },
};

// -- tokens --------------------------------------------------------------------------------------

export function normalize(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function tokenize(text: string): Tok[] {
  const spaced = text
    .replace(/\b([ap])\.m\./gi, "$1m")
    .replace(/(\d)(am|pm)\b/gi, "$1 $2")
    .replace(/[¿¡?!.,;"()]+/g, " ")
    .replace(/:(?!\d)/g, " ");
  return spaced
    .split(/\s+/)
    .filter(Boolean)
    .map((raw) => ({ raw, norm: normalize(raw).replace(/['’]/g, "").replace(/-/g, " ") }))
    .flatMap((t) =>
      t.norm.includes(" ") ? t.norm.split(" ").map((n) => ({ raw: n, norm: n })) : [t],
    )
    .filter((t) => t.norm);
}

/** Length of the longest phrase in `phrases` that `toks` starts with at `i`, else 0. */
function lead(toks: Tok[], i: number, phrases: Phrase[]): number {
  let best = 0;
  for (const ph of phrases) {
    if (ph.length > best && ph.every((w, k) => toks[i + k]?.norm === w)) best = ph.length;
  }
  return best;
}

function whole(toks: Tok[], phrases: Phrase[]): boolean {
  return toks.length > 0 && lead(toks, 0, phrases) === toks.length;
}

/** Longest phrase `toks` ends with. */
function tail(toks: Tok[], phrases: Phrase[]): number {
  let best = 0;
  for (const ph of phrases) {
    const start = toks.length - ph.length;
    if (ph.length > best && start >= 0 && ph.every((w, k) => toks[start + k].norm === w)) {
      best = ph.length;
    }
  }
  return best;
}

// -- numbers, dates, times -----------------------------------------------------------------------

/** A number at `i`: digits or words ("twenty five", "treinta y uno"). Returns [value, length]. */
function number(toks: Tok[], i: number, lang: Lang): [number, number] | null {
  const t = toks[i]?.norm;
  if (t === undefined) return null;
  if (/^\d{1,4}$/.test(t)) return [Number(t), 1];
  const units = UNITS[lang];
  const v = units[t];
  if (v === undefined) return null;
  if (v >= 20 && v % 10 === 0 && v < 100) {
    const joiner = lang === "es" && toks[i + 1]?.norm === "y" ? 1 : 0;
    const next = units[toks[i + 1 + joiner]?.norm ?? ""];
    if (next !== undefined && next >= 1 && next <= 9 && toks[i + 1 + joiner].norm.length > 1) {
      return [v + next, 2 + joiner];
    }
  }
  return [v, 1];
}

function ymd(y: number, m: number, d: number): string {
  const dt = new Date(Date.UTC(y, m - 1, d));
  return dt.toISOString().slice(0, 10);
}

function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  return ymd(y, m, d + n);
}

/** Monday = 0. */
function weekday(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
}

/** The next `wd` strictly after today. */
function nextWeekday(today: string, wd: number): string {
  const diff = (wd - weekday(today) + 7) % 7 || 7;
  return addDays(today, diff);
}

/** Day `d` of month `m` (1-12), this year or next, on or after today. */
function dayOfMonth(today: string, m: number, d: number): string | null {
  const [y] = today.split("-").map(Number);
  for (const year of [y, y + 1]) {
    const iso = ymd(year, m, d);
    if (Number(iso.slice(5, 7)) !== m) return null; // e.g. 31 September
    if (iso >= today) return iso;
  }
  return null;
}

/** Day `d` of this month or the next, on or after today. */
function dayOfAnyMonth(today: string, d: number): string | null {
  const [y, m] = today.split("-").map(Number);
  for (let k = 0; k < 3; k++) {
    const month = ((m - 1 + k) % 12) + 1;
    const year = y + Math.floor((m - 1 + k) / 12);
    const iso = ymd(year, month, d);
    if (Number(iso.slice(5, 7)) === month && iso >= today) return iso;
  }
  return null;
}

function dayNumber(toks: Tok[], i: number, lang: Lang): [number, number] | null {
  const ord = /^(\d{1,2})(st|nd|rd|th)$/.exec(toks[i]?.norm ?? "");
  if (ord && lang === "en") return [Number(ord[1]), 1];
  const n = number(toks, i, lang);
  return n && n[0] >= 1 && n[0] <= 31 ? n : null;
}

/** A date piece at `i`: returns [iso, tokens used]. */
function datePiece(toks: Tok[], i: number, today: string, lang: Lang): [string, number] | null {
  const pre = lead(toks, i, GRAMMAR[lang].datePrefix);
  for (const skip of pre > 0 ? [pre, 0] : [0]) {
    const r = datePieceBare(toks, i + skip, today, lang);
    if (r) return [r[0], r[1] + skip];
  }
  return null;
}

function datePieceBare(toks: Tok[], i: number, today: string, lang: Lang): [string, number] | null {
  const at = (k: number) => toks[i + k]?.norm;
  const wdIndex = (w: string | undefined) => (w ? WEEKDAYS[lang].indexOf(w) : -1);
  const monthIndex = (w: string | undefined) => (w ? MONTHS[lang].indexOf(w) : -1);

  if (lang === "en") {
    if (at(0) === "today" || at(0) === "tonight") return [today, 1];
    if (at(0) === "tomorrow") return [addDays(today, 1), 1];
    if (at(0) === "the" && at(1) === "day" && at(2) === "after" && at(3) === "tomorrow") {
      return [addDays(today, 2), 4];
    }
    if (at(0) === "day" && at(1) === "after" && at(2) === "tomorrow") return [addDays(today, 2), 3];
    if (at(0) === "next" && at(1) === "week") return [nextWeekday(today, 0), 2];
    const mod = ["this", "next", "coming"].includes(at(0) ?? "") ? 1 : 0;
    const wd = wdIndex(at(mod));
    if (wd >= 0) return [nextWeekday(today, wd), mod + 1];
    if (at(0) === "in") {
      const n = number(toks, i + 1, lang);
      if (n) {
        const unit = at(1 + n[1]);
        if (unit === "day" || unit === "days") return [addDays(today, n[0]), 2 + n[1]];
        if (unit === "week" || unit === "weeks") return [addDays(today, 7 * n[0]), 2 + n[1]];
      }
    }
    const mo = monthIndex(at(0));
    if (mo >= 0) {
      const d = dayNumber(toks, i + 1, lang);
      if (d) {
        const iso = dayOfMonth(today, mo + 1, d[0]);
        return iso ? [iso, 1 + d[1]] : null;
      }
    }
    const the = at(0) === "the" ? 1 : 0;
    const d = dayNumber(toks, i + the, lang);
    if (d) {
      const used = the + d[1];
      if (at(used) === "of" && monthIndex(at(used + 1)) >= 0) {
        const iso = dayOfMonth(today, monthIndex(at(used + 1)) + 1, d[0]);
        return iso ? [iso, used + 2] : null;
      }
      const ordinal = /(st|nd|rd|th)$/.test(toks[i + the].norm);
      if (ordinal && (the || used === 1)) {
        const iso = dayOfAnyMonth(today, d[0]);
        return iso ? [iso, used] : null;
      }
    }
    return null;
  }

  // es
  if (at(0) === "hoy") return [today, 1];
  if (at(0) === "esta" && (at(1) === "noche" || at(1) === "tarde")) return [today, 2];
  if (at(0) === "pasado" && at(1) === "manana") return [addDays(today, 2), 2];
  if (at(0) === "manana") return [addDays(today, 1), 1];
  if (at(0) === "la" && at(1) === "proxima" && at(2) === "semana")
    return [nextWeekday(today, 0), 3];
  if (at(0) === "la" && at(1) === "semana" && at(2) === "que" && at(3) === "viene") {
    return [nextWeekday(today, 0), 4];
  }
  if (at(0) === "proxima" && at(1) === "semana") return [nextWeekday(today, 0), 2];
  if (at(0) === "en") {
    const n = number(toks, i + 1, lang);
    if (n) {
      const unit = at(1 + n[1]);
      if (unit === "dia" || unit === "dias") return [addDays(today, n[0]), 2 + n[1]];
      if (unit === "semana" || unit === "semanas") return [addDays(today, 7 * n[0]), 2 + n[1]];
    }
  }
  const mod = at(0) === "proximo" || at(0) === "este" ? 1 : 0;
  const wd = wdIndex(at(mod));
  if (wd >= 0) {
    const after = at(mod + 1) === "que" && at(mod + 2) === "viene" ? 2 : 0;
    return [nextWeekday(today, wd), mod + 1 + after];
  }
  const d = dayNumber(toks, i, lang);
  if (d) {
    if (at(d[1]) === "de" && monthIndex(at(d[1] + 1)) >= 0) {
      const iso = dayOfMonth(today, monthIndex(at(d[1] + 1)) + 1, d[0]);
      return iso ? [iso, d[1] + 2] : null;
    }
    // "el 30": only straight after "el" (the caller's prefix), never a bare number.
    if (i > 0 && toks[i - 1].norm === "el") {
      const iso = dayOfAnyMonth(today, d[0]);
      return iso ? [iso, d[1]] : null;
    }
  }
  return null;
}

function hhmm(h: number, m: number): string | null {
  if (h < 0 || h > 23 || m < 0 || m > 59) return null;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/** An hour (+ minutes) at `i`: "10", "10:30", "ten". Returns [h, m, used]. */
function clock(toks: Tok[], i: number, lang: Lang): [number, number, number] | null {
  const t = toks[i]?.norm ?? "";
  const hm = /^(\d{1,2}):(\d{2})$/.exec(t);
  if (hm) return [Number(hm[1]), Number(hm[2]), 1];
  if (t === "a" || t === "an") return null; // "at a …" is not one o'clock
  const n = number(toks, i, lang);
  if (!n || n[0] > 23) return null;
  return [n[0], 0, n[1]];
}

/** Hours said without am/pm: 1-6 mean afternoon, 7-11 morning (task times, not alarms). */
function guessHour(h: number): number {
  return h >= 1 && h <= 6 ? h + 12 : h;
}

/** A time piece at `i`: returns [HH:MM, tokens used]. */
function timePiece(toks: Tok[], i: number, lang: Lang): [string, number] | null {
  const at = (k: number) => toks[i + k]?.norm;
  if (lang === "en") {
    const lead0 = at(0) === "at" ? 1 : 0;
    if (at(lead0) === "noon" || at(lead0) === "midday") return ["12:00", lead0 + 1];
    if (at(lead0) === "midnight") return ["00:00", lead0 + 1];
    const c = clock(toks, i + lead0, lang);
    if (!c) return null;
    const m = c[1];
    let h = c[0];
    let used = c[2] + lead0;
    const q = at(used);
    const q3 = [at(used), at(used + 1), at(used + 2)].join(" ");
    let pm: boolean | null = null;
    if (q === "am" || q === "pm") {
      pm = q === "pm";
      used += 1;
    } else if (q3 === "in the morning") {
      pm = false;
      used += 3;
    } else if (q3 === "in the afternoon" || q3 === "in the evening") {
      pm = true;
      used += 3;
    } else if (q === "at" && at(used + 1) === "night") {
      pm = true;
      used += 2;
    } else if (q === "oclock") {
      used += 1;
    }
    if (!lead0 && pm === null) return null; // a bare number is not a time
    if (h > 12 && pm !== null) return null;
    if (pm === true && h < 12) h += 12;
    else if (pm === false && h === 12) h = 0;
    else if (pm === null && h <= 12) h = guessHour(h);
    const s = hhmm(h, m);
    return s ? [s, used] : null;
  }

  // es
  if (at(0) === "al" && at(1) === "mediodia") return ["12:00", 2];
  if (at(0) === "a" && at(1) === "mediodia") return ["12:00", 2];
  if (at(0) === "a" && at(1) === "medianoche") return ["00:00", 2];
  let lead0 = 0;
  if (at(0) === "a" && (at(1) === "las" || at(1) === "la")) lead0 = 2;
  const c = clock(toks, i + lead0, lang);
  if (!c) return null;
  let [h, m, used] = c;
  used += lead0;
  if (at(used) === "y" && at(used + 1) === "media") {
    m = 30;
    used += 2;
  } else if (at(used) === "y" && at(used + 1) === "cuarto") {
    m = 15;
    used += 2;
  }
  let pm: boolean | null = null;
  const q = [at(used), at(used + 1), at(used + 2)].join(" ");
  if (q === "de la manana") {
    pm = false;
    used += 3;
  } else if (q === "de la tarde" || q === "de la noche") {
    pm = true;
    used += 3;
  } else if (at(used) === "am" || at(used) === "pm") {
    pm = at(used) === "pm";
    used += 1;
  } else if (at(used) === "en" && at(used + 1) === "punto") {
    used += 2;
  }
  if (!lead0 && pm === null) return null;
  if (h > 12 && pm !== null) return null;
  if (pm === true && h < 12) h += 12;
  else if (pm === true && h === 12 && q === "de la noche") h = 0;
  else if (pm === false && h === 12) h = 0;
  else if (pm === null && h <= 12) h = guessHour(h);
  const s = hhmm(h, m);
  return s ? [s, used] : null;
}

/** All of `toks` as one date and/or time expression, in either order. */
function parseWhen(toks: Tok[], today: string, lang: Lang): When | null {
  const out: When = {};
  let i = 0;
  while (i < toks.length) {
    const d = out.date === undefined ? datePiece(toks, i, today, lang) : null;
    if (d) {
      out.date = d[0];
      i += d[1];
      continue;
    }
    const t = out.time === undefined ? timePiece(toks, i, lang) : null;
    if (t) {
      out.time = t[0];
      i += t[1];
      continue;
    }
    return null;
  }
  if (out.date === undefined && out.time === undefined) return null;
  if (out.time !== undefined && out.date === undefined) out.date = today;
  return out;
}

/** Split `toks` into [head, when] at the longest trailing date/time expression. */
function trailingWhen(toks: Tok[], today: string, lang: Lang): [Tok[], When] | null {
  for (let start = 1; start < toks.length; start++) {
    const when = parseWhen(toks.slice(start), today, lang);
    if (when) return [toks.slice(0, start), when];
  }
  return null;
}

/** Minutes for all of `toks` ("20 minutes", "an hour and a half", "media hora"). */
function parseDuration(toks: Tok[], lang: Lang): number | null {
  const g = GRAMMAR[lang];
  const i = lead(toks, 0, g.durationPrefix);
  const rest = toks.slice(i).map((t) => t.norm);
  const s = rest.join(" ");
  if (lang === "en") {
    if (s === "half an hour" || s === "a half hour") return 30;
    if (s === "an hour and a half" || s === "one and a half hours") return 90;
  } else {
    if (s === "media hora") return 30;
    if (s === "una hora y media" || s === "hora y media") return 90;
  }
  const n = number(toks, i, lang);
  if (!n) return null;
  const unit = rest[n[1]];
  const extra = rest.slice(n[1] + 1).join(" ");
  const half = lang === "en" ? extra === "and a half" : extra === "y media";
  if (extra && !half) return null;
  const minutes = /^(minute|minutes|min|mins|minuto|minutos)$/.test(unit ?? "")
    ? n[0]
    : /^(hour|hours|hora|horas)$/.test(unit ?? "")
      ? n[0] * 60 + (half ? 30 : 0)
      : null;
  if (minutes === null || (half && !/^h/.test(unit ?? ""))) return null;
  return minutes >= 1 && minutes <= 1440 ? minutes : null;
}

function trailingDuration(toks: Tok[], lang: Lang): [Tok[], number] | null {
  for (let start = 1; start < toks.length; start++) {
    const m = parseDuration(toks.slice(start), lang);
    if (m !== null) return [toks.slice(0, start), m];
  }
  return null;
}

// -- commands ------------------------------------------------------------------------------------

function stripConnectors(toks: Tok[], lang: Lang): Tok[] {
  const out = [...toks];
  while (out.length > 1 && GRAMMAR[lang].connectors.includes(out[out.length - 1].norm)) out.pop();
  return out;
}

function questName(toks: Tok[], lang: Lang): string | undefined {
  let out = stripConnectors(toks, lang);
  while (out.length > 1 && GRAMMAR[lang].articles.includes(out[0].norm)) out = out.slice(1);
  const s = out
    .map((t) => t.raw)
    .join(" ")
    .slice(0, 120);
  return s || undefined;
}

function titleOf(toks: Tok[], lang: Lang): string {
  const s = stripConnectors(toks, lang)
    .map((t) => t.raw)
    .join(" ")
    .slice(0, 120);
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function parseIn(toks: Tok[], today: string, lang: Lang): VoiceCommand | null {
  const g = GRAMMAR[lang];
  if (whole(toks, g.whatsNext)) return { intent: "whats_next", lang };
  if (whole(toks, g.confirm)) return { intent: "confirm", lang };
  if (whole(toks, g.cancel)) return { intent: "cancel", lang };

  let n = lead(toks, 0, g.create);
  if (n > 0) {
    for (const group of g.createFiller) n += lead(toks, n, group);
    const rest = toks.slice(n);
    if (rest.length === 0) return null;
    const split = trailingWhen(rest, today, lang);
    const cmd: VoiceCommand = {
      intent: "create",
      lang,
      title: titleOf(split ? split[0] : rest, lang),
    };
    if (split?.[1].date) cmd.date = split[1].date;
    if (split?.[1].time) cmd.time = split[1].time;
    return cmd;
  }

  const snooze = lead(toks, 0, g.snoozeOnly);
  const defer = lead(toks, 0, g.deferOnly);
  const either = lead(toks, 0, g.either);
  const verb = Math.max(snooze, defer, either);
  if (verb > 0) {
    const rest = toks.slice(verb);
    if (rest.length === 0) return null;
    const dur = trailingDuration(rest, lang);
    if (dur) return { intent: "snooze", lang, quest: questName(dur[0], lang), minutes: dur[1] };
    const when = trailingWhen(rest, today, lang);
    if (when) return { intent: "defer", lang, quest: questName(when[0], lang), date: when[1].date };
    const intent = defer === verb ? "defer" : "snooze";
    return { intent, lang, quest: questName(rest, lang) };
  }

  n = lead(toks, 0, g.complete);
  if (n > 0) {
    let rest = toks.slice(n);
    const t = tail(rest, g.completeTail);
    if (t > 0 && rest.length > t) rest = rest.slice(0, rest.length - t);
    if (rest.length === 0) return null;
    return { intent: "complete", lang, quest: questName(rest, lang) };
  }
  return null;
}

/** Parse one utterance. `today` is the local reference day (YYYY-MM-DD). */
export function parseCommand(text: string, today: string, hint: Lang = "en"): VoiceCommand {
  const langs: Lang[] = hint === "es" ? ["es", "en"] : ["en", "es"];
  for (const lang of langs) {
    let toks = tokenize(text);
    const g = GRAMMAR[lang];
    toks = toks.slice(lead(toks, 0, g.polite));
    const t = tail(toks, g.polite);
    if (t > 0 && toks.length > t) toks = toks.slice(0, toks.length - t);
    const cmd = parseIn(toks, today, lang);
    if (cmd) return cmd;
  }
  return { intent: "unknown", lang: hint };
}
