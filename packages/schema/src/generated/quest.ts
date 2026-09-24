/* Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`. */

/**
 * A quest as stored in the `quests` table.
 */
export interface Quest {
  id: string;
  title: string;
  notes?: string | null;
  /**
   * Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).
   */
  persona: string;
  cadence: "daily" | "weekly" | "monthly";
  /**
   * Quest / record category. Non-general values match the email extractors.
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
