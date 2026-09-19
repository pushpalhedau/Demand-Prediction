"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ChevronsUpDown, Languages, LogOut } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { LANGUAGES } from "@/lib/i18n";
import { NAV } from "@/lib/nav";
import { usePresentation } from "@/lib/session";
import type { Lang, Me } from "@/lib/types";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
}

export function AppSidebar({ me }: { me: Me }) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t, lang, setLang } = usePresentation();
  const { isMobile, setOpenMobile } = useSidebar();
  const available = new Set(me.tabs);

  async function signOut() {
    await api("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    queryClient.clear();
    router.replace("/login");
  }

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="h-14 justify-center border-b px-4 group-data-[collapsible=icon]:px-2">
        <Link href="/" className="flex items-center" aria-label="PredictaX">
          <Image src="/logo.png" alt="PredictaX" width={132} height={33} priority className="h-auto w-[132px] group-data-[collapsible=icon]:hidden" />
          <span className="bg-primary text-primary-foreground hidden size-8 items-center justify-center rounded-md text-sm font-bold group-data-[collapsible=icon]:flex">
            P
          </span>
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{t("app.navigation")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV.filter((item) => available.has(item.key)).map((item) => {
                const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
                return (
                  <SidebarMenuItem key={item.key}>
                    <SidebarMenuButton asChild isActive={active} tooltip={t(item.key)}>
                      <Link href={item.href} onClick={() => isMobile && setOpenMobile(false)}>
                        <item.icon />
                        <span>{t(item.key)}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t">
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent">
                  <Avatar className="size-8 rounded-md">
                    <AvatarFallback className="bg-primary/10 text-primary rounded-md text-xs font-semibold">
                      {initials(me.organisation.name)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-medium">{me.organisation.name}</span>
                    <span className="text-muted-foreground truncate text-xs">{me.user.email}</span>
                  </div>
                  <ChevronsUpDown className="text-muted-foreground ml-auto size-4" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent side={isMobile ? "bottom" : "right"} align="end" className="w-60">
                <DropdownMenuLabel className="font-normal">
                  <p className="text-sm font-medium">{me.organisation.name}</p>
                  <p className="text-muted-foreground text-xs">{me.user.email}</p>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuLabel className="text-muted-foreground flex items-center gap-2 text-xs font-normal">
                  <Languages className="size-3.5" /> {t("app.language")}
                </DropdownMenuLabel>
                <DropdownMenuRadioGroup value={lang} onValueChange={(v) => setLang(v as Lang)}>
                  {Object.entries(LANGUAGES).map(([code, name]) => (
                    <DropdownMenuRadioItem key={code} value={code}>
                      {name}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={signOut}>
                  <LogOut /> {t("app.sign_out")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
