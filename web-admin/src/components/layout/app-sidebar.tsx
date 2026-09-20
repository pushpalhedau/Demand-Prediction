"use client";

import { useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { api } from "@/lib/api";
import { NAV, navForPath } from "@/lib/nav";
import type { Operator } from "@/lib/session";

export function AppSidebar({ operator }: { operator: Operator }) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isMobile, setOpenMobile } = useSidebar();
  const current = navForPath(pathname);

  async function signOut() {
    await api("/api/admin/auth/logout", { method: "POST" }).catch(() => undefined);
    queryClient.clear();
    router.replace("/login");
  }

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="h-14 justify-center border-b px-4 group-data-[collapsible=icon]:px-2">
        <Link href="/" className="flex items-center" aria-label="PredictaX Admin">
          <Image src="/logo.png" alt="PredictaX" width={132} height={33} priority className="h-auto w-[132px] group-data-[collapsible=icon]:hidden" />
          <span className="bg-primary text-primary-foreground hidden size-8 items-center justify-center rounded-md text-sm font-bold group-data-[collapsible=icon]:flex">
            P
          </span>
        </Link>
        <p className="text-muted-foreground group-data-[collapsible=icon]:hidden text-xs">Admin console</p>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Sections</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV.map((item) => (
                <SidebarMenuItem key={item.key}>
                  <SidebarMenuButton asChild isActive={current?.key === item.key} tooltip={item.label}>
                    <Link href={item.href} onClick={() => isMobile && setOpenMobile(false)}>
                      <item.icon />
                      <span>{item.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" onClick={signOut} tooltip="Sign out">
              <Avatar className="size-8 rounded-md">
                <AvatarFallback className="bg-primary/10 text-primary rounded-md text-xs font-semibold">
                  {operator.email.slice(0, 2).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">{operator.email}</span>
                <span className="text-muted-foreground truncate text-xs">Operator</span>
              </div>
              <LogOut className="text-muted-foreground ml-auto size-4" />
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
