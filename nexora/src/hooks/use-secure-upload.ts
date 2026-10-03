"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { validateFile, sanitizeFilename } from "@/lib/storage-config";

interface UploadConfig {
  bucket: string;
  maxSizeBytes: number;
  allowedMimeTypes: string[];
}

export function useSecureUpload(config: UploadConfig) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function upload(file: File, folderPath: string): Promise<{ path: string; filename: string; mimeType: string; size: number } | null> {
    setError(null);
    const validationError = validateFile(file, config);
    if (validationError) {
      setError(validationError);
      return null;
    }

    setUploading(true);
    const supabase = createClient();
    const safeName = sanitizeFilename(file.name);
    const fullPath = `${folderPath}/${safeName}`;

    const { error: uploadError } = await supabase.storage.from(config.bucket).upload(fullPath, file, {
      contentType: file.type,
      upsert: false,
    });

    setUploading(false);

    if (uploadError) {
      setError("تعذّر رفع الملف. حاول مرة أخرى.");
      return null;
    }

    return { path: fullPath, filename: file.name, mimeType: file.type, size: file.size };
  }

  return { upload, uploading, error };
}
