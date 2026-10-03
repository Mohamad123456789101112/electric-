// Pure, client-safe role constants/labels. Deliberately has NO "server-only"
// and NO next/headers import so client components (e.g. UserMenu) can use
// role labels/groups without pulling the server-side session module (which
// depends on cookies()/server-only) into the browser bundle.
import type { OrgRole } from "@/types/database";

export const ROLE_LABELS_AR: Record<OrgRole, string> = {
  owner: "مالك",
  admin: "مشرف",
  teacher: "معلم",
  accountant: "محاسب",
  student: "طالب",
  parent: "ولي أمر",
};

export const ADMIN_ROLES: OrgRole[] = ["owner", "admin"];
export const STAFF_ROLES: OrgRole[] = ["owner", "admin", "teacher"];
export const FINANCE_ROLES: OrgRole[] = ["owner", "admin", "accountant"];
