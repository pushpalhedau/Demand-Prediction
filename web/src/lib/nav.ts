import {
  BarChart3,
  Boxes,
  LayoutGrid,
  MessageSquareText,
  Store,
  TrendingUp,
  Users,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  key: string;
  href: string;
  icon: LucideIcon;
}

/** Every customer dashboard. The API decides which of these an account's data supports. */
export const NAV: NavItem[] = [
  { key: "tab.overview", href: "/", icon: BarChart3 },
  { key: "tab.forecasting", href: "/forecasting", icon: TrendingUp },
  { key: "tab.comparison", href: "/comparison", icon: LayoutGrid },
  { key: "tab.regional", href: "/regional", icon: Store },
  { key: "tab.customers", href: "/customers", icon: Users },
  { key: "tab.inventory", href: "/inventory", icon: Boxes },
  { key: "tab.sentiment", href: "/sentiment", icon: MessageSquareText },
];

export function navForPath(pathname: string): NavItem | undefined {
  return NAV.find((n) => (n.href === "/" ? pathname === "/" : pathname.startsWith(n.href)));
}
