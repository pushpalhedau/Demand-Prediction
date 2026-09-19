"use client";

import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, type ReactNode } from "react";
import { FilterToolbar } from "@/components/filters/filter-toolbar";
import { ErrorState } from "@/components/data/states";
import { Breadcrumb, BreadcrumbItem, BreadcrumbList, BreadcrumbPage } from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { ApiError } from "@/lib/api";
import { navForPath } from "@/lib/nav";
import { useMe, usePresentation } from "@/lib/session";
import { AppSidebar } from "./app-sidebar";
import { ModeToggle } from "./mode-toggle";

/** Authenticated frame: navigation, page context, global filters. Redirects to sign-in when there is no session. */
export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { t } = usePresentation();
  const { data: me, error, isPending } = useMe();

  const unauthenticated = error instanceof ApiError && error.status === 401;
  useEffect(() => {
    if (unauthenticated) router.replace("/login");
  }, [unauthenticated, router]);

  if (isPending || unauthenticated) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (error || !me) {
    return (
      <div className="mx-auto max-w-lg p-8">
        <ErrorState message={t("app.load_failed")} />
      </div>
    );
  }
  if (!me.ready) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-3 p-8">
        <h1 className="text-xl font-semibold">{t("app.setup.title")}</h1>
        <p className="text-muted-foreground text-sm leading-relaxed">{t("app.setup.body")}</p>
      </main>
    );
  }

  const current = navForPath(pathname);
  return (
    <SidebarProvider>
      <AppSidebar me={me} />
      <SidebarInset>
        <header className="bg-background/90 sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b px-4 backdrop-blur">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mx-1 h-4" />
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem className="text-muted-foreground hidden sm:block">{me.organisation.name}</BreadcrumbItem>
              <BreadcrumbItem>
                <BreadcrumbPage>{current ? t(current.key) : ""}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
          <div className="ml-auto">
            <ModeToggle />
          </div>
        </header>
        <div className="bg-background sticky top-14 z-10 border-b px-4 py-2.5 md:px-6">
          <Suspense fallback={<Skeleton className="h-9 w-full max-w-3xl" />}>
            <FilterToolbar regionLabel={me.organisation.region_label} dataRange={me.data_range} />
          </Suspense>
        </div>
        <main className="mx-auto w-full max-w-[1500px] flex-1 space-y-6 p-4 md:p-6">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
