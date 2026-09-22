import { ScrollText, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  key: string;
  label: string;
  href: string;
  icon: LucideIcon;
}

export const NAV: NavItem[] = [
  { key: "accounts", label: "Accounts", href: "/admin", icon: Users },
  { key: "audit", label: "Audit log", href: "/admin/audit", icon: ScrollText },
];

export function navForPath(pathname: string): NavItem | undefined {
  if (pathname.startsWith("/admin/accounts/")) return NAV[0];
  return NAV.find((n) => (n.href === "/admin" ? pathname === "/admin" : pathname.startsWith(n.href)));
}
