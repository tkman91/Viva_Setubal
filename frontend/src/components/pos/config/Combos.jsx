import { useEffect, useState, useCallback } from "react";
import api, { fmtMoney, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, X } from "lucide-react";

const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btn = "px-3 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

export default function Combos({ config }) {
  const [combos, setCombos] = useState([]);
  const [products, setProducts] = useState([]);
  const [form, setForm] = useState({ name: "", price: 0, vat_rate: 23, items: [] });
  const [pick, setPick] = useState({ product_id: "", quantity: 1 });

  const load = useCallback(async () => {
    const [c, p] = await Promise.all([api.get("/pos/combos"), api.get("/products")]);
    setCombos(c.data); setProducts(p.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const addItem = () => { if (!pick.product_id) return; setForm((f) => ({ ...f, items: [...f.items, { product_id: pick.product_id, quantity: Number(pick.quantity) || 1 }] })); setPick({ product_id: "", quantity: 1 }); };
  const rmItem = (i) => setForm((f) => ({ ...f, items: f.items.filter((_, idx) => idx !== i) }));
  const pname = (id) => products.find((p) => p.id === id)?.name || id;

  const save = async (e) => {
    e.preventDefault();
    try {
      await api.post("/pos/combos", { ...form, price: Number(form.price), vat_rate: Number(form.vat_rate), active: true });
      setForm({ name: "", price: 0, vat_rate: 23, items: [] });
      load(); toast.success("Menu criado");
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };
  const del = async (id) => { await api.delete(`/pos/combos/${id}`); load(); };

  return (
    <div className="grid md:grid-cols-2 gap-6">
      <form onSubmit={save} className="border border-border p-4 space-y-3">
        <div className="font-display font-bold tracking-tight">Novo menu / combo</div>
        <input data-testid="input-combo-name" required placeholder="Nome (ex: Menu do Dia)" className={field} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <div className="grid grid-cols-2 gap-2">
          <div><label className="label-tech block">Preço €</label><input data-testid="input-combo-price" type="number" step="any" className={field} value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} /></div>
          <div><label className="label-tech block">IVA %</label>
            <select className={field} value={form.vat_rate} onChange={(e) => setForm({ ...form, vat_rate: e.target.value })}>
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
              <option value="">Produto...</option>
              {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <input type="number" min="1" step="any" className={field + " w-20"} value={pick.quantity} onChange={(e) => setPick({ ...pick, quantity: e.target.value })} />
            <button type="button" data-testid="btn-add-combo-item" onClick={addItem} className="px-3 border border-border"><Plus className="w-4 h-4" /></button>
          </div>
        </div>
        <button data-testid="btn-save-combo" className={btn + " w-full"}>Guardar menu</button>
      </form>

      <div className="space-y-2">
        {combos.map((c) => (
          <div key={c.id} data-testid={`combo-row-${c.id}`} className="border border-border p-3">
            <div className="flex items-center justify-between">
              <div className="font-semibold">{c.name} <span className="mono text-sm">{fmtMoney(c.price, config)}</span> <span className="label-tech">IVA {c.vat_rate}%</span></div>
              <button data-testid={`btn-del-combo-${c.id}`} onClick={() => del(c.id)} className="text-destructive"><Trash2 className="w-4 h-4" /></button>
            </div>
            <div className="text-sm text-muted-foreground mt-1">{c.items.map((it) => `${it.quantity}× ${pname(it.product_id)}`).join(", ")}</div>
          </div>
        ))}
        {combos.length === 0 && <p className="text-sm text-muted-foreground">Sem menus.</p>}
      </div>
    </div>
  );
}
