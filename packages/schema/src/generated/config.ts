/* Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`. */

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
     */
    providers: ["claude-cli" | "ollama" | "claude-api", ...("claude-cli" | "ollama" | "claude-api")[]];
    /**
     * Per-job provider order override, keyed by job name.
     */
    per_job?: {
      /**
       * @minItems 1
       */
      [k: string]: ["claude-cli" | "ollama" | "claude-api", ...("claude-cli" | "ollama" | "claude-api")[]];
    };
  };
  /**
   * Items: Persona pack slug (coach, teacher, mom, quartermaster, or a custom pack).
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
export interface Goal {
  id: string;
  title: string;
  horizon: "week" | "month" | "quarter" | "year";
  persona?: string | null;
}
export interface QuietHours {
  /**
   * Wall-clock time HH:MM in the configured timezone.
   */
  start: string;
  /**
   * Wall-clock time HH:MM in the configured timezone.
   */
  end: string;
}
