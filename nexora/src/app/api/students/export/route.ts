import { NextResponse } from "next/server";
import { requireRole, ADMIN_ROLES } from "@/lib/auth/session";
import { logServerError } from "@/lib/errors";

function csvEscape(value: unknown): string {
  const str = value === null || value === undefined ? "" : String(value);
  if (/[",\n]/.test(str)) return `"${str.replace(/"/g, '""')}"`;
  return str;
}

// Streams students as CSV, fetched server-side in bounded chunks (RLS still
// applies — this can never return another organization's rows, even if the
// request is crafted by hand).
export async function GET() {
  let ctx;
  try {
    ctx = await requireRole(ADMIN_ROLES);
  } catch (error) {
    logServerError("students.export.auth", error);
    return NextResponse.json({ error: "غير مصرح" }, { status: 403 });
  }

  const { supabase, organization } = ctx;
  const headerRow = ["كود الطالب", "الاسم الكامل", "البريد الإلكتروني", "الهاتف", "الفصل", "الحالة", "تاريخ الإضافة"].join(",") + "\n";

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder();
      controller.enqueue(encoder.encode("\uFEFF" + headerRow));

      const chunkSize = 500;
      let from = 0;
      for (;;) {
        const { data, error } = await supabase
          .from("students")
          .select("student_code, full_name, email, phone, status, created_at, class:classes(name)")
          .eq("organization_id", organization.id)
          .is("deleted_at", null)
          .order("created_at", { ascending: true })
          .range(from, from + chunkSize - 1);

        if (error || !data || data.length === 0) break;

        const rows = data
          .map((s) => {
            const className = (s as unknown as { class?: { name?: string } }).class?.name ?? "";
            return [s.student_code, s.full_name, s.email, s.phone, className, s.status, s.created_at]
              .map(csvEscape)
              .join(",");
          })
          .join("\n");
        controller.enqueue(encoder.encode(rows + "\n"));

        if (data.length < chunkSize) break;
        from += chunkSize;
      }

      await supabase.rpc("log_audit_event", {
        p_org_id: organization.id,
        p_action: "student.exported",
        p_entity_type: "student",
        p_metadata: {},
      });

      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="nexora-students-${Date.now()}.csv"`,
    },
  });
}
