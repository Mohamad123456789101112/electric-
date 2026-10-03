"use client";

import { AlertTriangle, RefreshCcw, WifiOff, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ErrorState({
  title = "حدث خطأ أثناء تحميل البيانات",
  description = "حاول مرة أخرى، وإذا استمرت المشكلة تواصل مع فريق الدعم.",
  onRetry,
  variant = "generic",
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  variant?: "generic" | "network" | "forbidden";
}) {
  const Icon = variant === "network" ? WifiOff : variant === "forbidden" ? ShieldAlert : AlertTriangle;
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center animate-fade-in" role="alert">
      <div className="mb-1 flex h-12 w-12 items-center justify-center rounded-full bg-danger-soft">
        <Icon className="h-5 w-5 text-danger" aria-hidden="true" />
      </div>
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <p className="max-w-sm text-sm text-ink-muted">{description}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="mt-2">
          <RefreshCcw className="h-3.5 w-3.5" />
          إعادة المحاولة
        </Button>
      )}
    </div>
  );
}
