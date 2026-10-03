"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { NAV_ITEMS, BOTTOM_NAV_ITEMS, visibleNav } from "@/lib/navigation";
import { useOrg } from "@/components/providers/org-provider";
import { OrgSwitcher } from "./org-switcher";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();
  const { role } = useOrg();
  const [collapsed, setCollapsed] = useState(false);

  const mainItems = visibleNav(NAV_ITEMS, role);
  const bottomItems = visibleNav(BOTTOM_NAV_ITEMS, role);

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 76 : 264 }}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      className="sticky top-0 hidden h-screen shrink-0 flex-col border-l border-border bg-paper lg:flex"
    >
      <div className="flex h-16 items-center gap-2 border-b border-border px-3">
        {!collapsed && (
          <Link href="/dashboard" className="flex items-center gap-2 px-1 text-base font-bold text-ink">
            <span className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-sm)] bg-ink text-sm text-white">N</span>
            NEXORA
          </Link>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className={cn("flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] text-ink-muted transition-colors hover:bg-surface", collapsed && "mx-auto")}
          aria-label={collapsed ? "توسيع الشريط الجانبي" : "طي الشريط الجانبي"}
        >
          {collapsed ? <PanelRightOpen className="h-4 w-4" /> : <PanelRightClose className="h-4 w-4" />}
        </button>
      </div>

      <div className="p-3">
        <OrgSwitcher collapsed={collapsed} />
      </div>

      <nav className="flex-1 overflow-y-auto scrollbar-thin px-3 py-1" aria-label="التنقل الرئيسي">
        <ul className="space-y-0.5">
          {mainItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "group relative flex items-center gap-3 rounded-[var(--radius-md)] px-3 py-2.5 text-sm font-medium transition-colors",
                    active ? "bg-accent-soft text-accent" : "text-ink-soft hover:bg-surface hover:text-ink"
                  )}
                >
                  <item.icon className="h-[18px] w-[18px] shrink-0" />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                  {active && <span className="absolute inset-y-1.5 start-0 w-0.5 rounded-full bg-accent" />}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-border px-3 py-3">
        <ul className="space-y-0.5">
          {bottomItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-[var(--radius-md)] px-3 py-2.5 text-sm font-medium transition-colors",
                    active ? "bg-accent-soft text-accent" : "text-ink-soft hover:bg-surface hover:text-ink"
                  )}
                >
                  <item.icon className="h-[18px] w-[18px] shrink-0" />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </motion.aside>
  );
}
