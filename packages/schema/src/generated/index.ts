/* Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`. */

export interface QuestboardSchemas {
  common?: Common;
  config?: Config;
  daily_plan?: DailyPlan;
  extracted_record?: ExtractedRecord;
  fallback_lines?: FallbackLines;
  llm_run?: LLMRun;
  persona_line?: PersonaLine;
  persona_pack?: PersonaPack;
  quest?: Quest;
  quest_diff?: QuestDiff;
  quest_proposal?: QuestProposal;
  runner_state?: RunnerState;
}
/**
 * Shared enums and value types referenced by the other schemas.
 */
export interface Common {
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Common`'s JSON-Schema
 * via the `definition` "QuietHours".
 */
export interface QuietHours {
  /**
   * Wall-clock time HH:MM in the configured timezone.
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "LocalTime".
   */
  start: string;
  /**
   * Wall-clock time HH:MM in the configured timezone.
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "LocalTime".
   */
  end: string;
}
/**
 * The single `config` row. Code owns schema, prompts and scoring; config owns goals, personas, capacity and toggles.
 */
export interface Config {
  /**
   * IANA zone, e.g. America/Bogota.
   */
  timezone: string;
  goals: Goal[];
  capacity: {
    weekday_hours: number;
    weekend_hours: number;
    focus_factor: number;
  };
  quiet_hours: QuietHours;
  /**
   * Multiplier per category.
   */
  xp_weights: {
    [k: string]: number;
  };
  llm: {
    /**
     * @minItems 1
     *
     * Items: This interface was referenced by `Common`'s JSON-Schema
     * via the `definition` "ProviderName".
     */
    providers: ["claude-cli" | "ollama" | "claude-api", ...("claude-cli" | "ollama" | "claude-api")[]];
    /**
     * Model per provider, e.g. {"claude-api": "claude-opus-5", "ollama": "qwen3:8b"}. Unset uses the runner default.
     */
    models?: {
      [k: string]: string;
    };
    /**
     * Per-job provider order override, keyed by job name.
     */
    per_job?: {
      /**
       * @minItems 1
       *
       * Items: This interface was referenced by `Common`'s JSON-Schema
       * via the `definition` "ProviderName".
       */
      [k: string]: ["claude-cli" | "ollama" | "claude-api", ...("claude-cli" | "ollama" | "claude-api")[]];
    };
  };
  /**
   * Items: Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "PersonaSlug".
   */
  persona_order: string[];
  integrations: {
    gmail: boolean;
    gcal: boolean;
  };
  features: {
    three_d: boolean;
    mobile_rehydration: boolean;
  };
  notifications: {
    persona_speech_per_day: number;
    persona_speech_on_mobile: boolean;
  };
}
/**
 * This interface was referenced by `Config`'s JSON-Schema
 * via the `definition` "Goal".
 */
export interface Goal {
  id: string;
  title: string;
  horizon: "week" | "month" | "quarter" | "year";
  persona?: string | null;
}
/**
 * daily_am output: quest diffs for today plus the dialogue bundle the app performs from the cache.
 */
export interface DailyPlan {
  diff: QuestDiff;
  /**
   * @maxItems 40
   */
  quest_lines: QuestLines[];
  /**
   * @maxItems 48
   */
  board_lines: BoardLine[];
}
/**
 * What a model proposes against the current quest log. The user accepts or rejects each op; the model never writes quests directly.
 */
export interface QuestDiff {
  /**
   * @maxItems 50
   *
   * Items: This interface was referenced by `QuestDiff`'s JSON-Schema
   * via the `definition` "QuestOp".
   */
  ops: (AddOp | UpdateOp | DropOp)[];
  summary?: string | null;
}
/**
 * This interface was referenced by `QuestDiff`'s JSON-Schema
 * via the `definition` "AddOp".
 */
export interface AddOp {
  op: "add";
  quest: QuestDraft;
  reason: string;
}
/**
 * This interface was referenced by `QuestDiff`'s JSON-Schema
 * via the `definition` "QuestDraft".
 */
export interface QuestDraft {
  title: string;
  notes?: string | null;
  /**
   * Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "PersonaSlug".
   */
  persona: string;
  /**
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "Cadence".
   */
  cadence: "daily" | "weekly" | "monthly";
  /**
   * Quest / record category. Non-general values match the email extractors.
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "Category".
   */
  category:
    | "general"
    | "ics"
    | "utilities"
    | "government"
    | "health"
    | "delivery"
    | "subscription"
    | "jobs"
    | "learning"
    | "personal"
    | "travel";
  estimate_min: number;
  scheduled_for?: string | null;
  deadline?: string | null;
  priority: number;
  parent_id?: string | null;
}
/**
 * This interface was referenced by `QuestDiff`'s JSON-Schema
 * via the `definition` "UpdateOp".
 */
export interface UpdateOp {
  op: "update";
  quest_id: string;
  changes: QuestChanges;
  reason: string;
}
/**
 * This interface was referenced by `QuestDiff`'s JSON-Schema
 * via the `definition` "QuestChanges".
 */
export interface QuestChanges {
  title?: string;
  notes?: string | null;
  /**
   * Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "PersonaSlug".
   */
  persona?: string;
  estimate_min?: number;
  scheduled_for?: string | null;
  deadline?: string | null;
  priority?: number;
}
/**
 * This interface was referenced by `QuestDiff`'s JSON-Schema
 * via the `definition` "DropOp".
 */
export interface DropOp {
  op: "drop";
  quest_id: string;
  reason: string;
}
/**
 * This interface was referenced by `DailyPlan`'s JSON-Schema
 * via the `definition` "QuestLines".
 */
export interface QuestLines {
  /**
   * An existing quest id, or new:N for the N-th add op (0-based) in diff.ops.
   */
  quest: string;
  /**
   * Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "PersonaSlug".
   */
  persona: string;
  /**
   * @maxItems 60
   */
  lines: FallbackLine[];
}
/**
 * This interface was referenced by `FallbackLines`'s JSON-Schema
 * via the `definition` "FallbackLine".
 */
export interface FallbackLine {
  trigger:
    | "assigned"
    | "reminder_am"
    | "reminder_mid"
    | "reminder_pm"
    | "started"
    | "completed_early"
    | "completed_on_time"
    | "completed_late"
    | "partial"
    | "snoozed"
    | "deferred"
    | "skipped"
    | "forgotten"
    | "overdue_1d"
    | "overdue_3d"
    | "overdue_7d"
    | "carried_over"
    | "abandoned"
    | "all_done"
    | "half_by_noon"
    | "nothing_by_15"
    | "over_capacity";
  variant: number;
  /**
   * Mood bucket; mood itself is computed in code from completion rate.
   */
  condition: "any" | "pleased" | "neutral" | "concerned";
  /**
   * May contain runtime placeholders {time_left} {streak} {days_carried} {actual_vs_estimate} {next_quest}.
   */
  text: string;
}
/**
 * This interface was referenced by `DailyPlan`'s JSON-Schema
 * via the `definition` "BoardLine".
 */
export interface BoardLine {
  /**
   * Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "PersonaSlug".
   */
  persona: string;
  trigger: "all_done" | "half_by_noon" | "nothing_by_15" | "over_capacity";
  variant: number;
  condition: "any" | "pleased" | "neutral" | "concerned";
  text: string;
}
/**
 * Output of a deterministic email extractor. Money and dates enter the system only through this record.
 */
export interface ExtractedRecord {
  /**
   * Quest / record category. Non-general values match the email extractors.
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "Category".
   */
  category:
    | "general"
    | "ics"
    | "utilities"
    | "government"
    | "health"
    | "delivery"
    | "subscription"
    | "jobs"
    | "learning"
    | "personal"
    | "travel";
  /**
   * `completion` = receipt / delivered / confirmed signal that auto-resolves by reference_token.
   */
  kind: "obligation" | "completion";
  /**
   * Pseudonym token issued by the local vault, e.g. PERSON_7, ORG_3, AMOUNT_2.
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "Token".
   */
  entity_token: string;
  /**
   * AMOUNT_n token. The value and currency live only in the local vault; the PC UI re-hydrates it.
   */
  amount?: string | null;
  due_at?: string | null;
  event_at?: string | null;
  /**
   * Sanitized location text or token.
   */
  location?: string | null;
  /**
   * @maxItems 10
   */
  instructions:
    | []
    | [string]
    | [string, string]
    | [string, string, string]
    | [string, string, string, string]
    | [string, string, string, string, string]
    | [string, string, string, string, string, string]
    | [string, string, string, string, string, string, string]
    | [string, string, string, string, string, string, string, string]
    | [string, string, string, string, string, string, string, string, string]
    | [string, string, string, string, string, string, string, string, string, string];
  reference_token?: string | null;
  confidence: number;
}
/**
 * personas/<slug>/lines.fallback.json: static lines used when the dialogue cache has nothing for a trigger. Every trigger needs at least two lines (checked in tests).
 */
export interface FallbackLines {
  /**
   * @minItems 1
   */
  lines: [FallbackLine, ...FallbackLine[]];
}
/**
 * One attempt of a scheduled LLM job, as stored in `llm_runs`. Idempotent per (job, slot, date).
 */
export interface LLMRun {
  id?: string;
  /**
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "JobName".
   */
  job: "ingest" | "daily_am" | "daily_pm" | "weekly" | "monthly" | "persona_digest";
  /**
   * Only daily jobs have a slot.
   */
  slot?: ("AM" | "PM") | null;
  date: string;
  trigger: "tick" | "start" | "network_up" | "manual";
  provider_used?: ("claude-cli" | "ollama" | "claude-api") | null;
  attempt: number;
  status: "queued" | "running" | "succeeded" | "failed" | "invalid_output" | "skipped";
  tokens?: TokenUsage | null;
  error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}
/**
 * This interface was referenced by `LLMRun`'s JSON-Schema
 * via the `definition` "TokenUsage".
 */
export interface TokenUsage {
  input: number;
  output: number;
}
/**
 * One pre-authored dialogue line, as stored in `persona_lines`. Quest-level lines carry a quest_id; board-level lines do not.
 */
export interface PersonaLine {
  id?: string;
  quest_id?: string | null;
  /**
   * Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "PersonaSlug".
   */
  persona: string;
  trigger:
    | "assigned"
    | "reminder_am"
    | "reminder_mid"
    | "reminder_pm"
    | "started"
    | "completed_early"
    | "completed_on_time"
    | "completed_late"
    | "partial"
    | "snoozed"
    | "deferred"
    | "skipped"
    | "forgotten"
    | "overdue_1d"
    | "overdue_3d"
    | "overdue_7d"
    | "carried_over"
    | "abandoned"
    | "all_done"
    | "half_by_noon"
    | "nothing_by_15"
    | "over_capacity";
  variant: number;
  /**
   * Mood bucket; mood itself is computed in code from completion rate.
   */
  condition: "any" | "pleased" | "neutral" | "concerned";
  /**
   * May contain runtime placeholders {time_left} {streak} {days_carried} {actual_vs_estimate} {next_quest}.
   */
  text: string;
  used_at?: string | null;
}
/**
 * personas/<slug>/persona.yaml. Custom packs cannot change schema, escalation caps or quiet-hour rules (invariant 6).
 */
export interface PersonaPack {
  name: string;
  /**
   * Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "PersonaSlug".
   */
  slug: string;
  accent: string;
  /**
   * Escalation style, 0 = gentle, 3 = drill sergeant. Capped by code.
   */
  intensity: number;
  /**
   * Extra quiet hours for this persona; config quiet hours always apply too.
   */
  quiet_hours?: QuietHours | null;
  /**
   * Categories this persona hands out by default.
   *
   * Items: Quest / record category. Non-general values match the email extractors.
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "Category".
   */
  owns: (
    | "general"
    | "ics"
    | "utilities"
    | "government"
    | "health"
    | "delivery"
    | "subscription"
    | "jobs"
    | "learning"
    | "personal"
    | "travel"
  )[];
  /**
   * Tie-break when several personas own a category; higher wins.
   */
  priority: number;
}
/**
 * A quest as stored in the `quests` table.
 */
export interface Quest {
  id: string;
  title: string;
  notes?: string | null;
  /**
   * Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "PersonaSlug".
   */
  persona: string;
  /**
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "Cadence".
   */
  cadence: "daily" | "weekly" | "monthly";
  /**
   * Quest / record category. Non-general values match the email extractors.
   *
   * This interface was referenced by `Common`'s JSON-Schema
   * via the `definition` "Category".
   */
  category:
    | "general"
    | "ics"
    | "utilities"
    | "government"
    | "health"
    | "delivery"
    | "subscription"
    | "jobs"
    | "learning"
    | "personal"
    | "travel";
  status:
    | "open"
    | "in_progress"
    | "done"
    | "partial"
    | "snoozed"
    | "deferred"
    | "skipped"
    | "forgotten"
    | "overdue"
    | "abandoned";
  estimate_min: number;
  actual_min?: number | null;
  /**
   * Board day (daily), week start (weekly) or month start (monthly).
   */
  scheduled_for?: string | null;
  deadline?: string | null;
  started_at?: string | null;
  /**
   * Set when status becomes done or partial.
   */
  completed_at?: string | null;
  snoozed_until?: string | null;
  /**
   * XP actually earned (after lateness / partial modifiers). Computed in code.
   */
  xp_awarded?: number | null;
  /**
   * Hard-deadline obligations always carry over, ignoring carry caps.
   */
  hard_deadline: boolean;
  /**
   * 1 = highest.
   */
  priority: number;
  xp: number;
  carries: number;
  source: "manual" | "llm" | "llm-proposed" | "extractor" | "calendar" | "voice";
  /**
   * Links an extractor-created quest to its completion signal.
   */
  reference_token?: string | null;
  parent_id?: string | null;
  created_at: string;
  updated_at: string;
}
/**
 * One proposed QuestDiff op waiting for the user (`quest_proposals`). The model never writes quests; accepting applies the op in code.
 */
export interface QuestProposal {
  id: string;
  run_id?: string | null;
  op: "add" | "update" | "drop";
  quest_id?: string | null;
  /**
   * The op exactly as proposed (validated).
   */
  payload: AddOp | UpdateOp | DropOp;
  /**
   * Dialogue for a proposed add; inserted into persona_lines when accepted.
   */
  lines?: FallbackLine[];
  status: "pending" | "accepted" | "rejected" | "superseded";
  decided_at?: string | null;
  created_at: string;
}
/**
 * The runner's heartbeat row (`runner_state`). The status pill reads heartbeat_at.
 */
export interface RunnerState {
  user_id: string;
  heartbeat_at: string | null;
  last_am_success: string | null;
  last_pm_success: string | null;
  /**
   * Last successful ingest; LLM jobs want inputs fresher than 2 h.
   */
  last_ingest_at?: string | null;
  lock_holder?: string | null;
  lock_acquired_at?: string | null;
  /**
   * Last reachability check per provider.
   */
  provider_health: {
    [k: string]: ProviderHealth;
  };
  runner_version?: string | null;
  updated_at?: string;
}
/**
 * This interface was referenced by `RunnerState`'s JSON-Schema
 * via the `definition` "ProviderHealth".
 */
export interface ProviderHealth {
  reachable: boolean;
  checked_at: string;
}
