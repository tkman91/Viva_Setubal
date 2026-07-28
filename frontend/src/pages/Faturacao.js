import { useEffect, useState, useCallback } from "react";
import api, { eur, num, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Trash2, Table2, CheckCircle2, Utensils } from "lucide-react";

const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

export default function Registadora() {
  const [orders, setOrders] = useState([]);
  const [products, setProducts] = useState([]);
  const [newOpen, setNewOpen] = useState(false);
  const [newTable, setNewTable] = useState("");
  const [selected, setSelected] = useState(null);
  const [addForm, setAddForm] = useState({ product_id: "", quantity: 1 });

  const load = useCallback(async () => {
    const [o, p] = await Promise.all([api.get("/orders?status=aberta"), api.get("/products")]);
    setOrders(o.data);
    setProducts(p.data);
    return o.data;
  }, []);
  useEffect(() => { load(); }, [load]);

  const refreshSelected = async (id) => {
    const list = await load();
    setSelected(list.find((x) => x.id === id) || null);
  };

  const createTable = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/orders", { table_name: newTable });
      setNewTable(""); setNewOpen(false);
      await load();
      setSelected(data);
      toast.success("Mesa aberta");
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const addItem = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/orders/${selected.id}/items`, { product_id: addForm.product_id, quantity: Number(addForm.quantity) });
      toast.success("Item adicionado · stock descontado");
      setAddForm({ product_id: "", quantity: 1 });
      refreshSelected(selected.id);
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const removeItem = async (itemId) => {
    try {
      await api.delete(`/orders/${selected.id}/items/${itemId}`);
      toast.success("Item removido · stock devolvido");
      refreshSelected(selected.id);
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const closeOrder = async () => {
    try {
      const { data } = await api.post(`/orders/${selected.id}/close`);
      toast.success(`Conta fechada · ${eur(data.total)}`);
      setSelected(null);
      load();
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const cancelOrder = async () => {
    try {
      await api.delete(`/orders/${selected.id}`);
      toast.success("Mesa cancelada · stock devolvido");
      setSelected(null);
      load();
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  return (
    <div>
      <PageHeader title="Registadora" subtitle="Mesas · cada item desconta do stock">
        <Dialog open={newOpen} onOpenChange={setNewOpen}>
          <DialogTrigger asChild>
            <button data-testid="btn-new-table" className={btnPrimary}><Plus className="w-4 h-4 inline mr-1" /> Nova Mesa</button>
          </DialogTrigger>
          <DialogContent className="rounded-none">
            <DialogHeader><DialogTitle className="font-display tracking-tight">Abrir Mesa</DialogTitle></DialogHeader>
            <form onSubmit={createTable} className="space-y-3">
              <input data-testid="input-table-name" required placeholder="Nome/Nº da mesa (ex: Mesa 5)" className={field} value={newTable} onChange={(e) => setNewTable(e.target.value)} />
              <button data-testid="btn-save-table" className={btnPrimary + " w-full"}>Abrir mesa</button>
            </form>
          </DialogContent>
        </Dialog>
      </PageHeader>

      <div className="p-8">
        {orders.length === 0 && (
          <div className="text-center text-muted-foreground py-16 border border-dashed border-border">
            <Table2 className="w-10 h-10 mx-auto mb-3" /> Sem mesas abertas. Abre a primeira em "Nova Mesa".
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-1 bg-border">
          {orders.map((o) => (
            <button
              key={o.id}
              data-testid={`table-card-${o.id}`}
              onClick={() => setSelected(o)}
              className="bg-card border border-border p-6 text-left hover:bg-secondary transition-colors duration-150 fade-up"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2 font-display text-xl font-bold tracking-tight"><Utensils className="w-4 h-4 text-primary" /> {o.table_name}</div>
                <span className="text-xs px-2 py-0.5 bg-accent text-accent-foreground font-semibold">aberta</span>
              </div>
              <div className="label-tech">{o.items.length} {o.items.length === 1 ? "item" : "itens"}</div>
              <div className="font-display text-4xl font-black tracking-tighter mono">{eur(o.total)}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Detalhe da mesa */}
      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="rounded-none max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-display tracking-tight flex items-center gap-2">
              <Utensils className="w-5 h-5 text-primary" /> {selected?.table_name}
            </DialogTitle>
          </DialogHeader>

          {selected && (
            <div className="space-y-4">
              <form onSubmit={addItem} className="grid grid-cols-12 gap-2 items-end border-b border-border pb-4">
                <div className="col-span-7">
                  <label className="label-tech">Produto</label>
                  <select data-testid="select-order-product" required className={field} value={addForm.product_id} onChange={(e) => setAddForm({ ...addForm, product_id: e.target.value })}>
                    <option value="">Selecionar...</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id} disabled={p.quantity <= 0}>
                        {p.name} · {eur(p.sale_price)} · stock {num(p.quantity)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="col-span-3">
                  <label className="label-tech">Qtd</label>
                  <input data-testid="input-order-qty" type="number" step="any" min="0" className={field} value={addForm.quantity} onChange={(e) => setAddForm({ ...addForm, quantity: e.target.value })} />
                </div>
                <button data-testid="btn-add-item" className={btnPrimary + " col-span-2"}>Add</button>
              </form>

              <div className="space-y-1">
                {selected.items.length === 0 && <p className="text-sm text-muted-foreground">Sem itens. Adicione produtos acima.</p>}
                {selected.items.map((it) => (
                  <div key={it.id} data-testid={`order-item-${it.id}`} className="flex items-center justify-between py-2 border-b border-border text-sm">
                    <div><span className="mono">{num(it.quantity)}×</span> {it.product_name}</div>
                    <div className="flex items-center gap-3">
                      <span className="mono font-semibold">{eur(it.line_total)}</span>
                      <button data-testid={`btn-remove-item-${it.id}`} onClick={() => removeItem(it.id)} className="text-destructive hover:opacity-70 transition-opacity duration-150"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex items-center justify-between pt-2">
                <span className="label-tech">Total</span>
                <span data-testid="order-total" className="font-display text-4xl font-black tracking-tighter mono">{eur(selected.total)}</span>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-2">
                <button data-testid="btn-cancel-order" onClick={cancelOrder} className="py-2.5 border border-destructive text-destructive font-semibold text-sm hover:bg-destructive/10 transition-colors duration-150">Cancelar mesa</button>
                <button data-testid="btn-close-order" onClick={closeOrder} className={btnPrimary + " flex items-center justify-center gap-1"}><CheckCircle2 className="w-4 h-4" /> Fechar conta</button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
