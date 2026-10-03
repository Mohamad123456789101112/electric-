// Mirrors the bucket configuration created in
// supabase/migrations/0007_storage.sql. Client-side checks here are a UX
// convenience only — the real enforcement lives in the storage bucket's
// file_size_limit/allowed_mime_types and the RLS policies on storage.objects.

export const ASSIGNMENT_FILE_CONFIG = {
  bucket: "assignment-files",
  maxSizeBytes: 25 * 1024 * 1024,
  allowedMimeTypes: [
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
  ],
};

export const SUBMISSION_FILE_CONFIG = {
  bucket: "submission-files",
  maxSizeBytes: 25 * 1024 * 1024,
  allowedMimeTypes: [
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/zip",
    "text/plain",
  ],
};

export const AVATAR_FILE_CONFIG = {
  bucket: "avatars",
  maxSizeBytes: 5 * 1024 * 1024,
  allowedMimeTypes: ["image/png", "image/jpeg", "image/webp"],
};

export function validateFile(file: File, config: { maxSizeBytes: number; allowedMimeTypes: string[] }): string | null {
  if (file.size > config.maxSizeBytes) {
    return `حجم الملف يتجاوز الحد المسموح به (${Math.round(config.maxSizeBytes / 1024 / 1024)}MB).`;
  }
  if (!config.allowedMimeTypes.includes(file.type)) {
    return "نوع الملف غير مسموح به.";
  }
  return null;
}

export function sanitizeFilename(name: string): string {
  const ext = name.includes(".") ? name.slice(name.lastIndexOf(".")) : "";
  const base = name
    .slice(0, name.length - ext.length)
    .replace(/[^a-zA-Z0-9\u0600-\u06FF_-]/g, "_")
    .slice(0, 80);
  return `${Date.now()}-${base || "file"}${ext.slice(0, 10)}`;
}
