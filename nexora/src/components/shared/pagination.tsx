"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatNumber } from "@/lib/utils";

export function Pagination({ page, pageSize, total }: { page: number; pageSize: number; total: number }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  function goTo(p: number) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", String(p));
    router.push(`${pathname}?${params.toString()}`);
  }

  if (total === 0) return null;

  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-col items-center justify-between gap-3 border-t border-border px-4 py-3.5 sm:flex-row">
      <p className="text-xs text-ink-muted">
        عرض {formatNumber(from)}–{formatNumber(to)} من أصل {formatNumber(total)}
      </p>
      <div className="flex items-center gap-1.5">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => goTo(page - 1)} aria-label="الصفحة السابقة">
          <ChevronRight className="h-3.5 w-3.5" />
        </Button>
        <span className="px-2 text-xs font-medium text-ink-soft">
          {formatNumber(page)} / {formatNumber(totalPages)}
        </span>
        <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => goTo(page + 1)} aria-label="الصفحة التالية">
          <ChevronLeft className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
