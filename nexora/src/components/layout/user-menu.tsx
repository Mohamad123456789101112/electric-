"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import Link from "next/link";
import { LogOut, Settings, ShieldCheck, User } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar } from "@/components/ui/avatar";
import { useOrg } from "@/components/providers/org-provider";
import { ROLE_LABELS_AR } from "@/lib/auth/roles";
import { logoutAction } from "@/app/auth/actions";

export function UserMenu() {
  const { profile, user, role } = useOrg();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const name = profile?.full_name || user.email || "مستخدم";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-2 rounded-full transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent" aria-label="قائمة الحساب">
          <Avatar name={name} src={profile?.avatar_url} size="sm" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel>
          <p className="truncate text-sm font-semibold text-ink">{name}</p>
          <p className="truncate text-xs font-normal text-ink-muted">{user.email}</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <div className="px-2.5 py-1">
          <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">{ROLE_LABELS_AR[role]}</span>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/settings">
            <User className="h-3.5 w-3.5" />
            الملف الشخصي
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/settings/security">
            <ShieldCheck className="h-3.5 w-3.5" />
            الأمان
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/settings/organization">
            <Settings className="h-3.5 w-3.5" />
            إعدادات المؤسسة
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          disabled={isPending}
          onSelect={() =>
            startTransition(async () => {
              await logoutAction();
              router.replace("/login");
              router.refresh();
            })
          }
          className="text-danger focus:bg-danger-soft"
        >
          <LogOut className="h-3.5 w-3.5" />
          تسجيل الخروج
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
