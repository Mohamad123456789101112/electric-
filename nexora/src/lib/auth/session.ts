import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { OrgRole, Organization, OrganizationMember, Profile } from "@/types/database";

export const ACTIVE_ORG_COOKIE = "nexora_active_org";

export interface AppContext {
  supabase: Awaited<ReturnType<typeof createClient>>;
  user: { id: string; email: string | null };
  profile: Profile | null;
  memberships: Array<OrganizationMember & { organization: Organization }>;
  organization: Organization;
  membership: OrganizationMember;
}

/**
 * Returns the signed-in user or null. Never throws. Use in layouts/pages
 * that need to branch on auth state without forcing a redirect.
 */
export async function getOptionalUser() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return { supabase, user };
}

/**
 * Loads every organization the current user actively belongs to.
 */
export async function getUserMemberships(supabase: Awaited<ReturnType<typeof createClient>>, userId: string) {
  const { data, error } = await supabase
    .from("organization_members")
    .select("*, organization:organizations(*)")
    .eq("user_id", userId)
    .eq("status", "active")
    .order("created_at", { ascending: true });

  if (error) throw error;
  return (data ?? []) as Array<OrganizationMember & { organization: Organization }>;
}

/**
 * Enforces: signed in + has at least one active organization. Redirects to
 * /login or /onboarding otherwise. Resolves the "active" organization from a
 * cookie, falling back to the first membership.
 *
 * Every protected server component/page/action should call this (or
 * requireRole below) rather than querying organization_members manually —
 * this is the single choke point for tenant-context resolution.
 */
export async function requireActiveOrg(): Promise<AppContext> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const [memberships, profileRes] = await Promise.all([
    getUserMemberships(supabase, user.id),
    supabase.from("profiles").select("*").eq("id", user.id).maybeSingle(),
  ]);

  if (memberships.length === 0) {
    redirect("/onboarding");
  }

  const cookieStore = await cookies();
  const preferredOrgId = cookieStore.get(ACTIVE_ORG_COOKIE)?.value;
  const active = memberships.find((m) => m.organization_id === preferredOrgId) ?? memberships[0];

  return {
    supabase,
    user: { id: user.id, email: user.email ?? null },
    profile: (profileRes.data as Profile) ?? null,
    memberships,
    organization: active.organization,
    membership: active,
  };
}

/**
 * Same as requireActiveOrg, but additionally enforces the caller's role in
 * the active organization is one of `roles`. Throws a typed error (caught by
 * the nearest error boundary) rather than silently rendering — callers that
 * want a custom 403 page should check membership.role themselves instead.
 */
export async function requireRole(roles: OrgRole[]): Promise<AppContext> {
  const ctx = await requireActiveOrg();
  if (!roles.includes(ctx.membership.role)) {
    redirect("/403");
  }
  return ctx;
}

// Re-exported from roles.ts (a plain, client-safe module) so existing
// server-side imports of these constants from "@/lib/auth/session" keep
// working unchanged. Client components should import from
// "@/lib/auth/roles" directly instead of this file, since this module is
// marked server-only and pulls in next/headers.
export { ROLE_LABELS_AR, ADMIN_ROLES, STAFF_ROLES, FINANCE_ROLES } from "./roles";
