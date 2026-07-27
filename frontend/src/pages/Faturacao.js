import { useEffect, useState, useCallback } from "react";
import api, { eur, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Trash2, Send, CheckCircle2 } from "lucide-react";

const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";
const emptyItem = { description: "", quantity: 1, unit_price: 0, vat_rate: 23 };
const newLine = () => ({ uid: crypto.randomUUID(), ...emptyItem });

export default function Faturacao() {
  const [invoices, setInvoices] = useState([]);
  const [open, setOpen] = useState(false);
  const [client, setClient] = useState({ client_name: "", client_nif: "" });
  const [lines, setLines] = useState([newLine()]);

  const load = useCallback(() => api.get("/invoices").then((r) => setInvoices(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const updateLine = (idx, key, val) => setLines(lines.map((l, i) => (i === idx ? { ...l, [key]: val } : l)));
  const addLine = () => setLines([...lines, newLine()]);
  const removeLine = (idx) => setLines(lines.filter((_, i) => i !== idx));

  const totals = lines.reduce(
    (acc, l) => {
      const line = Number(l.quantity) * Number(l.unit_price);
      const vat = (line * Number(l.vat_rate)) / 100;
      acc.sub += line; acc.vat += vat;
      return acc;
    },
    { sub: 0, vat: 0 }
  );

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/invoices", {
        ...client,
        items: lines.map((l) => ({ description: l.description, quantity: Number(l.quantity), unit_price: Number(l.unit_price), vat_rate: Number(l.vat_rate) })),
      });
      toast.success("Fatura criada");
      setOpen(false); setClient({ client_name: "", client_nif: "" }); setLines([newLine()]);
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  };

  const sync = async (id) => {
    try {
      const { data } = await api.post(`/invoices/${id}/sync`);
      toast.success(data.message);
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  };

  return (
    <div>
      <PageHeader title="Faturação" subtitle="Documentos e integração externa (preparada)">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <button data-testid="btn-add-invoice" className={btnPrimary}><Plus className="w-4 h-4 inline mr-1" /> Nova Fatura</button>
          </DialogTrigger>
          <DialogContent className="rounded-none max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle className="font-display tracking-tight">Nova Fatura</DialogTitle></DialogHeader>
            <form onSubmit={submit} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <input data-testid="input-client-name" required placeholder="Cliente" className={field} value={client.client_name} onChange={(e) => setClient({ ...client, client_name: e.target.value })} />
                <input placeholder="NIF" className={field} value={client.client_nif} onChange={(e) => setClient({ ...client, client_nif: e.target.value })} />
              </div>
              <div className="label-tech">Linhas</div>
              {lines.map((l, idx) => (
                <div key={l.uid} className="grid grid-cols-12 gap-2 items-center">
                  <input data-testid={`input-line-desc-${idx}`} required placeholder="Descrição" className={field + " col-span-5"} value={l.description} onChange={(e) => updateLine(idx, "description", e.target.value)} />
                  <input type="number" step="any" placeholder="Qtd" className={field + " col-span-2"} value={l.quantity} onChange={(e) => updateLine(idx, "quantity", e.target.value)} />
                  <input type="number" step="any" placeholder="Preço" className={field + " col-span-2"} value={l.unit_price} onChange={(e) => updateLine(idx, "unit_price", e.target.value)} />
                  <select className={field + " col-span-2"} value={l.vat_rate} onChange={(e) => updateLine(idx, "vat_rate", e.target.value)}>
                    <option value={23}>23%</option>
                    <option value={13}>13%</option>
                    <option value={6}>6%</option>
                    <option value={0}>0%</option>
                  </select>
                  <button type="button" onClick={() => removeLine(idx)} className="col-span-1 text-destructive"><Trash2 className="w-4 h-4" /></button>
                </div>
              ))}
              <button type="button" data-testid="btn-add-line" onClick={addLine} className="text-sm border border-border px-3 py-1.5 hover:bg-secondary transition-colors duration-150">+ Linha</button>
              <div className="border-t border-border pt-3 mono text-sm text-right space-y-1">
                <div>Subtotal: {eur(totals.sub)}</div>
                <div>IVA: {eur(totals.vat)}</div>
                <div className="font-display text-xl font-bold">Total: {eur(totals.sub + totals.vat)}</div>
              </div>
              <button data-testid="btn-save-invoice" className={btnPrimary + " w-full"}>Criar fatura</button>
            </form>
          </DialogContent>
        </Dialog>
      </PageHeader>

      <div className="p-8">
        <div className="bg-accent/15 border border-accent p-4 mb-4 text-sm">
          <b>Integração de faturação:</b> a estrutura está preparada. O botão "Emitir" simula o envio para um sistema externo (ex: InvoiceXpress / Moloni), a ligar futuramente.
        </div>
        <div className="bg-card border border-border overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border label-tech text-left">
                <th className="px-4 py-3">Nº</th>
                <th className="px-4 py-3">Cliente</th>
                <th className="px-4 py-3">NIF</th>
                <th className="px-4 py-3 text-right">Total</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id} data-testid={`invoice-row-${inv.id}`} className="border-b border-border">
                  <td className="px-4 py-3 mono font-semibold">{inv.number}</td>
                  <td className="px-4 py-3">{inv.client_name}</td>
                  <td className="px-4 py-3 mono text-muted-foreground">{inv.client_nif || "—"}</td>
                  <td className="px-4 py-3 text-right mono font-semibold">{eur(inv.total)}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 font-semibold ${inv.external_synced ? "bg-primary text-primary-foreground" : "bg-secondary"}`}>{inv.status}</span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {inv.external_synced ? (
                      <span className="text-xs text-primary inline-flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> emitida</span>
                    ) : (
                      <button data-testid={`btn-sync-${inv.id}`} onClick={() => sync(inv.id)} className="text-xs border border-border px-2 py-1 hover:bg-secondary transition-colors duration-150 inline-flex items-center gap-1"><Send className="w-3 h-3" /> Emitir</button>
                    )}
                  </td>
                </tr>
              ))}
              {invoices.length === 0 && <tr><td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">Sem faturas.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
