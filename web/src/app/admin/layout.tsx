import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/admin/components/layout/app-shell";

export const metadata: Metadata = { title: { default: "Admin console", template: "%s · PredictaX Admin" } };

export default function AdminLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
