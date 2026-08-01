import { useEffect, useState, useCallback } from "react";
import api, { fmtMoney, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, X } from "lucide-react";

const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btn = "px-3 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

export default function Modifiers({ config }) {
  const [groups, setGroups] = useState([]);
  const [form, setForm] = useState({ name: "", min: 0, max: 1, required: false, options: [] });
  const [opt, setOpt] = useState({ name: "", price_delta: 0 });

  const load = useCallback(() => api.get("/pos/modifier-groups").then((r) => setGroups(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const addOpt = () => { if (!opt.name) return; setForm((f) => ({ ...f, options: [...f.options, { name: opt.name, price_delta: Number(opt.price_delta) || 0 }] })); setOpt({ name: "", price_delta: 0 }); };
  const rmOpt = (i) => setForm((f) => ({ ...f, options: f.options.filter((_, idx) => idx !== i) }));

  const save = async (e) => {
    e.preventDefault();
    try {
      await api.post("/pos/modifier-groups", { ...form, min: Number(form.min), max: Number(form.max) });
      setForm({ name: "", min: 0, max: 1, required: false, options: [] });
      load(); toast.success("Grupo criado");
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };
  const del = async (id) => { await api.delete(`/pos/modifier-groups/${id}`); load(); };

  return (
    <div className="grid md:grid-cols-2 gap-6">
      <form onSubmit={save} className="border border-border p-4 space-y-3">
        <div className="font-display font-bold tracking-tight">Novo grupo de modificadores</div>
        <input data-testid="input-mod-name" required placeholder="Nome (ex: Extras, Ponto da carne)" className={field} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <div className="grid grid-cols-3 gap-2 items-end">
          <div><label className="label-tech block">Mín.</label><input type="number" min="0" className={field} value={form.min} onChange={(e) => setForm({ ...form, min: e.target.value })} /></div>
          <div><label className="label-tech block">Máx.</label><input type="number" min="1" className={field} value={form.max} onChange={(e) => setForm({ ...form, max: e.target.value })} /></div>
          <label className="flex items-center gap-2 text-sm pb-2"><input type="checkbox" checked={form.required} onChange={(e) => setForm({ ...form, required: e.target.checked })} /> Obrigatório</label>
        </div>
        <div className="border-t border-border pt-2">
          <div className="label-tech mb-1">Opções</div>
          {form.options.map((o, i) => (
            <div key={i} className="flex items-center justify-between text-sm py-1">
              <span>{o.name} <span className="mono text-xs text-muted-foreground">{o.price_delta ? fmtMoney(o.price_delta, config) : ""}</span></span>
              <button type="button" onClick={() => rmOpt(i)} className="text-destructive"><X className="w-3.5 h-3.5" /></button>
            </div>
          ))}
          <div className="flex gap-2 mt-1">
            <input data-testid="input-opt-name" placeholder="Opção" className={field} value={opt.name} onChange={(e) => setOpt({ ...opt, name: e.target.value })} />
            <input placeholder="±€" type="number" step="any" className={field + " w-24"} value={opt.price_delta} onChange={(e) => setOpt({ ...opt, price_delta: e.target.value })} />
            <button type="button" data-testid="btn-add-opt" onClick={addOpt} className="px-3 border border-border"><Plus className="w-4 h-4" /></button>
          </div>
        </div>
        <button data-testid="btn-save-mod" className={btn + " w-full"}>Guardar grupo</button>
      </form>

      <div className="space-y-2">
        {groups.map((g) => (
          <div key={g.id} data-testid={`mod-row-${g.id}`} className="border border-border p-3">
            <div className="flex items-center justify-between">
              <div className="font-semibold">{g.name} <span className="label-tech">máx {g.max}{g.required ? " · obrig." : ""}</span></div>
              <button data-testid={`btn-del-mod-${g.id}`} onClick={() => del(g.id)} className="text-destructive"><Trash2 className="w-4 h-4" /></button>
            </div>
            <div className="text-sm text-muted-foreground mt-1">{g.options.map((o) => o.name).join(", ")}</div>
          </div>
        ))}
        {groups.length === 0 && <p className="text-sm text-muted-foreground">Sem grupos. Depois associa-os a produtos no Stock.</p>}
      </div>
    </div>
  );
}
