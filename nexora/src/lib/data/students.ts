import "server-only";
import type { createClient } from "@/lib/supabase/server";
import type { Student, StudentStatus } from "@/types/database";

type SupabaseServer = Awaited<ReturnType<typeof createClient>>;

export interface ListStudentsParams {
  orgId: string;
  page: number;
  pageSize: number;
  q?: string;
  status?: StudentStatus | "all";
  classId?: string | "all";
  sort?: "name_asc" | "name_desc" | "created_desc" | "created_asc";
}

export async function listStudents(supabase: SupabaseServer, params: ListStudentsParams) {
  const { orgId, page, pageSize, q, status = "all", classId = "all", sort = "created_desc" } = params;

  let query = supabase
    .from("students")
    .select("*, class:classes(id, name, subject)", { count: "exact" })
    .eq("organization_id", orgId)
    .is("deleted_at", null);

  if (status !== "all") query = query.eq("status", status);
  if (classId !== "all") query = query.eq("class_id", classId);
  if (q && q.trim()) {
    const term = q.trim().replace(/[%_]/g, "");
    query = query.or(`full_name.ilike.%${term}%,student_code.ilike.%${term}%,email.ilike.%${term}%`);
  }

  const [sortCol, sortDir] = (
    {
      name_asc: ["full_name", true],
      name_desc: ["full_name", false],
      created_asc: ["created_at", true],
      created_desc: ["created_at", false],
    } as const
  )[sort];

  const from = (page - 1) * pageSize;
  const to = from + pageSize - 1;

  const { data, error, count } = await query.order(sortCol, { ascending: sortDir }).range(from, to);

  if (error) throw error;

  return { data: (data ?? []) as Student[], count: count ?? 0 };
}

export async function getStudentById(supabase: SupabaseServer, orgId: string, studentId: string) {
  const { data, error } = await supabase
    .from("students")
    .select("*, class:classes(id, name, subject)")
    .eq("organization_id", orgId)
    .eq("id", studentId)
    .maybeSingle();
  if (error) throw error;
  return data as Student | null;
}

export async function listStudentsForSelect(supabase: SupabaseServer, orgId: string) {
  const { data, error } = await supabase
    .from("students")
    .select("id, full_name, student_code")
    .eq("organization_id", orgId)
    .is("deleted_at", null)
    .eq("status", "active")
    .order("full_name");
  if (error) throw error;
  return data ?? [];
}

export async function listClassesForSelect(supabase: SupabaseServer, orgId: string) {
  const { data, error } = await supabase
    .from("classes")
    .select("id, name, subject")
    .eq("organization_id", orgId)
    .is("deleted_at", null)
    .order("name");
  if (error) throw error;
  return data ?? [];
}
