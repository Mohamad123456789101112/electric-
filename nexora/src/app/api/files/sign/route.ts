import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { logServerError } from "@/lib/errors";

const ALLOWED_BUCKETS = new Set(["assignment-files", "submission-files", "avatars", "org-logos"]);

// Generates a short-lived signed URL for a PRIVATE storage object. Relies
// entirely on the storage RLS policies (0007_storage.sql) to decide whether
// the current session is allowed to read this exact object — this route
// does not grant any access itself, it just proxies the signed-URL call
// using the caller's own session (never the service role).
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const bucket = searchParams.get("bucket");
  const path = searchParams.get("path");

  if (!bucket || !path || !ALLOWED_BUCKETS.has(bucket)) {
    return NextResponse.json({ error: "طلب غير صالح" }, { status: 400 });
  }

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "غير مصرح" }, { status: 401 });

  const { data, error } = await supabase.storage.from(bucket).createSignedUrl(path, 60);

  if (error || !data) {
    logServerError("files.sign", error);
    return NextResponse.json({ error: "تعذّر الوصول إلى هذا الملف" }, { status: 403 });
  }

  return NextResponse.json({ url: data.signedUrl });
}
