"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

export function FileDownloadLink({ bucket, path, label }: { bucket: string; path: string; label: string }) {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    setLoading(true);
    try {
      const res = await fetch(`/api/files/sign?bucket=${encodeURIComponent(bucket)}&path=${encodeURIComponent(path)}`);
      const json = await res.json();
      if (!res.ok || !json.url) {
        toast.error(json.error ?? "تعذّر فتح الملف");
        return;
      }
      window.open(json.url, "_blank", "noopener,noreferrer");
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className="inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline disabled:opacity-60"
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
      {label}
    </button>
  );
}
