import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

const PROTECTED_PREFIXES = ["/dashboard", "/students", "/classes", "/attendance", "/assignments", "/exams", "/payments", "/messages", "/analytics", "/ai", "/notifications", "/settings", "/audit-logs", "/billing", "/onboarding"];
const AUTH_PREFIXES = ["/login", "/register", "/forgot-password", "/reset-password"];

export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        },
      },
    }
  );

  // IMPORTANT: this call refreshes the session token if it's expired. Do not
  // remove it — without it, users get silently logged out mid-session.
  // Wrapped defensively: if Supabase is unreachable (misconfigured env vars,
  // transient outage, DNS failure for a placeholder project URL, etc.) we
  // must not crash every single request with a 500 — fail safe as "no user"
  // so public pages keep working and protected pages just redirect to login
  // instead of showing a raw error.
  let user: { id: string } | null = null;
  try {
    const {
      data: { user: resolvedUser },
    } = await supabase.auth.getUser();
    user = resolvedUser;
  } catch {
    user = null;
  }

  const path = request.nextUrl.pathname;
  const isProtected = PROTECTED_PREFIXES.some((p) => path === p || path.startsWith(p + "/"));
  const isAuthPage = AUTH_PREFIXES.some((p) => path === p || path.startsWith(p + "/"));

  if (!user && isProtected) {
    const redirectUrl = new URL("/login", request.url);
    redirectUrl.searchParams.set("next", path);
    return NextResponse.redirect(redirectUrl);
  }

  if (user && isAuthPage) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return response;
}
