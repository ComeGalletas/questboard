/* Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`. */

/**
 * Output of a deterministic email extractor. Money and dates enter the system only through this record.
 */
export interface ExtractedRecord {
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
  /**
   * `completion` = receipt / delivered / confirmed signal that auto-resolves by reference_token.
   */
  kind: "obligation" | "completion";
  /**
   * Pseudonym token issued by the local vault, e.g. PERSON_7, ORG_3, AMOUNT_2.
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
