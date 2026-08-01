import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { MapPin, LogIn, LogOut, CheckCircle2, XCircle } from "lucide-react";

function fmtDuration(s) {
  if (!s) return "—";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
}

export default function Picagem() {
  const { user } = useAuth();
  const showAll = !!user && (user.role === "admin" || (user.role === "gestor" && (user.permissions || []).includes("picagem")));
  const [status, setStatus] = useState(null);
  const [settings, setSettings] = useState(null);
  const [entries, setEntries] = useState([]);
  const [locating, setLocating] = useState(false);
  const [geoState, setGeoState] = useState("idle"); // idle | ok | error

  const load = useCallback(() => {
    api.get("/timeclock/status").then((r) => setStatus(r.data));
    api.get("/timeclock/entries").then((r) => setEntries(r.data));
    api.get("/settings").then((r) => setSettings(r.data));
  }, []);
  useEffect(() => { load(); }, [load]);

  const punch = () => {
    setLocating(true);
    setGeoState("idle");
    if (!navigator.geolocation) {
      toast.error("Geolocalização não suportada");
      setLocating(false);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const { data } = await api.post("/timeclock/punch", { lat: pos.coords.latitude, lng: pos.coords.longitude });
          setGeoState("ok");
          toast.success(data.action === "entrada" ? "Entrada registada ✓" : "Saída registada ✓");
          load();
        } catch (err) {
          setGeoState("error");
          toast.error(formatApiError(err.response?.data?.detail));
        } finally {
          setLocating(false);
        }
      },
      () => {
        setGeoState("error");
        toast.error("Não foi possível obter a localização");
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const clockedIn = status?.clocked_in;

  const renderCenterIcon = () => {
    if (geoState === "ok") return <CheckCircle2 className="w-16 h-16 text-primary" />;
    if (geoState === "error") return <XCircle className="w-16 h-16 text-destructive" />;
    return <MapPin className={`w-14 h-14 ${clockedIn ? "text-destructive" : "text-primary"}`} />;
  };

  return (
    <div>
      <PageHeader title="Picagem de Ponto" subtitle="Validação por geolocalização" />
      <div className="p-4 sm:p-8 grid grid-cols-1 lg:grid-cols-2 gap-1 bg-border">
        <div className="bg-card border border-border p-8 flex flex-col items-center justify-center">
          {!settings?.lat ? (
            <div className="text-center text-muted-foreground">
              <MapPin className="w-10 h-10 mx-auto mb-3" />
              Localização do restaurante ainda não configurada.<br />Peça a um gestor para definir em <b>Definições</b>.
            </div>
          ) : (
            <>
              <div className="relative w-52 h-52 mb-8">
                <div className="absolute inset-0 rounded-full border-2 border-primary/30" />
                <div className={`absolute inset-0 rounded-full border-2 ${clockedIn ? "border-destructive/40" : "border-primary/40"} ${locating ? "pulse-ring" : ""}`} />
                <div className="absolute inset-8 rounded-full border border-border" />
                {locating && (
                  <div className="absolute inset-0 rounded-full overflow-hidden radar-sweep"
                    style={{ background: "conic-gradient(from 0deg, transparent 0deg, hsl(var(--primary)/0.35) 60deg, transparent 90deg)" }} />
                )}
                <div className="absolute inset-0 flex items-center justify-center">
                  {renderCenterIcon()}
                </div>
              </div>

              <div className="label-tech mb-1">Estado atual</div>
              <div data-testid="clock-status" className="font-display text-3xl font-bold tracking-tighter mb-6">
                {clockedIn ? "EM SERVIÇO" : "FORA DE SERVIÇO"}
              </div>

              <button
                data-testid="btn-punch"
                onClick={punch}
                disabled={locating}
                className={`w-full max-w-xs py-4 font-semibold text-sm flex items-center justify-center gap-2 hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150 disabled:opacity-60 ${clockedIn ? "bg-destructive text-destructive-foreground" : "bg-primary text-primary-foreground"}`}
              >
                {clockedIn ? <LogOut className="w-4 h-4" /> : <LogIn className="w-4 h-4" />}
                {locating ? "A validar localização..." : clockedIn ? "Picar Saída" : "Picar Entrada"}
              </button>
              <p className="text-xs text-muted-foreground mt-4 mono">
                Raio permitido: {settings.radius_m}m · {settings.restaurant_name}
              </p>
            </>
          )}
        </div>

        <div className="bg-card border border-border p-6">
          <div className="label-tech mb-4">{showAll ? "Histórico de picagens (todos)" : "As minhas picagens"}</div>
          <div className="space-y-2 max-h-[420px] overflow-y-auto">
            {entries.map((e) => (
              <div key={e.id} data-testid={`entry-${e.id}`} className="flex items-center justify-between p-3 border border-border">
                <div>
                  {showAll && <div className="text-sm font-medium">{e.user_name}</div>}
                  <div className="mono text-xs text-muted-foreground">
                    {new Date(e.clock_in).toLocaleString("pt-PT")}
                  </div>
                </div>
                <div className="text-right">
                  <span className={`text-xs px-2 py-0.5 font-semibold ${e.clock_out ? "bg-secondary" : "bg-primary text-primary-foreground"}`}>
                    {e.clock_out ? fmtDuration(e.duration_seconds) : "ativo"}
                  </span>
                </div>
              </div>
            ))}
            {entries.length === 0 && <p className="text-sm text-muted-foreground">Sem registos.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
