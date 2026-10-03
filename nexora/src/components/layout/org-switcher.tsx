"use client";

import { useTransition } from "react";
import { ChevronsUpDown, Building2, Plus, Check } from "lucide-react";
import Link from "next/link";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useOrg } from "@/components/providers/org-provider";
import { switchOrganizationAction } from "@/app/(app)/layout-actions";
import { cn } from "@/lib/utils";

export function OrgSwitcher({ collapsed }: { collapsed?: boolean }) {
  const { organization, memberships } = useOrg();
  const [isPending, startTransition] = useTransition();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className={cn(
            "flex w-full items-center gap-2.5 rounded-[var(--radius-md)] border border-border bg-paper px-2.5 py-2 text-start transition-colors hover:bg-surface",
            isPending && "opacity-60"
          )}
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-sm)] bg-ink text-sm font-bold text-white">
            {organization.name.slice(0, 1)}
          </div>
          {!collapsed && (
            <>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink">{organization.name}</p>
                <p className="truncate text-[11px] text-ink-muted">{memberships.length > 1 ? `${memberships.length} مؤسسات` : "مؤسسة واحدة"}</p>
              </div>
              <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-ink-muted" />
            </>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel>مؤسساتك</DropdownMenuLabel>
        {memberships.map((m) => (
          <DropdownMenuItem
            key={m.organization_id}
            onSelect={() => startTransition(() => switchOrganizationAction(m.organization_id))}
            className="justify-between"
          >
            <span className="flex items-center gap-2 truncate">
              <Building2 className="h-3.5 w-3.5 shrink-0 text-ink-muted" />
              <span className="truncate">{m.organization.name}</span>
            </span>
            {m.organization_id === organization.id && <Check className="h-3.5 w-3.5 shrink-0 text-accent" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/onboarding">
            <Plus className="h-3.5 w-3.5" />
            إنشاء مؤسسة جديدة
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
