import { useEffect, useState, useCallback } from "react";
import api, { eur, num, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Plus, ArrowUp, ArrowDown, Trash2, Pencil } from "lucide-react";

const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

export default function Stock() {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [modGroups, setModGroups] = useState([]);
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState(null);
  const [moveProduct, setMoveProduct] = useState(null);
  const [form, setForm] = useState({ name: "", category: "Geral", category_id: "", unit: "un", quantity: 0, min_quantity: 0, cost_price: 0, sale_price: 0, vat_rate: 23, track_stock: true, modifier_group_ids: [] });
  const [move, setMove] = useState({ type: "entrada", quantity: 1, note: "" });

  const load = useCallback(() => api.get("/products").then((r) => setProducts(r.data)), []);
  useEffect(() => {
    load();
    api.get("/pos/categories").then((r) => setCategories(r.data)).catch(() => {});
    api.get("/pos/modifier-groups").then((r) => setModGroups(r.data)).catch(() => {});
  }, [load]);

  const emptyForm = { name: "", category: "Geral", category_id: "", unit: "un", quantity: 0, min_quantity: 0, cost_price: 0, sale_price: 0, vat_rate: 23, track_stock: true, modifier_group_ids: [] };

  const addProduct = async (e) => {
    e.preventDefault();
    try {
      const cat = categories.find((c) => c.id === form.category_id);
      const payload = {
        ...form,
        category: cat ? cat.name : (form.category || "Geral"),
        quantity: Number(form.quantity),
        min_quantity: Number(form.min_quantity),
        cost_price: Number(form.cost_price),
        sale_price: Number(form.sale_price),
        vat_rate: Number(form.vat_rate),
      };
      if (editId) {
        await api.put(`/products/${editId}`, payload);
        toast.success("Produto atualizado");
      } else {
        await api.post("/products", payload);
        toast.success("Produto adicionado");
      }
      setOpen(false); setEditId(null);
      setForm(emptyForm);
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  };

  const openEdit = (p) => {
    setEditId(p.id);
    setForm({
      name: p.name || "", category: p.category || "Geral", category_id: p.category_id || "",
      unit: p.unit || "un", quantity: p.quantity ?? 0, min_quantity: p.min_quantity ?? 0,
      cost_price: p.cost_price ?? 0, sale_price: p.sale_price ?? 0, vat_rate: p.vat_rate ?? 23,
      track_stock: p.track_stock !== false, modifier_group_ids: p.modifier_group_ids || [],
    });
    setOpen(true);
  };

  const toggleMod = (id) => setForm((f) => ({ ...f, modifier_group_ids: f.modifier_group_ids.includes(id) ? f.modifier_group_ids.filter((x) => x !== id) : [...f.modifier_group_ids, id] }));

  const submitMove = async (e) => {
    e.preventDefault();
    try {
      await api.post("/stock/movement", { product_id: moveProduct.id, type: move.type, quantity: Number(move.quantity), note: move.note });
      toast.success("Movimento registado");
      setMoveProduct(null);
      setMove({ type: "entrada", quantity: 1, note: "" });
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  };

  const remove = async (id) => {
    await api.delete(`/products/${id}`);
    toast.success("Produto eliminado");
    load();
  };

  return (
    <div>
      <PageHeader title="Controlo de Stock" subtitle="Inventário e movimentos">
        <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) { setEditId(null); setForm(emptyForm); } }}>
          <DialogTrigger asChild>
            <button data-testid="btn-add-product" onClick={() => { setEditId(null); setForm(emptyForm); }} className={btnPrimary}>
              <Plus className="w-4 h-4 inline mr-1" /> Produto
            </button>
          </DialogTrigger>
          <DialogContent className="rounded-none">
            <DialogHeader><DialogTitle className="font-display tracking-tight">{editId ? "Editar Produto" : "Novo Produto"}</DialogTitle></DialogHeader>
            <form onSubmit={addProduct} className="space-y-3">
              <input data-testid="input-product-name" required placeholder="Nome" className={field} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label-tech">Categoria</label>
                  <select data-testid="select-product-category" className={field} value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
                    <option value="">Geral</option>
                    {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                <div><label className="label-tech">Unidade</label><input placeholder="un, kg, L" className={field} value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} /></div>
                <div><label className="label-tech">Quantidade</label><input data-testid="input-product-qty" type="number" step="any" className={field} value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></div>
                <div><label className="label-tech">Stock mínimo</label><input type="number" step="any" className={field} value={form.min_quantity} onChange={(e) => setForm({ ...form, min_quantity: e.target.value })} /></div>
                <div><label className="label-tech">Preço custo €</label><input data-testid="input-product-cost" type="number" step="any" className={field} value={form.cost_price} onChange={(e) => setForm({ ...form, cost_price: e.target.value })} /></div>
                <div><label className="label-tech">Preço venda €</label><input data-testid="input-product-price" type="number" step="any" className={field} value={form.sale_price} onChange={(e) => setForm({ ...form, sale_price: e.target.value })} /></div>
                <div>
                  <label className="label-tech">IVA</label>
                  <select data-testid="select-product-vat" className={field} value={form.vat_rate} onChange={(e) => setForm({ ...form, vat_rate: e.target.value })}>
                    {[23, 13, 6, 0].map((r) => <option key={r} value={r}>{r}%</option>)}
                  </select>
                </div>
                <label className="flex items-center gap-2 text-sm pt-5"><input data-testid="chk-product-track" type="checkbox" checked={form.track_stock} onChange={(e) => setForm({ ...form, track_stock: e.target.checked })} /> Controlar stock</label>
              </div>
              {modGroups.length > 0 && (
                <div>
                  <label className="label-tech block mb-1">Modificadores</label>
                  <div className="flex flex-wrap gap-1">
                    {modGroups.map((g) => (
                      <button type="button" key={g.id} data-testid={`prod-mod-${g.id}`} onClick={() => toggleMod(g.id)}
                        className={`px-2 py-1 border text-xs ${form.modifier_group_ids.includes(g.id) ? "bg-primary text-primary-foreground border-primary" : "border-border"}`}>{g.name}</button>
                    ))}
                  </div>
                </div>
              )}
              <button data-testid="btn-save-product" className={btnPrimary + " w-full"}>Guardar</button>
            </form>
          </DialogContent>
        </Dialog>
      </PageHeader>

      <div className="p-4 sm:p-8">
        <div className="bg-card border border-border overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border label-tech text-left">
                <th className="px-4 py-3">Produto</th>
                <th className="px-4 py-3">Categoria</th>
                <th className="px-4 py-3 text-right">Stock</th>
                <th className="px-4 py-3 text-right">Mín.</th>
                <th className="px-4 py-3 text-right">Custo</th>
                <th className="px-4 py-3 text-right">Venda</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => {
                const low = p.quantity <= p.min_quantity;
                return (
                  <tr key={p.id} data-testid={`product-row-${p.id}`} className={`border-b border-border ${low ? "bg-destructive/10" : ""}`}>
                    <td className="px-4 py-3 font-medium">{p.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{p.category}</td>
                    <td className={`px-4 py-3 text-right mono font-semibold ${low ? "text-destructive" : ""}`}>{num(p.quantity)} {p.unit}</td>
                    <td className="px-4 py-3 text-right mono text-muted-foreground">{num(p.min_quantity)}</td>
                    <td className="px-4 py-3 text-right mono">{eur(p.cost_price)}</td>
                    <td className="px-4 py-3 text-right mono">{eur(p.sale_price)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button data-testid={`btn-edit-product-${p.id}`} onClick={() => openEdit(p)} className="p-1.5 border border-border hover:bg-secondary transition-colors duration-150" title="Editar"><Pencil className="w-3.5 h-3.5" /></button>
                        <button data-testid={`btn-move-${p.id}`} onClick={() => setMoveProduct(p)} className="p-1.5 border border-border hover:bg-secondary transition-colors duration-150" title="Movimento"><ArrowUp className="w-3.5 h-3.5" /></button>
                        <button data-testid={`btn-delete-product-${p.id}`} onClick={() => remove(p.id)} className="p-1.5 border border-border text-destructive hover:bg-destructive/10 transition-colors duration-150"><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {products.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">Sem produtos. Adicione o primeiro.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={!!moveProduct} onOpenChange={(o) => !o && setMoveProduct(null)}>
        <DialogContent className="rounded-none">
          <DialogHeader><DialogTitle className="font-display tracking-tight">Movimento · {moveProduct?.name}</DialogTitle></DialogHeader>
          <form onSubmit={submitMove} className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <button type="button" data-testid="btn-mv-entrada" onClick={() => setMove({ ...move, type: "entrada" })} className={`py-2 border text-sm font-semibold flex items-center justify-center gap-1 ${move.type === "entrada" ? "bg-primary text-primary-foreground border-primary" : "border-border"}`}><ArrowDown className="w-4 h-4" /> Entrada</button>
              <button type="button" data-testid="btn-mv-saida" onClick={() => setMove({ ...move, type: "saida" })} className={`py-2 border text-sm font-semibold flex items-center justify-center gap-1 ${move.type === "saida" ? "bg-destructive text-destructive-foreground border-destructive" : "border-border"}`}><ArrowUp className="w-4 h-4" /> Saída</button>
            </div>
            <div><label className="label-tech">Quantidade</label><input data-testid="input-move-qty" type="number" step="any" min="0" className={field} value={move.quantity} onChange={(e) => setMove({ ...move, quantity: e.target.value })} /></div>
            <input placeholder="Nota (opcional)" className={field} value={move.note} onChange={(e) => setMove({ ...move, note: e.target.value })} />
            <button data-testid="btn-save-move" className={btnPrimary + " w-full"}>Registar movimento</button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
