import { Check, LogOut, Menu, Moon, MoreHorizontal, PanelLeftClose, PanelLeftOpen, Search } from "lucide-react"
import { Suspense, useState } from "react"
import { NavLink, Outlet, useLocation, useNavigate } from "react-router"
import { useHealth, useMe } from "@/api/queries"
import { Loading } from "@/components/common"
import { CommandPalette } from "@/components/layout/CommandPalette"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useAuth } from "@/lib/auth/useAuth"
import { PRODUCT_LOGO, PRODUCT_NAME } from "@/lib/branding"
import { useLiveStats, useWsState } from "@/lib/realtime"
import { readStored, writeStored } from "@/lib/storage"
import { applyTheme, currentTheme, THEMES, type ThemeId } from "@/lib/theme"
import { cn } from "@/lib/utils"
import { NAV } from "./nav"

const COLLAPSE_KEY = "vcamx.sidebar"

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(() => readStored(COLLAPSE_KEY, { collapsed: false }).collapsed)
  const [mobileMenu, setMobileMenu] = useState(false)
  const [palette, setPalette] = useState(false)
  const location = useLocation()
  const toggle = () =>
    setCollapsed((c) => {
      writeStored(COLLAPSE_KEY, { collapsed: !c })
      return !c
    })
  const primaryMobile = NAV.slice(0, 4)
  const secondaryMobile = NAV.slice(4)

  return (
    <div className="flex h-dvh min-h-0 overflow-hidden">
      <aside className={cn("hidden shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-[width] duration-200 lg:flex", collapsed ? "w-16" : "w-56")}>
        <div className="flex h-14 items-center gap-2 px-4">
          <img src={PRODUCT_LOGO} alt="" className="size-8 shrink-0 object-contain" />
          {!collapsed && <span className="font-semibold tracking-tight">{PRODUCT_NAME}</span>}
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-2">
          {NAV.map(({ to, label, icon: Icon, ...rest }) => {
            const link = (
              <NavLink
                key={to}
                to={to}
                end={"end" in rest}
                className={({ isActive }) =>
                  cn(
                    "flex h-9 items-center gap-3 rounded-md px-3 text-sm transition-colors",
                    isActive ? "bg-sidebar-accent font-medium text-sidebar-primary" : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                    collapsed && "justify-center px-0",
                  )
                }
              >
                <Icon className="size-4.5 shrink-0" />
                {!collapsed && label}
              </NavLink>
            )
            return collapsed ? (
              <Tooltip key={to}>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right">{label}</TooltipContent>
              </Tooltip>
            ) : link
          })}
        </nav>
        <div className="p-2">
          <Button variant="ghost" size="sm" className="w-full justify-center text-muted-foreground" onClick={toggle}>
            {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
            {!collapsed && "Collapse"}
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setMobileMenu(true)} onSearch={() => setPalette(true)} />
        <main className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto p-3 pb-[calc(4.5rem+env(safe-area-inset-bottom))] sm:p-4 lg:p-5 lg:pb-5">
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
        </main>
      </div>

      <nav aria-label="Primary navigation" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-sidebar-border bg-sidebar/95 pb-[env(safe-area-inset-bottom)] text-sidebar-foreground backdrop-blur lg:hidden">
        {primaryMobile.map(({ to, label, icon: Icon, ...rest }) => (
          <NavLink key={to} to={to} end={"end" in rest} className={({ isActive }) => cn("flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 text-[10px]", isActive ? "text-sidebar-primary" : "text-sidebar-foreground/75")}>
            <Icon className="size-5" />
            <span>{label}</span>
          </NavLink>
        ))}
        <button type="button" onClick={() => setMobileMenu(true)} className={cn("flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 text-[10px]", secondaryMobile.some((i) => location.pathname.startsWith(i.to)) ? "text-sidebar-primary" : "text-sidebar-foreground/75")}>
          <MoreHorizontal className="size-5" />
          <span>More</span>
        </button>
      </nav>

      <Sheet open={mobileMenu} onOpenChange={setMobileMenu}>
        <SheetContent side="left" className="w-[min(88vw,22rem)] overflow-y-auto p-0 lg:hidden">
          <SheetHeader className="border-b">
            <SheetTitle className="flex items-center gap-2">
              <img src={PRODUCT_LOGO} alt="" className="size-9 shrink-0 object-contain" />
              {PRODUCT_NAME}
            </SheetTitle>
            <SheetDescription>Virtual camera farm</SheetDescription>
          </SheetHeader>
          <nav className="space-y-1 p-3">
            {NAV.map(({ to, label, icon: Icon, ...rest }) => (
              <NavLink key={to} to={to} end={"end" in rest} onClick={() => setMobileMenu(false)} className={({ isActive }) => cn("flex min-h-12 items-center gap-3 rounded-lg px-3 text-sm", isActive ? "bg-accent font-medium text-primary" : "text-foreground/85")}>
                <Icon className="size-5" /> {label}
              </NavLink>
            ))}
          </nav>
        </SheetContent>
      </Sheet>

      <CommandPalette open={palette} onOpenChange={setPalette} />
    </div>
  )
}

function Pill({ ok, label, title, warn }: { ok: boolean; label: string; title?: string; warn?: boolean }) {
  return (
    <span title={title} className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs">
      <span className={cn("size-2 rounded-full", ok ? "bg-success" : warn ? "animate-pulse bg-warning" : "animate-pulse bg-danger")} />
      {label}
    </span>
  )
}

function Topbar({ onMenu, onSearch }: { onMenu: () => void; onSearch: () => void }) {
  const health = useHealth()
  const ws = useWsState()
  const { farm } = useLiveStats()
  const serverOk = health.isSuccess
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b bg-card/40 px-3 text-sm sm:px-4 lg:gap-4 lg:px-5">
      <Button variant="ghost" size="icon" className="-ml-1 size-10 lg:hidden" onClick={onMenu} aria-label="Open navigation">
        <Menu className="size-5" />
      </Button>
      <div className="flex min-w-0 items-center gap-2 lg:hidden">
        <img src={PRODUCT_LOGO} alt="" className="size-8 shrink-0 object-contain" />
        <span className="truncate font-semibold">{PRODUCT_NAME}</span>
      </div>
      <Button variant="outline" className="hidden h-8 w-64 justify-start gap-2 text-muted-foreground md:flex" onClick={onSearch}>
        <Search className="size-4" /> Search cameras, pages…
        <kbd className="ml-auto rounded border px-1.5 font-mono text-[10px]">Ctrl K</kbd>
      </Button>
      <div className="ml-auto flex items-center gap-2">
        {farm && (
          <span className="hidden text-muted-foreground xl:inline">
            <span className="font-medium text-foreground">{farm.running}</span>/{farm.cameras} running · {farm.rtsp_clients} RTSP clients
          </span>
        )}
        <span className="hidden sm:inline-flex">
          <Pill ok={ws === "open"} warn={ws === "connecting"} label={ws === "open" ? "Live" : ws === "connecting" ? "Reconnecting…" : "Offline"} title="Live updates (WebSocket)" />
        </span>
        <Pill ok={serverOk} label={serverOk ? `Server ${health.data.host_ip}` : health.isLoading ? "Connecting…" : "Server unreachable"} />
        <UserMenu />
      </div>
    </header>
  )
}

function UserMenu() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [theme, setTheme] = useState<ThemeId>(currentTheme)
  const me = useMe()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-9 gap-2 px-1.5" aria-label="Account">
          <span className="grid size-7 place-items-center rounded-full bg-primary/15 text-xs font-semibold text-primary">{(me.data?.username ?? "?").slice(0, 2).toUpperCase()}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal text-muted-foreground">Signed in as {me.data?.username ?? "…"}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuSub>
          <DropdownMenuSubTrigger><Moon className="size-4" /> Theme</DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            {THEMES.map((t) => (
              <DropdownMenuItem key={t.id} onSelect={() => { applyTheme(t.id); setTheme(t.id) }}>
                <Check className={cn("size-4", theme !== t.id && "invisible")} /> {t.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuItem onSelect={() => navigate("/settings")}>Settings</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={logout}><LogOut className="size-4" /> Sign out</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
