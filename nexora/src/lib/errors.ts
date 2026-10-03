// =============================================================================
// Centralized, user-safe error handling.
// Never forward raw Postgres/Supabase error messages to the UI — they can
// leak schema details. Log the technical detail server-side (console.error
// reaches the platform's server logs) and return a friendly Arabic message.
// =============================================================================

export class AppError extends Error {
  public readonly userMessage: string;
  public readonly code: string;

  constructor(userMessage: string, code = "APP_ERROR", technicalDetail?: unknown) {
    super(typeof technicalDetail === "string" ? technicalDetail : userMessage);
    this.userMessage = userMessage;
    this.code = code;
    if (technicalDetail) {
      // Server-side only log — never sent to the client.
      // eslint-disable-next-line no-console
      console.error(`[AppError:${code}]`, technicalDetail);
    }
  }
}

const FRIENDLY_MESSAGES: Record<string, string> = {
  "23505": "هذا السجل موجود بالفعل. تحقق من البيانات وحاول مرة أخرى.",
  "23503": "لا يمكن إتمام العملية لوجود بيانات مرتبطة بهذا السجل.",
  "23502": "بعض الحقول المطلوبة غير مكتملة.",
  "23514": "البيانات المدخلة لا تطابق الشروط المسموح بها.",
  "42501": "ليست لديك الصلاحية الكافية لتنفيذ هذا الإجراء.",
  "28000": "يجب تسجيل الدخول لتنفيذ هذا الإجراء.",
  PGRST116: "لم يتم العثور على البيانات المطلوبة.",
};

export function friendlyErrorMessage(error: unknown): string {
  const code = (error as { code?: string } | null)?.code;
  if (code && FRIENDLY_MESSAGES[code]) return FRIENDLY_MESSAGES[code];

  const message = (error as { message?: string } | null)?.message ?? "";
  if (/CANNOT_REMOVE_LAST_OWNER/.test(message)) {
    return "لا يمكن حذف أو تعديل آخر مالك في المؤسسة.";
  }
  if (/NOT_A_MEMBER/.test(message)) {
    return "ليست لديك عضوية فعالة في هذه المؤسسة.";
  }
  if (/AUTH_REQUIRED/.test(message)) {
    return "يجب تسجيل الدخول لتنفيذ هذا الإجراء.";
  }

  return "حدث خطأ أثناء حفظ البيانات. حاول مرة أخرى.";
}

export function logServerError(scope: string, error: unknown) {
  // In production this would forward to a structured logger / monitoring
  // service. For now it writes to the server console only — never exposed
  // to the client bundle or the HTTP response.
  // eslint-disable-next-line no-console
  console.error(`[${scope}]`, error);
}
