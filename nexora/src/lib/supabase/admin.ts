import "server-only";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";

// =============================================================================
// PRIVILEGED, SERVER-ONLY client. Uses the service role key and therefore
// bypasses Row Level Security entirely.
//
// The `server-only` import above makes it a build error to ever import this
// file from a Client Component or any code bundled into the browser.
//
// Use this ONLY for operations that are legitimately impossible under RLS,
// e.g. looking up a user by email during an invite flow, or admin-level
// auth management (listing/revoking sessions). Every call site using this
// client MUST perform its own explicit authorization check first — this
// client trusts nothing by default.
// =============================================================================
let cached: ReturnType<typeof createSupabaseClient> | null = null;

export function createAdminClient() {
  if (cached) return cached;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !serviceKey) {
    throw new Error(
      "SUPABASE_SERVICE_ROLE_KEY is not configured. Server-side privileged operations are unavailable until it is set in your environment (never expose it to the client)."
    );
  }

  cached = createSupabaseClient(url, serviceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  return cached;
}
