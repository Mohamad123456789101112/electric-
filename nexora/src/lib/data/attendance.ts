import "server-only";
import type { createClient } from "@/lib/supabase/server";
import type { OrgRole } from "@/types/database";

type SupabaseServer = Awaited<ReturnType<typeof createClient>>;

export async function listClassesForAttendance(supabase: SupabaseServer, orgId: string, role: OrgRole, userId: string) {
  let query = supabase.from("classes").select("id, name, subject").eq("organization_id", orgId).is("deleted_at", null).order("name");

  if (role === "teacher") query = query.eq("teacher_id", userId);

  const { data, error } = await query;
  if (error) throw error;
  return data ?? [];
}
