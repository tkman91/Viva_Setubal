import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Pencil, CalendarClock } from "lucide-react";

const DAYS = [
  { k: "mon", l: "Seg" }, { k: "tue", l: "Ter" }, { k: "wed", l: "Qua" },
  { k: "thu", l: "Qui" }, { k: "fri", l: "Sex" }, { k: "sat", l: "Sáb" }, { k: "sun", l: "Dom" },
];
const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

const emptyShifts = () => DAYS.reduce((a, d) => ({ ...a, [d.k]: { start: "", end: "", off: false } }), {});

const STATUS = {
  presente: { label: "Presente", cls: "bg-primary/15 text-primary" },
  atraso: { label: "Atraso", cls: "bg-yellow-500/20 text-yellow-700 dark:text-yellow-400" },
  falta: { label: "Falta", cls: "bg-destructive/15 text-destructive" },
};

export default function HorarioTab() {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyShifts());
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [compliance, setCompliance] = useState([]);

  const load = useCallback(() => api.get("/schedules").then((r) => setRows(r.data)), []);
  const loadCompliance = useCallback((d) => api.get(`/schedules/compliance?date=${d}`).then((r) => setCompliance(r.data.items)).catch(() => setCompliance([])), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadCompliance(date); }, [date, loadCompliance]);

  const openEdit = (row) => {
    setEditing(row);
    const base = emptyShifts();
    Object.entries(row.shifts || {}).forEach(([k, v]) => { if (base[k]) base[k] = { start: v.start || "", end: v.end || "", off: !!v.off }; });
    setForm(base);
    setOpen(true);
  };

  const save = async () => {
    try {
      const shifts = {};
      DAYS.forEach((d) => {
        const s = form[d.k];
        if (s.off) shifts[d.k] = { off: true };
        else if (s.start) shifts[d.k] = { start: s.start, end: s.end || "", off: false };
      });
      await api.put(`/schedules/${editing.user_id}`, { shifts });
      toast.success("Horário guardado");
      setOpen(false);
      load(); loadCompliance(date);
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const cellText = (s) => (s?.off ? "Folga" : (s?.start ? `${s.start}–${s.end || "?"}` : "—"));

  return (
    <div className="p-4 sm:p-8 space-y-1">
      <div className="bg-card border border-border p-6 mb-1">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div className="label-tech flex items-center gap-2"><CalendarClock className="w-4 h-4" /> Cumprimento do dia</div>
          <input data-testid="compliance-date" type="date" className={field + " max-w-[180px]"} value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div className="flex flex-wrap gap-2">
          {compliance.map((c) => {
            const st = STATUS[c.status] || STATUS.presente;
            return (
              <div key={c.user_id} data-testid={`compliance-${c.user_id}`} className="border border-border px-3 py-2 min-w-[170px]">
                <div className="text-sm font-medium">{c.user_name}</div>
                <div className="mono text-xs text-muted-foreground">{c.scheduled_start}{c.scheduled_end ? `–${c.scheduled_end}` : ""} · entrou {c.actual_in || "—"}</div>
                <span className={`inline-block mt-1 text-[0.65rem] px-1.5 py-0.5 label-tech ${st.cls}`}>{st.label}{c.status === "atraso" && c.late_minutes != null ? ` +${c.late_minutes}m` : ""}</span>
              </div>
            );
          })}
          {compliance.length === 0 && <p className="text-sm text-muted-foreground">Sem turnos definidos para este dia.</p>}
        </div>
      </div>

      <div className="bg-card border border-border overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border label-tech text-left">
              <th className="px-4 py-3">Funcionário</th>
              {DAYS.map((d) => <th key={d.k} className="px-3 py-3 text-center">{d.l}</th>)}
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.user_id} data-testid={`sched-row-${row.user_id}`} className="border-b border-border">
                <td className="px-4 py-3 font-medium">{row.user_name}</td>
                {DAYS.map((d) => {
                  const s = row.shifts?.[d.k];
                  return <td key={d.k} className={`px-3 py-3 text-center mono text-xs ${s?.off ? "text-muted-foreground" : ""}`}>{cellText(s)}</td>;
                })}
                <td className="px-4 py-3 text-right">
                  <button data-testid={`btn-edit-sched-${row.user_id}`} onClick={() => openEdit(row)} className="py-1.5 px-3 border border-border text-sm hover:bg-secondary transition-colors duration-150 flex items-center gap-1 ml-auto"><Pencil className="w-3.5 h-3.5" /> Editar</button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={9} className="px-4 py-10 text-center text-muted-foreground">Sem funcionários.</td></tr>}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="rounded-none max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display tracking-tight">Horário — {editing?.user_name}</DialogTitle></DialogHeader>
          <div className="space-y-2">
            {DAYS.map((d) => {
              const s = form[d.k];
              return (
                <div key={d.k} className="grid grid-cols-[3rem_1fr_1fr_auto] items-center gap-2 border border-border px-2 py-1.5">
                  <span className="font-semibold text-sm">{d.l}</span>
                  <input data-testid={`sched-${d.k}-start`} type="time" disabled={s.off} className={field + (s.off ? " opacity-40" : "")} value={s.start} onChange={(e) => setForm({ ...form, [d.k]: { ...s, start: e.target.value } })} />
                  <input data-testid={`sched-${d.k}-end`} type="time" disabled={s.off} className={field + (s.off ? " opacity-40" : "")} value={s.end} onChange={(e) => setForm({ ...form, [d.k]: { ...s, end: e.target.value } })} />
                  <label className="flex items-center gap-1 text-xs whitespace-nowrap">
                    <input data-testid={`sched-${d.k}-off`} type="checkbox" checked={s.off} onChange={(e) => setForm({ ...form, [d.k]: { ...s, off: e.target.checked } })} /> Folga
                  </label>
                </div>
              );
            })}
            <button data-testid="btn-save-sched" onClick={save} className={btnPrimary + " w-full mt-2"}>Guardar horário</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
