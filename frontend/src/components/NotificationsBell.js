import { useEffect, useState, useRef, useCallback } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Bell } from "lucide-react";

export default function NotificationsBell() {
  const { canManage } = useAuth();
  const allowed = canManage("picagem");
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const ref = useRef(null);

  const load = useCallback(() => {
    api.get("/notifications").then((r) => { setItems(r.data.items || []); setUnread(r.data.unread || 0); }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!allowed) return;
    load();
    const i = setInterval(load, 60000);
    return () => clearInterval(i);
  }, [allowed, load]);

  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  if (!allowed) return null;

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && unread > 0) { try { await api.post("/notifications/read"); setUnread(0); } catch (e) { /* ignore */ } }
  };

  return (
    <div className="relative" ref={ref}>
      <button data-testid="btn-notifications" onClick={toggle} className="relative p-2 text-muted-foreground hover:text-foreground transition-colors duration-150" aria-label="Avisos">
        <Bell className="w-5 h-5" />
        {unread > 0 && (
          <span data-testid="notif-unread" className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 text-[0.6rem] font-bold bg-destructive text-destructive-foreground rounded-full flex items-center justify-center">{unread}</span>
        )}
      </button>
      {open && (
        <div data-testid="notif-dropdown" className="absolute right-0 mt-2 w-80 max-h-96 overflow-y-auto bg-card border border-border shadow-lg z-50">
          <div className="label-tech px-4 py-3 border-b border-border">Avisos de picagem</div>
          {items.length === 0 && <p className="text-sm text-muted-foreground px-4 py-6">Sem avisos.</p>}
          {items.map((n) => (
            <div key={n.id} data-testid={`notif-${n.id}`} className={`px-4 py-3 border-b border-border ${!n.read ? "bg-secondary/40" : ""}`}>
              <div className="flex items-center gap-2 mb-0.5">
                <span className={`text-[0.6rem] px-1.5 py-0.5 label-tech ${n.type === "falta" ? "bg-destructive/15 text-destructive" : "bg-yellow-500/20 text-yellow-700 dark:text-yellow-400"}`}>{n.type}</span>
                <span className="text-sm font-medium">{n.user_name}</span>
              </div>
              <div className="text-xs text-muted-foreground">{n.message}</div>
              <div className="mono text-[0.6rem] text-muted-foreground mt-0.5">{new Date(n.created_at).toLocaleString("pt-PT")}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
