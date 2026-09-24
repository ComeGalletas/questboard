/* Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`. */

/**
 * One attempt of a scheduled LLM job, as stored in `llm_runs`. Idempotent per (job, slot, date).
 */
export interface LLMRun {
  id?: string;
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
export interface TokenUsage {
  input: number;
  output: number;
}
