import { useEffect, useState, useCallback } from "react";
import api, { fmtMoney, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Plus, Trash2, Pencil, X, UtensilsCrossed } from "lucide-react";

const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

const empty = { name: "", price: 0, vat_rate: 23, items: [], active: true };

export default function MenusCombos() {
  const [config, setConfig] = useState(null);
  const [combos, setCombos] = useState([]);
  const [products, setProducts] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(empty);
  const [pick, setPick] = useState({ product_id: "", quantity: 1 });

  const m = (v) => fmtMoney(v, config);
  const load = useCallback(async () => {
    const [c, p, cfg] = await Promise.all([api.get("/pos/combos"), api.get("/products"), api.get("/pos/config")]);
    setCombos(c.data); setProducts(p.data); setConfig(cfg.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const pname = (id) => products.find((p) => p.id === id)?.name || id;
  const openNew = () => { setEditing(null); setForm(empty); setPick({ product_id: "", quantity: 1 }); setOpen(true); };
  const openEdit = (c) => { setEditing(c); setForm({ name: c.name, price: c.price, vat_rate: c.vat_rate, items: (c.items || []).map((i) => ({ ...i })), active: c.active !== false }); setPick({ product_id: "", quantity: 1 }); setOpen(true); };

  const addItem = () => { if (!pick.product_id) return; setForm((f) => ({ ...f, items: [...f.items, { product_id: pick.product_id, quantity: Number(pick.quantity) || 1 }] })); setPick({ product_id: "", quantity: 1 }); };
  const rmItem = (i) => setForm((f) => ({ ...f, items: f.items.filter((_, idx) => idx !== i) }));

  const save = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form, price: Number(form.price), vat_rate: Number(form.vat_rate) };
      if (editing) { await api.put(`/pos/combos/${editing.id}`, payload); toast.success("Menu atualizado"); }
      else { await api.post("/pos/combos", payload); toast.success("Menu criado"); }
      setOpen(false); load();
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const del = async (id) => {
    if (!window.confirm("Eliminar este menu/combo?")) return;
    try { await api.delete(`/pos/combos/${id}`); toast.success("Menu eliminado"); load(); }
    catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  return (
    <div>
      <PageHeader title="Menus & Combos" subtitle="Artigos vendáveis na registadora (descontam stock)">
        <button data-testid="btn-add-combo" onClick={openNew} className={btnPrimary}><Plus className="w-4 h-4 inline mr-1" /> Menu / Combo</button>
      </PageHeader>

      <div className="p-4 sm:p-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-1 bg-border">
          {combos.map((c) => (
            <div key={c.id} data-testid={`combo-card-${c.id}`} className="bg-card border border-border p-6 fade-up">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <UtensilsCrossed className="w-5 h-5 text-primary" />
                  <div className="font-display text-xl font-bold tracking-tight">{c.name}</div>
                </div>
                <span className={`text-xs px-2 py-0.5 font-semibold ${c.active !== false ? "bg-primary text-primary-foreground" : "bg-secondary"}`}>{c.active !== false ? "ativo" : "inativo"}</span>
              </div>
              <div className="mono text-sm mb-1">{m(c.price)} <span className="text-muted-foreground text-xs">· IVA {c.vat_rate}%</span></div>
              <div className="flex flex-wrap gap-1 mb-4">
                {(c.items || []).map((it, i) => (
                  <span key={i} className="text-[0.65rem] px-1.5 py-0.5 border border-border label-tech" style={{ letterSpacing: "0.08em" }}>{it.quantity}× {pname(it.product_id)}</span>
                ))}
                {(!c.items || c.items.length === 0) && <span className="text-xs text-muted-foreground">Sem componentes</span>}
              </div>
              <div className="flex gap-2">
                <button data-testid={`btn-edit-combo-${c.id}`} onClick={() => openEdit(c)} className="flex-1 py-1.5 border border-border text-sm hover:bg-secondary transition-colors duration-150 flex items-center justify-center gap-1"><Pencil className="w-3.5 h-3.5" /> Editar</button>
                <button data-testid={`btn-delete-combo-${c.id}`} onClick={() => del(c.id)} className="py-1.5 px-3 border border-border text-destructive hover:bg-destructive/10 transition-colors duration-150"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            </div>
          ))}
          {combos.length === 0 && <div className="bg-card border border-border p-10 text-center text-muted-foreground md:col-span-2 lg:col-span-3">Sem menus/combos. Crie o primeiro acima.</div>}
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="rounded-none max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display tracking-tight">{editing ? "Editar Menu / Combo" : "Novo Menu / Combo"}</DialogTitle></DialogHeader>
          <form onSubmit={save} className="space-y-3">
            <input data-testid="input-combo-name" required placeholder="Nome (ex: Menu do Dia)" className={field} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <div className="grid grid-cols-2 gap-2">
              <div><label className="label-tech block mb-1">Preço €</label><input data-testid="input-combo-price" type="number" step="any" min="0" className={field} value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} /></div>
              <div><label className="label-tech block mb-1">IVA %</label>
                <select data-testid="select-combo-vat" className={field} value={form.vat_rate} onChange={(e) => setForm({ ...form, vat_rate: e.target.value })}>
                  {[23, 13, 6, 0].map((r) => <option key={r} value={r}>{r}%</option>)}
                </select>
              </div>
            </div>
            <div className="border-t border-border pt-2">
              <div className="label-tech mb-1">Componentes (descontam stock)</div>
              {form.items.map((it, i) => (
                <div key={i} className="flex items-center justify-between text-sm py-1">
                  <span>{it.quantity}× {pname(it.product_id)}</span>
                  <button type="button" onClick={() => rmItem(i)} className="text-destructive"><X className="w-3.5 h-3.5" /></button>
                </div>
              ))}
              <div className="flex gap-2 mt-1">
                <select data-testid="combo-product" className={field} value={pick.product_id} onChange={(e) => setPick({ ...pick, product_id: e.target.value })}>
                  <option value="">Produto de stock...</option>
                  {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
                <input type="number" min="0.1" step="any" className={field + " w-24"} value={pick.quantity} onChange={(e) => setPick({ ...pick, quantity: e.target.value })} />
                <button type="button" data-testid="btn-add-combo-item" onClick={addItem} className="px-3 border border-border hover:bg-secondary transition-colors duration-150"><Plus className="w-4 h-4" /></button>
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm border border-border px-2 py-2 cursor-pointer">
              <input data-testid="combo-active" type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} />
              <span>Ativo (aparece na registadora)</span>
            </label>
            <button data-testid="btn-save-combo" className={btnPrimary + " w-full"}>{editing ? "Guardar alterações" : "Criar menu / combo"}</button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
