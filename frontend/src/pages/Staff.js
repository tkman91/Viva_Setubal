import { useEffect, useState, useCallback } from "react";
import api, { eur, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Trash2, Shield } from "lucide-react";

const MODULES = [
  { key: "stock", label: "Stock" },
  { key: "picagem", label: "Picagem" },
  { key: "consumo", label: "Consumo" },
  { key: "staff", label: "Staff" },
  { key: "faturacao", label: "Faturação" },
  { key: "relatorios", label: "Relatórios" },
];
const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

const empty = { name: "", email: "", password: "", role: "funcionario", hourly_wage: 0, phone: "", permissions: ["picagem"] };

export default function Staff() {
  const { user } = useAuth();
  const [staff, setStaff] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(empty);

  const load = useCallback(() => api.get("/staff").then((r) => setStaff(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEditing(null); setForm(empty); setOpen(true); };
  const openEdit = (s) => { setEditing(s); setForm({ ...s, password: "" }); setOpen(true); };

  const togglePerm = (key) => {
    const has = form.permissions.includes(key);
    setForm({ ...form, permissions: has ? form.permissions.filter((p) => p !== key) : [...form.permissions, key] });
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form, hourly_wage: Number(form.hourly_wage) };
      if (editing) {
        if (!payload.password) delete payload.password;
        await api.put(`/staff/${editing.id}`, payload);
        toast.success("Funcionário atualizado");
      } else {
        await api.post("/staff", payload);
        toast.success("Funcionário adicionado");
      }
      setOpen(false);
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  };

  const remove = async (id) => {
    try {
      await api.delete(`/staff/${id}`);
      toast.success("Funcionário eliminado");
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  };

  const roleColor = { admin: "bg-primary text-primary-foreground", gestor: "bg-accent text-accent-foreground", funcionario: "bg-secondary" };

  return (
    <div>
      <PageHeader title="Gestão de Staff" subtitle="Funcionários, permissões e salários">
        <button data-testid="btn-add-staff" onClick={openNew} className={btnPrimary}><Plus className="w-4 h-4 inline mr-1" /> Funcionário</button>
      </PageHeader>

      <div className="p-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-1 bg-border">
          {staff.map((s) => (
            <div key={s.id} data-testid={`staff-card-${s.id}`} className="bg-card border border-border p-6 fade-up">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="font-display text-xl font-bold tracking-tight">{s.name}</div>
                  <div className="mono text-xs text-muted-foreground">{s.email}</div>
                </div>
                <span className={`text-xs px-2 py-0.5 font-semibold ${roleColor[s.role]}`}>{s.role}</span>
              </div>
              <div className="flex items-center gap-2 mb-3 mono text-sm">
                <span className="text-muted-foreground">Salário/h:</span> {eur(s.hourly_wage)}
              </div>
              <div className="flex flex-wrap gap-1 mb-4">
                {(s.permissions || []).map((p) => (
                  <span key={p} className="text-[0.65rem] px-1.5 py-0.5 border border-border label-tech" style={{ letterSpacing: "0.1em" }}>{p}</span>
                ))}
              </div>
              <div className="flex gap-2">
                <button data-testid={`btn-edit-staff-${s.id}`} onClick={() => openEdit(s)} className="flex-1 py-1.5 border border-border text-sm hover:bg-secondary transition-colors duration-150 flex items-center justify-center gap-1"><Shield className="w-3.5 h-3.5" /> Gerir</button>
                {s.id !== user.id && (
                  <button data-testid={`btn-delete-staff-${s.id}`} onClick={() => remove(s.id)} className="py-1.5 px-3 border border-border text-destructive hover:bg-destructive/10 transition-colors duration-150"><Trash2 className="w-3.5 h-3.5" /></button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="rounded-none max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display tracking-tight">{editing ? "Gerir Funcionário" : "Novo Funcionário"}</DialogTitle></DialogHeader>
          <form onSubmit={submit} className="space-y-3">
            <input data-testid="input-staff-name" required placeholder="Nome" className={field} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input data-testid="input-staff-email" required type="email" placeholder="Email" disabled={!!editing} className={field + (editing ? " opacity-60" : "")} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            <input data-testid="input-staff-password" type="password" placeholder={editing ? "Nova palavra-passe (deixe vazio p/ manter)" : "Palavra-passe"} required={!editing} className={field} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label-tech">Função</label>
                <select data-testid="select-staff-role" className={field} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  <option value="funcionario">Funcionário</option>
                  <option value="gestor">Gestor</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div><label className="label-tech">Salário/hora €</label><input type="number" step="any" className={field} value={form.hourly_wage} onChange={(e) => setForm({ ...form, hourly_wage: e.target.value })} /></div>
            </div>
            <input placeholder="Telefone" className={field} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            {form.role === "funcionario" && (
              <div>
                <label className="label-tech block mb-2">Permissões de acesso</label>
                <div className="grid grid-cols-2 gap-2">
                  {MODULES.map((m) => (
                    <label key={m.key} className="flex items-center gap-2 text-sm border border-border px-2 py-1.5 cursor-pointer">
                      <input data-testid={`perm-${m.key}`} type="checkbox" checked={form.permissions.includes(m.key)} onChange={() => togglePerm(m.key)} />
                      {m.label}
                    </label>
                  ))}
                </div>
              </div>
            )}
            {form.role !== "funcionario" && <p className="text-xs text-muted-foreground">Gestores e Admins têm acesso a todos os módulos.</p>}
            <button data-testid="btn-save-staff" className={btnPrimary + " w-full"}>{editing ? "Guardar alterações" : "Adicionar"}</button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
