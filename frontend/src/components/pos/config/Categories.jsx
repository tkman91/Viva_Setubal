import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";

const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btn = "px-3 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

export default function Categories() {
  const [cats, setCats] = useState([]);
  const [form, setForm] = useState({ name: "", color: "#111827" });

  const load = useCallback(() => api.get("/pos/categories").then((r) => setCats(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const add = async (e) => {
    e.preventDefault();
    try { await api.post("/pos/categories", { ...form, order: cats.length }); setForm({ name: "", color: "#111827" }); load(); toast.success("Categoria criada"); }
    catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };
  const del = async (id) => { await api.delete(`/pos/categories/${id}`); load(); };

  return (
    <div className="space-y-4 max-w-xl">
      <form onSubmit={add} className="flex items-end gap-2">
        <div className="flex-1"><label className="label-tech block mb-1">Nome</label><input data-testid="input-cat-name" required placeholder="ex: Bebidas" className={field} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
        <div><label className="label-tech block mb-1">Cor</label><input data-testid="input-cat-color" type="color" className="h-10 w-14 border border-input bg-background" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} /></div>
        <button data-testid="btn-add-cat" className={btn}><Plus className="w-4 h-4" /></button>
      </form>
      <div className="space-y-1">
        {cats.map((c) => (
          <div key={c.id} data-testid={`cat-row-${c.id}`} className="flex items-center justify-between border border-border px-3 py-2">
            <div className="flex items-center gap-2"><span className="w-4 h-4 rounded-full" style={{ backgroundColor: c.color }} /> {c.name}</div>
            <button data-testid={`btn-del-cat-${c.id}`} onClick={() => del(c.id)} className="text-destructive"><Trash2 className="w-4 h-4" /></button>
          </div>
        ))}
        {cats.length === 0 && <p className="text-sm text-muted-foreground">Sem categorias.</p>}
      </div>
    </div>
  );
}
