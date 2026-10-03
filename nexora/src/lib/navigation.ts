import type { OrgRole } from "@/types/database";
import {
  LayoutDashboard,
  Users,
  GraduationCap,
  CalendarCheck,
  ClipboardList,
  FileSpreadsheet,
  Wallet,
  MessageSquare,
  BarChart3,
  Sparkles,
  Bell,
  Settings,
  ShieldCheck,
  CreditCard,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  roles?: OrgRole[]; // undefined = all roles
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "لوحة التحكم", icon: LayoutDashboard },
  { href: "/students", label: "الطلاب", icon: Users, roles: ["owner", "admin", "teacher", "accountant"] },
  { href: "/classes", label: "الفصول", icon: GraduationCap },
  { href: "/attendance", label: "الحضور", icon: CalendarCheck, roles: ["owner", "admin", "teacher"] },
  { href: "/assignments", label: "الواجبات", icon: ClipboardList },
  { href: "/exams", label: "الاختبارات والدرجات", icon: FileSpreadsheet },
  { href: "/payments", label: "المدفوعات", icon: Wallet, roles: ["owner", "admin", "accountant", "student", "parent"] },
  { href: "/messages", label: "الرسائل", icon: MessageSquare },
  { href: "/analytics", label: "التحليلات", icon: BarChart3, roles: ["owner", "admin", "teacher"] },
  { href: "/ai", label: "مساعد NEXORA الذكي", icon: Sparkles, roles: ["owner", "admin", "teacher"] },
  { href: "/notifications", label: "الإشعارات", icon: Bell },
];

export const BOTTOM_NAV_ITEMS: NavItem[] = [
  { href: "/settings", label: "الإعدادات", icon: Settings },
  { href: "/audit-logs", label: "سجل التدقيق", icon: ShieldCheck, roles: ["owner", "admin"] },
  { href: "/billing", label: "الاشتراك", icon: CreditCard, roles: ["owner"] },
];

export function visibleNav(items: NavItem[], role: OrgRole): NavItem[] {
  return items.filter((item) => !item.roles || item.roles.includes(role));
}

// Compact set for the mobile bottom tab bar.
export const MOBILE_PRIMARY_HREFS = ["/dashboard", "/students", "/classes", "/assignments", "/messages"];
