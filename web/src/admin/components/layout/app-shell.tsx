"use client";

import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { toast } from "sonner";
import { ErrorState } from "@/admin/components/data/states";
import { Breadcrumb, BreadcrumbItem, BreadcrumbList, BreadcrumbPage } from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { api, ApiError } from "@/admin/lib/api";
import { useIdleLogout } from "@/admin/lib/idle";
import { navForPath } from "@/admin/lib/nav";
import { useMe } from "@/admin/lib/session";
import { AppSidebar } from "./app-sidebar";
import { ModeToggle } from "./mode-toggle";

/** Authenticated frame: navigation and page context. Redirects to sign-in when there is no session. */
export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { data: operator, error, isPending } = useMe();

  const unauthenticated = error instanceof ApiError && error.status === 401;
  useEffect(() => {
    if (unauthenticated) router.replace("/login");
  }, [unauthenticated, router]);

  useIdleLogout(() => {
    api("/api/admin/auth/logout", { method: "POST" }).finally(() => {
      queryClient.clear();
      toast.message("Signed out after 30 minutes of inactivity.");
      router.replace("/login");
    });
  });

  if (isPending || unauthenticated) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (error || !operator) {
    return (
      <div className="mx-auto max-w-lg p-8">
        <ErrorState message="Could not load the console. Please refresh." />
      </div>
    );
  }

  const current = navForPath(pathname);
  return (
    <SidebarProvider>
      <AppSidebar operator={operator} />
      <SidebarInset className="min-w-0">
        <header className="bg-background/90 sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b px-4 backdrop-blur">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mx-1 h-4" />
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbPage>{current?.label ?? "Admin console"}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
          <div className="ml-auto">
            <ModeToggle />
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1200px] min-w-0 flex-1 space-y-8 p-4 md:p-6">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
