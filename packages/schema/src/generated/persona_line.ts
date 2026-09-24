/* Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`. */

/**
 * One pre-authored dialogue line, as stored in `persona_lines`. Quest-level lines carry a quest_id; board-level lines do not.
 */
export interface PersonaLine {
  id?: string;
  quest_id?: string | null;
  /**
   * Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).
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
