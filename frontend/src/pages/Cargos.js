import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Plus, Trash2, Pencil, Lock, ShieldCheck } from "lucide-react";

const MODULES = [
  { key: "stock", label: "Stock" },
  { key: "picagem", label: "Picagem" },
  { key: "consumo", label: "Consumo" },
  { key: "staff", label: "Staff" },
  { key: "faturacao", label: "Registadora" },
  { key: "relatorios", label: "Relatórios" },
];
const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

const empty = { name: "", modules: [], is_supervisor: false };

export default function Cargos() {
  const [roles, setRoles] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(empty);

  const load = useCallback(() => api.get("/roles").then((r) => setRoles(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEditing(null); setForm(empty); setOpen(true); };
  const openEdit = (r) => { setEditing(r); setForm({ name: r.name, modules: r.modules || [], is_supervisor: !!r.is_supervisor }); setOpen(true); };

  const toggleMod = (key) => {
    const has = form.modules.includes(key);
    setForm({ ...form, modules: has ? form.modules.filter((m) => m !== key) : [...form.modules, key] });
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      if (editing) {
        await api.put(`/roles/${editing.id}`, form);
        toast.success("Cargo atualizado");
      } else {
        await api.post("/roles", form);
        toast.success("Cargo criado");
      }
      setOpen(false);
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  };

  const remove = async (id) => {
    try {
      await api.delete(`/roles/${id}`);
      toast.success("Cargo eliminado");
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  };

  return (
    <div>
      <PageHeader title="Cargos" subtitle="Funções personalizadas e acesso por módulo">
        <button data-testid="btn-add-role" onClick={openNew} className={btnPrimary}><Plus className="w-4 h-4 inline mr-1" /> Cargo</button>
      </PageHeader>

      <div className="p-4 sm:p-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-1 bg-border">
          {roles.map((r) => (
            <div key={r.id} data-testid={`role-card-${r.id}`} className="bg-card border border-border p-6 fade-up">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className={`w-5 h-5 ${r.is_admin ? "text-primary" : "text-muted-foreground"}`} />
                  <div className="font-display text-xl font-bold tracking-tight">{r.name}</div>
                </div>
                {r.is_system && <span className="text-[0.6rem] px-1.5 py-0.5 bg-primary text-primary-foreground label-tech flex items-center gap-1"><Lock className="w-3 h-3" /> sistema</span>}
              </div>
              {r.is_supervisor && !r.is_admin && <div className="text-xs text-muted-foreground mb-2">Supervisão (vê registos de todos)</div>}
              <div className="flex flex-wrap gap-1 mb-4">
                {r.is_admin ? (
                  <span className="text-[0.65rem] px-1.5 py-0.5 border border-border label-tech" style={{ letterSpacing: "0.1em" }}>acesso total</span>
                ) : (r.modules || []).length ? (
                  r.modules.map((m) => <span key={m} className="text-[0.65rem] px-1.5 py-0.5 border border-border label-tech" style={{ letterSpacing: "0.1em" }}>{m}</span>)
                ) : <span className="text-xs text-muted-foreground">Sem módulos</span>}
              </div>
              <div className="flex gap-2">
                {r.is_system ? (
                  <div className="flex-1 py-1.5 text-center text-xs text-muted-foreground border border-dashed border-border">Protegido — só editável no código</div>
                ) : (
                  <>
                    <button data-testid={`btn-edit-role-${r.id}`} onClick={() => openEdit(r)} className="flex-1 py-1.5 border border-border text-sm hover:bg-secondary transition-colors duration-150 flex items-center justify-center gap-1"><Pencil className="w-3.5 h-3.5" /> Editar</button>
                    <button data-testid={`btn-delete-role-${r.id}`} onClick={() => remove(r.id)} className="py-1.5 px-3 border border-border text-destructive hover:bg-destructive/10 transition-colors duration-150"><Trash2 className="w-3.5 h-3.5" /></button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="rounded-none max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display tracking-tight">{editing ? "Editar Cargo" : "Novo Cargo"}</DialogTitle></DialogHeader>
          <form onSubmit={submit} className="space-y-3">
            <input data-testid="input-role-name" required placeholder="Nome do cargo (ex: Chefe de Sala)" className={field} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <div>
              <label className="label-tech block mb-2">Módulos com acesso</label>
              <div className="grid grid-cols-2 gap-2">
                {MODULES.map((m) => (
                  <label key={m.key} className="flex items-center gap-2 text-sm border border-border px-2 py-1.5 cursor-pointer">
                    <input data-testid={`role-mod-${m.key}`} type="checkbox" checked={form.modules.includes(m.key)} onChange={() => toggleMod(m.key)} />
                    {m.label}
                  </label>
                ))}
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm border border-border px-2 py-2 cursor-pointer">
              <input data-testid="role-supervisor" type="checkbox" checked={form.is_supervisor} onChange={(e) => setForm({ ...form, is_supervisor: e.target.checked })} />
              <span>Supervisão — pode ver e registar por todos os funcionários</span>
            </label>
            <button data-testid="btn-save-role" className={btnPrimary + " w-full"}>{editing ? "Guardar alterações" : "Criar cargo"}</button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
