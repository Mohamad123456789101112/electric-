"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { Search } from "lucide-react";
import { NAV_ITEMS, BOTTOM_NAV_ITEMS, visibleNav } from "@/lib/navigation";
import { useOrg } from "@/components/providers/org-provider";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { role } = useOrg();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || e.key === "/") {
        if (e.key === "/" && (e.target as HTMLElement)?.tagName === "INPUT") return;
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const items = [...visibleNav(NAV_ITEMS, role), ...visibleNav(BOTTOM_NAV_ITEMS, role)];

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex h-9 w-full max-w-xs items-center gap-2 rounded-[var(--radius-md)] border border-border bg-surface px-3 text-sm text-ink-muted transition-colors hover:border-border-strong"
      >
        <Search className="h-3.5 w-3.5" />
        <span className="flex-1 text-start">بحث سريع...</span>
        <kbd className="rounded border border-border bg-paper px-1.5 py-0.5 text-[10px] font-medium">⌘K</kbd>
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-ink/40 pt-[12vh] backdrop-blur-[2px] animate-fade-in" onClick={() => setOpen(false)}>
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-lg animate-scale-in">
        <Command
          className="overflow-hidden rounded-[var(--radius-lg)] border border-border bg-paper shadow-[var(--shadow-elevation-3)]"
          label="قائمة الأوامر"
        >
          <div className="flex items-center gap-2 border-b border-border px-4">
            <Search className="h-4 w-4 text-ink-muted" />
            <Command.Input
              autoFocus
              placeholder="اكتب للبحث عن صفحة أو إجراء..."
              className="h-12 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted"
            />
          </div>
          <Command.List className="max-h-80 overflow-y-auto p-2 scrollbar-thin">
            <Command.Empty className="px-3 py-8 text-center text-sm text-ink-muted">لا توجد نتائج</Command.Empty>
            <Command.Group heading="التنقل" className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:text-ink-muted">
              {items.map((item) => (
                <Command.Item
                  key={item.href}
                  onSelect={() => {
                    router.push(item.href);
                    setOpen(false);
                  }}
                  className="flex cursor-pointer items-center gap-2.5 rounded-[var(--radius-sm)] px-2.5 py-2.5 text-sm text-ink data-[selected=true]:bg-surface"
                >
                  <item.icon className="h-4 w-4 text-ink-muted" />
                  {item.label}
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
