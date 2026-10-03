"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { NAV_ITEMS, BOTTOM_NAV_ITEMS, MOBILE_PRIMARY_HREFS, visibleNav } from "@/lib/navigation";
import { useOrg } from "@/components/providers/org-provider";
import { cn } from "@/lib/utils";

export function MobileNav() {
  const pathname = usePathname();
  const { role } = useOrg();
  const [moreOpen, setMoreOpen] = useState(false);

  const allItems = visibleNav(NAV_ITEMS, role);
  const primary = MOBILE_PRIMARY_HREFS.map((href) => allItems.find((i) => i.href === href)).filter(Boolean) as typeof allItems;
  const rest = [...allItems.filter((i) => !MOBILE_PRIMARY_HREFS.includes(i.href)), ...visibleNav(BOTTOM_NAV_ITEMS, role)];

  return (
    <>
      <nav
        className="fixed inset-x-0 bottom-0 z-40 flex items-stretch justify-around border-t border-border bg-paper/95 backdrop-blur lg:hidden"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        aria-label="التنقل السريع"
      >
        {primary.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn("flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium", active ? "text-accent" : "text-ink-muted")}
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
        <button onClick={() => setMoreOpen(true)} className="flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium text-ink-muted">
          <Menu className="h-5 w-5" />
          المزيد
        </button>
      </nav>

      <AnimatePresence>
        {moreOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 bg-ink/40 lg:hidden"
              onClick={() => setMoreOpen(false)}
            />
            <motion.div
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 300 }}
              className="fixed inset-x-0 bottom-0 z-50 rounded-t-[var(--radius-lg)] border-t border-border bg-paper p-4 pb-8 lg:hidden"
            >
              <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-border-strong" />
              <div className="grid grid-cols-4 gap-3">
                {rest.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMoreOpen(false)}
                    className="flex flex-col items-center gap-1.5 rounded-[var(--radius-md)] p-3 text-center text-[11px] font-medium text-ink-soft hover:bg-surface"
                  >
                    <item.icon className="h-5 w-5 text-ink-muted" />
                    {item.label}
                  </Link>
                ))}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
