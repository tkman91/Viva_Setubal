import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import {
  LayoutDashboard,
  Package,
  MapPin,
  Users,
  Coffee,
  Receipt,
  BarChart3,
  SlidersHorizontal,
  Settings,
  LogOut,
  UtensilsCrossed,
  Sun,
  Moon,
  Monitor,
} from "lucide-react";

const NAV = [
  { to: "/", label: "Painel", icon: LayoutDashboard, module: null },
  { to: "/picagem", label: "Picagem de Ponto", icon: MapPin, module: "picagem" },
  { to: "/stock", label: "Controlo de Stock", icon: Package, module: "stock" },
  { to: "/consumo", label: "Consumo Staff", icon: Coffee, module: "consumo" },
  { to: "/staff", label: "Gestão de Staff", icon: Users, module: "staff" },
  { to: "/faturacao", label: "Registadora", icon: Receipt, module: "faturacao" },
  { to: "/relatorios", label: "Relatórios", icon: BarChart3, module: "relatorios" },
  { to: "/config-pos", label: "Config POS", icon: SlidersHorizontal, module: "settings" },
  { to: "/definicoes", label: "Definições", icon: Settings, module: "settings" },
];

export default function Layout({ children }) {
  const { user, logout, can, isAdmin } = useAuth();
  const { mode, cycleMode } = useTheme();
  const navigate = useNavigate();

  const themeMeta = {
    system: { icon: Monitor, label: "Sistema" },
    light: { icon: Sun, label: "Claro" },
    dark: { icon: Moon, label: "Escuro" },
  };
  const ThemeIcon = themeMeta[mode].icon;

  const visible = NAV.filter((n) => {
    if (n.module === null) return true;
    if (n.module === "settings") return isAdmin;
    return can(n.module);
  });

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <aside className="w-64 border-r border-border bg-card flex flex-col shrink-0 sticky top-0 h-screen">
        <div className="px-6 py-6 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 bg-primary flex items-center justify-center">
              <UtensilsCrossed className="w-5 h-5 text-primary-foreground" />
            </div>
            <div>
              <div className="font-display font-bold text-lg leading-none tracking-tight">GESTÃO</div>
              <div className="label-tech" style={{ fontSize: "0.6rem" }}>Restaurante</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 py-4 overflow-y-auto">
          {visible.map((n) => {
            const Icon = n.icon;
            return (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                data-testid={`nav-${n.to === "/" ? "painel" : n.to.slice(1)}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-6 py-3 text-sm font-medium transition-colors duration-150 border-l-2 ${
                    isActive
                      ? "border-primary bg-secondary text-foreground"
                      : "border-transparent text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {n.label}
              </NavLink>
            );
          })}
        </nav>
        <div className="border-t border-border p-4">
          <div className="mb-3">
            <div className="text-sm font-semibold truncate">{user?.name}</div>
            <div className="label-tech" style={{ fontSize: "0.6rem" }}>{user?.role}</div>
          </div>
          <button
            data-testid="btn-theme-toggle"
            onClick={cycleMode}
            title="Alternar tema: Sistema → Claro → Escuro"
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors duration-150 mb-3 w-full"
          >
            <ThemeIcon className="w-4 h-4" />
            Tema: {themeMeta[mode].label}
          </button>
          <button
            data-testid="btn-logout"
            onClick={() => {
              logout();
              navigate("/login");
            }}
            className="flex items-center gap-2 text-sm text-destructive hover:opacity-70 transition-opacity duration-150"
          >
            <LogOut className="w-4 h-4" /> Terminar sessão
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0">{children}</main>
    </div>
  );
}

export function PageHeader({ title, subtitle, children }) {
  const now = new Date();
  return (
    <div className="sticky top-0 z-10 backdrop-blur-xl bg-background/80 border-b border-border px-8 py-5 flex items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tighter leading-none">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-4">
        <div className="text-right hidden sm:block">
          <div className="mono text-sm font-medium">{now.toLocaleDateString("pt-PT")}</div>
          <div className="label-tech" style={{ fontSize: "0.6rem" }}>{now.toLocaleDateString("pt-PT", { weekday: "long" })}</div>
        </div>
        {children}
      </div>
    </div>
  );
}
