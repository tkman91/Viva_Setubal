import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { MapPin, LogIn, LogOut, CheckCircle2, XCircle, Wifi } from "lucide-react";

function fmtDuration(s) {
  if (!s) return "—";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
}

const REASON_LABEL = {
  out_of_radius: "saída automática — saiu da área",
  no_signal: "saída automática — sem sinal",
  correction: "correção (gestor)",
  manual: "saída manual",
};

export default function PunchPanel() {
  const { user } = useAuth();
  const showAll = !!user && (user.is_admin || (user.is_supervisor && (user.permissions || []).includes("picagem")));
  const [status, setStatus] = useState(null);
  const [settings, setSettings] = useState(null);
  const [entries, setEntries] = useState([]);
  const [locating, setLocating] = useState(false);
  const [geoState, setGeoState] = useState("idle"); // idle | ok | error
  const [tracking, setTracking] = useState(false);

  const load = useCallback(() => {
    api.get("/timeclock/status").then((r) => setStatus(r.data));
    api.get("/timeclock/entries").then((r) => setEntries(r.data));
    api.get("/settings").then((r) => setSettings(r.data));
  }, []);
  useEffect(() => { load(); }, [load]);

  const clockedIn = status?.clocked_in;

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

  // Seguimento contínuo enquanto em serviço → fecho automático ao sair do raio.
  useEffect(() => {
    if (!clockedIn || !navigator.geolocation) { setTracking(false); return; }
    setTracking(true);
    let lastPos = null;
    let stopped = false;

    const sendBeat = async (lat, lng) => {
      try {
        const { data } = await api.post("/timeclock/heartbeat", { lat, lng });
        if (data.clocked_in === false) {
          stopped = true;
          const msg = data.reason === "out_of_radius"
            ? "Saída automática — saiu da área do restaurante"
            : "Sessão de ponto terminada";
          toast.warning(msg);
          load();
        }
      } catch (e) { /* ignora falhas transitórias */ }
    };

    const watchId = navigator.geolocation.watchPosition(
      (pos) => { lastPos = { lat: pos.coords.latitude, lng: pos.coords.longitude }; },
      () => { /* sem sinal — servidor fecha por no_signal após tolerância */ },
      { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 }
    );

    const tick = async () => {
      if (stopped) return;
      if (lastPos) {
        await sendBeat(lastPos.lat, lastPos.lng);
      } else {
        try {
          const { data } = await api.get("/timeclock/status");
          if (!data.clocked_in) { stopped = true; toast.warning("Saída automática registada (sem sinal)"); load(); }
        } catch (e) { /* ignora */ }
      }
    };

    const kick = setTimeout(tick, 3000);
    const interval = setInterval(tick, 45000);

    return () => {
      navigator.geolocation.clearWatch(watchId);
      clearTimeout(kick);
      clearInterval(interval);
      setTracking(false);
    };
  }, [clockedIn, load]);

  const renderCenterIcon = () => {
    if (geoState === "ok") return <CheckCircle2 className="w-16 h-16 text-primary" />;
    if (geoState === "error") return <XCircle className="w-16 h-16 text-destructive" />;
    return <MapPin className={`w-14 h-14 ${clockedIn ? "text-destructive" : "text-primary"}`} />;
  };

  return (
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
              <div className={`absolute inset-0 rounded-full border-2 ${clockedIn ? "border-destructive/40" : "border-primary/40"} ${(locating || tracking) ? "pulse-ring" : ""}`} />
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
            {clockedIn && tracking && (
              <div data-testid="geofence-tracking" className="flex items-center gap-1.5 text-xs text-primary mt-4">
                <Wifi className="w-3.5 h-3.5" /> A monitorizar localização — sai automaticamente ao deixar a área
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-3 mono">
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
                {e.clock_out && (
                  <div className="mono text-[0.65rem] text-muted-foreground mt-0.5">
                    {e.auto_checkout ? "⚠ " : ""}{REASON_LABEL[e.checkout_reason] || (e.auto_checkout ? "saída automática" : "saída")}
                  </div>
                )}
              </div>
              <div className="text-right flex flex-col items-end gap-1">
                <span className={`text-xs px-2 py-0.5 font-semibold ${e.clock_out ? "bg-secondary" : "bg-primary text-primary-foreground"}`}>
                  {e.clock_out ? fmtDuration(e.duration_seconds) : "ativo"}
                </span>
                {e.auto_checkout && (
                  <span data-testid={`auto-badge-${e.id}`} className="text-[0.6rem] px-1.5 py-0.5 bg-accent/20 text-accent-foreground label-tech" style={{ letterSpacing: "0.08em" }}>auto</span>
                )}
              </div>
            </div>
          ))}
          {entries.length === 0 && <p className="text-sm text-muted-foreground">Sem registos.</p>}
        </div>
      </div>
    </div>
  );
}
