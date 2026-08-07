import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Pencil, Trash2 } from "lucide-react";

const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

const REASON = { out_of_radius: "auto — fora da área", no_signal: "auto — sem sinal", manual: "manual", correction: "correção" };

function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}
function fmtDur(s) { if (!s) return "—"; const h = Math.floor(s / 3600); const m = Math.floor((s % 3600) / 60); return `${h}h ${m}m`; }

export default function CorrecaoTab() {
  const { user } = useAuth();
  const canDelete = !!user?.is_system;
  const [entries, setEntries] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ clock_in: "", clock_out: "" });

  const load = useCallback(() => api.get("/timeclock/entries").then((r) => setEntries(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const openEdit = (e) => { setEditing(e); setForm({ clock_in: toLocalInput(e.clock_in), clock_out: toLocalInput(e.clock_out) }); setOpen(true); };

  const save = async () => {
    try {
      const payload = { clock_in: form.clock_in || undefined, clock_out: form.clock_out || undefined };
      await api.put(`/timeclock/entries/${editing.id}`, payload);
      toast.success("Picagem atualizada");
      setOpen(false); load();
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const remove = async (id) => {
    if (!window.confirm("Eliminar esta picagem? Ação irreversível.")) return;
    try { await api.delete(`/timeclock/entries/${id}`); toast.success("Picagem eliminada"); load(); }
    catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  return (
    <div className="p-4 sm:p-8">
      <div className="bg-card border border-border overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border label-tech text-left">
              <th className="px-4 py-3">Funcionário</th>
              <th className="px-4 py-3">Entrada</th>
              <th className="px-4 py-3">Saída</th>
              <th className="px-4 py-3 text-right">Duração</th>
              <th className="px-4 py-3">Motivo</th>
              <th className="px-4 py-3 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} data-testid={`corr-row-${e.id}`} className="border-b border-border">
                <td className="px-4 py-3 font-medium">{e.user_name}</td>
                <td className="px-4 py-3 mono text-xs">{new Date(e.clock_in).toLocaleString("pt-PT")}</td>
                <td className="px-4 py-3 mono text-xs">{e.clock_out ? new Date(e.clock_out).toLocaleString("pt-PT") : <span className="text-primary font-semibold">ativo</span>}</td>
                <td className="px-4 py-3 text-right mono">{e.clock_out ? fmtDur(e.duration_seconds) : "—"}</td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{e.clock_out ? (REASON[e.checkout_reason] || "—") : "—"}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-2 justify-end">
                    <button data-testid={`btn-edit-entry-${e.id}`} onClick={() => openEdit(e)} className="py-1.5 px-3 border border-border hover:bg-secondary transition-colors duration-150 flex items-center gap-1"><Pencil className="w-3.5 h-3.5" /> {e.clock_out ? "Editar" : "Fechar"}</button>
                    {canDelete && (
                      <button data-testid={`btn-delete-entry-${e.id}`} onClick={() => remove(e.id)} className="py-1.5 px-3 border border-border text-destructive hover:bg-destructive/10 transition-colors duration-150"><Trash2 className="w-3.5 h-3.5" /></button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {entries.length === 0 && <tr><td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">Sem registos.</td></tr>}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="rounded-none">
          <DialogHeader><DialogTitle className="font-display tracking-tight">{editing?.clock_out ? "Editar picagem" : "Fechar picagem"} — {editing?.user_name}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><label className="label-tech">Entrada</label><input data-testid="corr-clock-in" type="datetime-local" className={field} value={form.clock_in} onChange={(e) => setForm({ ...form, clock_in: e.target.value })} /></div>
            <div><label className="label-tech">Saída {editing && !editing.clock_out ? "(deixe vazio para manter aberto)" : ""}</label><input data-testid="corr-clock-out" type="datetime-local" className={field} value={form.clock_out} onChange={(e) => setForm({ ...form, clock_out: e.target.value })} /></div>
            <button data-testid="btn-save-entry" onClick={save} className={btnPrimary + " w-full"}>Guardar</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
