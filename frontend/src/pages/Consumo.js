import { useEffect, useState, useCallback } from "react";
import api, { eur, num, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Plus } from "lucide-react";

const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

export default function Consumo() {
  const { user } = useAuth();
  const canSeeAll = !!user && (user.is_admin || (user.is_supervisor && (user.permissions || []).includes("consumo")));
  const [items, setItems] = useState([]);
  const [products, setProducts] = useState([]);
  const [staff, setStaff] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ staff_id: "", product_id: "", quantity: 1, deduct_stock: true });

  const load = useCallback(() => {
    api.get("/consumption").then((r) => setItems(r.data));
    api.get("/products").then((r) => setProducts(r.data));
    if (canSeeAll) api.get("/staff").then((r) => setStaff(r.data)).catch(() => {});
  }, [canSeeAll]);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/consumption", {
        staff_id: form.staff_id || undefined,
        product_id: form.product_id,
        quantity: Number(form.quantity),
        deduct_stock: form.deduct_stock,
      });
      toast.success("Consumo registado");
      setOpen(false);
      setForm({ staff_id: "", product_id: "", quantity: 1, deduct_stock: true });
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  };

  const total = items.reduce((s, i) => s + i.value, 0);

  // Aggregate per staff
  const perStaff = {};
  items.forEach((i) => { perStaff[i.staff_name] = (perStaff[i.staff_name] || 0) + i.value; });

  return (
    <div>
      <PageHeader title="Consumo Staff" subtitle="Refeições e produtos consumidos pelos funcionários">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <button data-testid="btn-add-consumo" className={btnPrimary}><Plus className="w-4 h-4 inline mr-1" /> Registar</button>
          </DialogTrigger>
          <DialogContent className="rounded-none">
            <DialogHeader><DialogTitle className="font-display tracking-tight">Registar Consumo</DialogTitle></DialogHeader>
            <form onSubmit={submit} className="space-y-3">
              {canSeeAll && (
                <div>
                  <label className="label-tech">Funcionário</label>
                  <select data-testid="select-consumo-staff" className={field} value={form.staff_id} onChange={(e) => setForm({ ...form, staff_id: e.target.value })}>
                    <option value="">— Eu ({user.name}) —</option>
                    {staff.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>
              )}
              <div>
                <label className="label-tech">Produto</label>
                <select data-testid="select-consumo-product" required className={field} value={form.product_id} onChange={(e) => setForm({ ...form, product_id: e.target.value })}>
                  <option value="">Selecionar...</option>
                  {products.map((p) => <option key={p.id} value={p.id}>{p.name} · {eur(p.sale_price)}</option>)}
                </select>
              </div>
              <div><label className="label-tech">Quantidade</label><input data-testid="input-consumo-qty" type="number" step="any" min="0" className={field} value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></div>
              <label className="flex items-center gap-2 text-sm">
                <input data-testid="check-deduct-stock" type="checkbox" checked={form.deduct_stock} onChange={(e) => setForm({ ...form, deduct_stock: e.target.checked })} />
                Descontar do stock
              </label>
              <button data-testid="btn-save-consumo" className={btnPrimary + " w-full"}>Registar</button>
            </form>
          </DialogContent>
        </Dialog>
      </PageHeader>

      <div className="p-4 sm:p-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-1 bg-border mb-1">
          <div className="bg-card border border-border p-6">
            <div className="label-tech mb-2">Total {canSeeAll ? "geral" : "meu"}</div>
            <div data-testid="consumo-total" className="font-display text-4xl font-black tracking-tighter">{eur(total)}</div>
          </div>
          {canSeeAll && (
            <div className="lg:col-span-2 bg-card border border-border p-6">
              <div className="label-tech mb-3">Por funcionário</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(perStaff).map(([name, v]) => (
                  <div key={name} className="border border-border px-3 py-2">
                    <div className="text-sm font-medium">{name}</div>
                    <div className="mono text-sm text-accent-foreground" style={{ color: "hsl(var(--accent))" }}>{eur(v)}</div>
                  </div>
                ))}
                {Object.keys(perStaff).length === 0 && <p className="text-sm text-muted-foreground">Sem registos.</p>}
              </div>
            </div>
          )}
        </div>

        <div className="bg-card border border-border overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border label-tech text-left">
                <th className="px-4 py-3">Data</th>
                {canSeeAll && <th className="px-4 py-3">Funcionário</th>}
                <th className="px-4 py-3">Produto</th>
                <th className="px-4 py-3 text-right">Qtd.</th>
                <th className="px-4 py-3 text-right">Valor</th>
                <th className="px-4 py-3 text-right">Stock</th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id} data-testid={`consumo-row-${i.id}`} className="border-b border-border">
                  <td className="px-4 py-3 mono text-xs text-muted-foreground">{new Date(i.created_at).toLocaleString("pt-PT")}</td>
                  {canSeeAll && <td className="px-4 py-3 font-medium">{i.staff_name}</td>}
                  <td className="px-4 py-3">{i.product_name}</td>
                  <td className="px-4 py-3 text-right mono">{num(i.quantity)}</td>
                  <td className="px-4 py-3 text-right mono font-semibold">{eur(i.value)}</td>
                  <td className="px-4 py-3 text-right text-xs">{i.deducted_stock ? "descontado" : "—"}</td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={canSeeAll ? 6 : 5} className="px-4 py-10 text-center text-muted-foreground">Sem consumos registados.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
