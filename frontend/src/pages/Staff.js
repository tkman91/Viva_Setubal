import { useEffect, useState, useCallback } from "react";
import api, { eur, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Plus, Trash2, Shield } from "lucide-react";

const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

const empty = { name: "", email: "", password: "", role_id: "", hourly_wage: 0, phone: "" };

export default function Staff() {
  const { user, isAdmin } = useAuth();
  const [staff, setStaff] = useState([]);
  const [roles, setRoles] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(empty);

  const load = useCallback(() => {
    api.get("/staff").then((r) => setStaff(r.data));
    api.get("/roles").then((r) => setRoles(r.data));
  }, []);
  useEffect(() => { load(); }, [load]);

  const myRank = Number(user?.rank || 0);
  const assignableRoles = roles.filter((r) => Number(r.rank || 0) <= myRank);
  const canManageTarget = (s) => Number(s.rank || 0) <= myRank;

  const defaultRoleId = () => {
    const nonAdmin = assignableRoles.find((r) => !r.is_admin);
    return (nonAdmin || assignableRoles[0])?.id || "";
  };

  const openNew = () => { setEditing(null); setForm({ ...empty, role_id: defaultRoleId() }); setOpen(true); };
  const openEdit = (s) => { setEditing(s); setForm({ ...s, password: "", role_id: s.role_id || "" }); setOpen(true); };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.role_id) { toast.error("Selecione um cargo"); return; }
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

  const selectedRole = roles.find((r) => r.id === form.role_id);

  return (
    <div>
      <PageHeader title="Gestão de Staff" subtitle="Funcionários, cargos e salários">
        {isAdmin && (
          <button data-testid="btn-add-staff" onClick={openNew} className={btnPrimary}><Plus className="w-4 h-4 inline mr-1" /> Funcionário</button>
        )}
      </PageHeader>

      <div className="p-4 sm:p-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-1 bg-border">
          {staff.map((s) => (
            <div key={s.id} data-testid={`staff-card-${s.id}`} className="bg-card border border-border p-6 fade-up">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="font-display text-xl font-bold tracking-tight">{s.name}</div>
                  <div className="mono text-xs text-muted-foreground">{s.email}</div>
                </div>
                <span className={`text-xs px-2 py-0.5 font-semibold ${s.is_admin ? "bg-primary text-primary-foreground" : "bg-secondary"}`}>{s.role}</span>
              </div>
              <div className="flex items-center gap-2 mb-3 mono text-sm">
                <span className="text-muted-foreground">Salário/h:</span> {eur(s.hourly_wage)}
              </div>
              <div className="flex flex-wrap gap-1 mb-4">
                {(s.permissions || []).map((p) => (
                  <span key={p} className="text-[0.65rem] px-1.5 py-0.5 border border-border label-tech" style={{ letterSpacing: "0.1em" }}>{p}</span>
                ))}
              </div>
              {canManageTarget(s) && (
                <div className="flex gap-2">
                  <button data-testid={`btn-edit-staff-${s.id}`} onClick={() => openEdit(s)} className="flex-1 py-1.5 border border-border text-sm hover:bg-secondary transition-colors duration-150 flex items-center justify-center gap-1"><Shield className="w-3.5 h-3.5" /> Gerir</button>
                  {s.id !== user.id && (
                    <button data-testid={`btn-delete-staff-${s.id}`} onClick={() => remove(s.id)} className="py-1.5 px-3 border border-border text-destructive hover:bg-destructive/10 transition-colors duration-150"><Trash2 className="w-3.5 h-3.5" /></button>
                  )}
                </div>
              )}
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
                <label className="label-tech">Cargo</label>
                <select data-testid="select-staff-role" required className={field} value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })}>
                  <option value="">Selecionar...</option>
                  {assignableRoles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </div>
              <div><label className="label-tech">Salário/hora €</label><input type="number" step="any" className={field} value={form.hourly_wage} onChange={(e) => setForm({ ...form, hourly_wage: e.target.value })} /></div>
            </div>
            <input placeholder="Telefone" className={field} value={form.phone || ""} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            {selectedRole && (
              <div className="border border-border p-3 bg-secondary/30">
                <div className="label-tech mb-2">Acesso deste cargo</div>
                {selectedRole.is_admin ? (
                  <p className="text-xs text-muted-foreground">Acesso total a todos os módulos (administrador).</p>
                ) : (selectedRole.modules || []).length ? (
                  <div className="flex flex-wrap gap-1">
                    {selectedRole.modules.map((m) => <span key={m} className="text-[0.65rem] px-1.5 py-0.5 border border-border label-tech" style={{ letterSpacing: "0.1em" }}>{m}</span>)}
                  </div>
                ) : <p className="text-xs text-muted-foreground">Sem módulos atribuídos.</p>}
                <p className="text-[0.7rem] text-muted-foreground mt-2">As permissões são definidas no cargo. Edite em <b>Cargos</b>.</p>
              </div>
            )}
            <button data-testid="btn-save-staff" className={btnPrimary + " w-full"}>{editing ? "Guardar alterações" : "Adicionar"}</button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
