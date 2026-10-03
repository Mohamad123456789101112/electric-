import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

// =============================================================================
// Server-side Supabase client (Server Components, Server Actions, Route
// Handlers). Still uses the PUBLIC anon key only — authorization comes from
// the user's session (forwarded via cookies) plus RLS, never from elevated
// privileges. This client can only ever do what the signed-in user is allowed
// to do.
// =============================================================================
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => {
              cookieStore.set(name, value, options);
            });
          } catch {
            // Called from a Server Component without a mutable response —
            // middleware will refresh the session cookie on the next request.
          }
        },
      },
    }
  );
}
