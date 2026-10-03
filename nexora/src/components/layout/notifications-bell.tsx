"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { useOrg } from "@/components/providers/org-provider";
import { cn } from "@/lib/utils";

export function NotificationsBell() {
  const { user, organization } = useOrg();
  const [unread, setUnread] = useState<number | null>(null);

  useEffect(() => {
    const supabase = createClient();
    let active = true;

    async function loadCount() {
      const { count } = await supabase
        .from("notifications")
        .select("id", { count: "exact", head: true })
        .eq("user_id", user.id)
        .is("read_at", null);
      if (active) setUnread(count ?? 0);
    }

    loadCount();

    const channel = supabase
      .channel(`notifications:${organization.id}:${user.id}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "notifications", filter: `user_id=eq.${user.id}` },
        () => loadCount()
      )
      .subscribe();

    return () => {
      active = false;
      supabase.removeChannel(channel);
    };
  }, [user.id, organization.id]);

  return (
    <Link
      href="/notifications"
      className="relative flex h-9 w-9 items-center justify-center rounded-full text-ink-soft transition-colors hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      aria-label={unread ? `الإشعارات، ${unread} غير مقروءة` : "الإشعارات"}
    >
      <Bell className="h-[18px] w-[18px]" />
      {!!unread && (
        <span
          className={cn(
            "absolute -top-0.5 -end-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-bold text-white"
          )}
        >
          {unread > 9 ? "9+" : unread}
        </span>
      )}
    </Link>
  );
}
