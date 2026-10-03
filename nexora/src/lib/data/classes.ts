import "server-only";
import type { createClient } from "@/lib/supabase/server";
import type { ClassRow } from "@/types/database";

type SupabaseServer = Awaited<ReturnType<typeof createClient>>;

async function attachTeachers(supabase: SupabaseServer, classes: ClassRow[]): Promise<ClassRow[]> {
  const teacherIds = Array.from(new Set(classes.map((c) => c.teacher_id).filter(Boolean))) as string[];
  if (teacherIds.length === 0) return classes;

  const { data: profiles } = await supabase.from("profiles").select("id, full_name, avatar_url").in("id", teacherIds);
  const byId = new Map((profiles ?? []).map((p) => [p.id, p]));

  return classes.map((c) => ({ ...c, teacher: c.teacher_id ? byId.get(c.teacher_id) ?? null : null }));
}

export async function listClasses(supabase: SupabaseServer, orgId: string) {
  const { data, error } = await supabase
    .from("classes")
    .select("*, class_members(count)")
    .eq("organization_id", orgId)
    .is("deleted_at", null)
    .order("created_at", { ascending: false });

  if (error) throw error;

  const classes = (data ?? []).map((c) => ({
    ...c,
    student_count: Array.isArray((c as { class_members?: Array<{ count: number }> }).class_members)
      ? (c as unknown as { class_members: Array<{ count: number }> }).class_members[0]?.count ?? 0
      : 0,
  })) as ClassRow[];

  return attachTeachers(supabase, classes);
}

export async function getClassById(supabase: SupabaseServer, orgId: string, classId: string) {
  const { data, error } = await supabase
    .from("classes")
    .select("*")
    .eq("organization_id", orgId)
    .eq("id", classId)
    .maybeSingle();
  if (error) throw error;
  if (!data) return null;

  const [withTeacher] = await attachTeachers(supabase, [data as ClassRow]);
  return withTeacher;
}

export async function listClassRoster(supabase: SupabaseServer, classId: string) {
  const { data, error } = await supabase
    .from("class_members")
    .select("id, student:students(id, full_name, student_code, status)")
    .eq("class_id", classId);
  if (error) throw error;
  return data ?? [];
}

export async function listStudentsNotInClass(supabase: SupabaseServer, orgId: string, classId: string) {
  const { data: roster } = await supabase.from("class_members").select("student_id").eq("class_id", classId);
  const excludedIds = (roster ?? []).map((r) => r.student_id);

  let query = supabase
    .from("students")
    .select("id, full_name, student_code")
    .eq("organization_id", orgId)
    .is("deleted_at", null)
    .order("full_name")
    .limit(200);

  if (excludedIds.length > 0) query = query.not("id", "in", `(${excludedIds.join(",")})`);

  const { data, error } = await query;
  if (error) throw error;
  return data ?? [];
}

export async function listTeachersForSelect(supabase: SupabaseServer, orgId: string) {
  const { data, error } = await supabase
    .from("organization_members")
    .select("user_id")
    .eq("organization_id", orgId)
    .eq("role", "teacher")
    .eq("status", "active");
  if (error) throw error;

  const ids = (data ?? []).map((m) => m.user_id).filter(Boolean) as string[];
  if (ids.length === 0) return [];

  const { data: profiles } = await supabase.from("profiles").select("id, full_name").in("id", ids);
  return (profiles ?? []).map((p) => ({ id: p.id, name: p.full_name }));
}
