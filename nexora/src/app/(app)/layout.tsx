import { requireActiveOrg } from "@/lib/auth/session";
import { OrgProvider } from "@/components/providers/org-provider";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { MobileNav } from "@/components/layout/mobile-nav";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const ctx = await requireActiveOrg();

  return (
    <OrgProvider
      value={{
        user: ctx.user,
        profile: ctx.profile,
        organization: ctx.organization,
        membership: ctx.membership,
        memberships: ctx.memberships,
        role: ctx.membership.role,
      }}
    >
      <div className="flex min-h-screen bg-surface">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar />
          <main className="flex-1 pb-20 lg:pb-0">
            <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 sm:py-8">{children}</div>
          </main>
        </div>
        <MobileNav />
      </div>
    </OrgProvider>
  );
}
