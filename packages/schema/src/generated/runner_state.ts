/* Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`. */

/**
 * The runner's heartbeat row (`runner_state`). The status pill reads heartbeat_at.
 */
export interface RunnerState {
  user_id: string;
  heartbeat_at: string | null;
  last_am_success: string | null;
  last_pm_success: string | null;
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
export interface ProviderHealth {
  reachable: boolean;
  checked_at: string;
}
