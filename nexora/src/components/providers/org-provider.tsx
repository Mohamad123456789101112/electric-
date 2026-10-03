"use client";

import { createContext, useContext } from "react";
import type { Organization, OrganizationMember, Profile, OrgRole } from "@/types/database";

export interface OrgContextValue {
  user: { id: string; email: string | null };
  profile: Profile | null;
  organization: Organization;
  membership: OrganizationMember;
  memberships: Array<OrganizationMember & { organization: Organization }>;
  role: OrgRole;
}

const OrgContext = createContext<OrgContextValue | null>(null);

export function OrgProvider({ value, children }: { value: OrgContextValue; children: React.ReactNode }) {
  return <OrgContext.Provider value={value}>{children}</OrgContext.Provider>;
}

export function useOrg(): OrgContextValue {
  const ctx = useContext(OrgContext);
  if (!ctx) throw new Error("useOrg must be used within OrgProvider");
  return ctx;
}

export function useHasRole(roles: OrgRole[]): boolean {
  const { role } = useOrg();
  return roles.includes(role);
}
