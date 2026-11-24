import { Bug, Camera, Film, LayoutDashboard, LayoutGrid, Settings, ShieldAlert, Shapes, Zap } from "lucide-react"

export const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/cameras", label: "Cameras", icon: Camera },
  { to: "/live", label: "Live Wall", icon: LayoutGrid },
  { to: "/media", label: "Media", icon: Film },
  { to: "/templates", label: "Templates", icon: Shapes },
  { to: "/events", label: "Events", icon: Zap },
  { to: "/faults", label: "Faults", icon: ShieldAlert },
  { to: "/inspector", label: "Inspector", icon: Bug },
  { to: "/settings", label: "Settings", icon: Settings },
] as const
