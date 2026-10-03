import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

// Handles Supabase's PKCE email links: email confirmation, password recovery,
// and (if enabled later) OAuth/magic-link sign-in. Exchanges the one-time
// `code` for a real session cookie, then redirects onward.
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/dashboard";

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  return NextResponse.redirect(`${origin}/login?error=link_expired`);
}
