import { ScrollText, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  key: string;
  label: string;
  href: string;
  icon: LucideIcon;
}

export const NAV: NavItem[] = [
  { key: "accounts", label: "Accounts", href: "/", icon: Users },
  { key: "audit", label: "Audit log", href: "/audit", icon: ScrollText },
];

export function navForPath(pathname: string): NavItem | undefined {
  if (pathname.startsWith("/accounts/")) return NAV[0];
  return NAV.find((n) => (n.href === "/" ? pathname === "/" : pathname.startsWith(n.href)));
}
