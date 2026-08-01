import { useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Save } from "lucide-react";

const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btn = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

export default function GeneralConfig({ config, setConfig }) {
  const [saving, setSaving] = useState(false);
  const c = config;
  const upd = (patch) => setConfig({ ...c, ...patch });
  const updReceipt = (patch) => setConfig({ ...c, receipt: { ...c.receipt, ...patch } });

  const addMethod = () => upd({ payment_methods: [...(c.payment_methods || []), { id: crypto.randomUUID(), name: "Novo", enabled: true }] });
  const setMethod = (id, patch) => upd({ payment_methods: c.payment_methods.map((m) => m.id === id ? { ...m, ...patch } : m) });
  const rmMethod = (id) => upd({ payment_methods: c.payment_methods.filter((m) => m.id !== id) });

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/pos/config", {
        currency_symbol: c.currency_symbol, decimals: Number(c.decimals), rounding: c.rounding,
        track_stock_default: c.track_stock_default, service_charge_enabled: c.service_charge_enabled,
        service_charge_percent: Number(c.service_charge_percent), default_vat_rate: Number(c.default_vat_rate),
        payment_methods: c.payment_methods, receipt: c.receipt,
        invoice_provider: c.invoice_provider || "none", invoice_enabled: !!c.invoice_enabled,
        invoice_account: c.invoice_account || "", invoice_api_key: c.invoice_api_key || "",
      });
      toast.success("Configuração guardada");
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
    setSaving(false);
  };

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Pagamentos & IVA */}
      <section className="border border-border p-4 space-y-3">
        <div className="font-display font-bold tracking-tight">Pagamentos & Serviço</div>
        <div className="space-y-1">
          {(c.payment_methods || []).map((mth) => (
            <div key={mth.id} data-testid={`method-${mth.id}`} className="flex items-center gap-2">
              <input className={field} value={mth.name} onChange={(e) => setMethod(mth.id, { name: e.target.value })} />
              <label className="flex items-center gap-1 text-sm whitespace-nowrap"><input type="checkbox" checked={mth.enabled} onChange={(e) => setMethod(mth.id, { enabled: e.target.checked })} /> ativo</label>
              <button onClick={() => rmMethod(mth.id)} className="text-destructive"><Trash2 className="w-4 h-4" /></button>
            </div>
          ))}
          <button data-testid="btn-add-method" onClick={addMethod} className="text-sm border border-border px-2 py-1 hover:bg-secondary"><Plus className="w-3.5 h-3.5 inline" /> método</button>
        </div>
        <div className="grid grid-cols-3 gap-3 items-end pt-2">
          <label className="flex items-center gap-2 text-sm pb-2"><input data-testid="chk-service" type="checkbox" checked={c.service_charge_enabled} onChange={(e) => upd({ service_charge_enabled: e.target.checked })} /> Taxa de serviço</label>
          <div><label className="label-tech block">Serviço %</label><input data-testid="input-service-pct" type="number" step="any" className={field} value={c.service_charge_percent} onChange={(e) => upd({ service_charge_percent: e.target.value })} /></div>
          <div><label className="label-tech block">IVA padrão %</label>
            <select data-testid="select-default-vat" className={field} value={c.default_vat_rate} onChange={(e) => upd({ default_vat_rate: e.target.value })}>
              {[23, 13, 6, 0].map((r) => <option key={r} value={r}>{r}%</option>)}
            </select>
          </div>
        </div>
      </section>

      {/* Talão */}
      <section className="border border-border p-4 space-y-3">
        <div className="font-display font-bold tracking-tight">Cabeçalho do talão</div>
        <div className="grid sm:grid-cols-2 gap-3">
          <div><label className="label-tech block">Nome</label><input data-testid="rcpt-name" className={field} value={c.receipt?.name || ""} onChange={(e) => updReceipt({ name: e.target.value })} /></div>
          <div><label className="label-tech block">NIF</label><input data-testid="rcpt-nif" className={field} value={c.receipt?.nif || ""} onChange={(e) => updReceipt({ nif: e.target.value })} /></div>
          <div><label className="label-tech block">Morada</label><input className={field} value={c.receipt?.address || ""} onChange={(e) => updReceipt({ address: e.target.value })} /></div>
          <div><label className="label-tech block">Telefone</label><input className={field} value={c.receipt?.phone || ""} onChange={(e) => updReceipt({ phone: e.target.value })} /></div>
          <div className="sm:col-span-2"><label className="label-tech block">Rodapé</label><input className={field} value={c.receipt?.footer || ""} onChange={(e) => updReceipt({ footer: e.target.value })} /></div>
        </div>
      </section>

      {/* Geral */}
      <section className="border border-border p-4 space-y-3">
        <div className="font-display font-bold tracking-tight">Moeda & arredondamento</div>
        <div className="grid grid-cols-3 gap-3">
          <div><label className="label-tech block">Símbolo</label><input data-testid="input-symbol" className={field} value={c.currency_symbol} onChange={(e) => upd({ currency_symbol: e.target.value })} /></div>
          <div><label className="label-tech block">Casas decimais</label><input data-testid="input-decimals" type="number" min="0" max="3" className={field} value={c.decimals} onChange={(e) => upd({ decimals: e.target.value })} /></div>
          <div><label className="label-tech block">Arredondamento</label>
            <select data-testid="select-rounding" className={field} value={c.rounding} onChange={(e) => upd({ rounding: e.target.value })}>
              <option value="none">Nenhum</option>
              <option value="0.05">0,05 €</option>
              <option value="0.10">0,10 €</option>
            </select>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm"><input data-testid="chk-track-stock" type="checkbox" checked={c.track_stock_default} onChange={(e) => upd({ track_stock_default: e.target.checked })} /> Controlar stock por defeito nos novos produtos</label>
      </section>

      {/* Faturação (configurável) */}
      <section className="border border-border p-4 space-y-3">
        <div className="font-display font-bold tracking-tight">Faturação certificada</div>
        <label className="flex items-center gap-2 text-sm"><input data-testid="chk-invoice-enabled" type="checkbox" checked={!!c.invoice_enabled} onChange={(e) => upd({ invoice_enabled: e.target.checked })} /> Ativar emissão de faturas</label>
        <div className="grid sm:grid-cols-3 gap-3">
          <div><label className="label-tech block">Fornecedor</label>
            <select data-testid="select-invoice-provider" className={field} value={c.invoice_provider || "none"} onChange={(e) => upd({ invoice_provider: e.target.value })}>
              <option value="none">Nenhum</option>
              <option value="invoicexpress">InvoiceXpress</option>
              <option value="moloni">Moloni</option>
              <option value="outro">Outro</option>
            </select>
          </div>
          <div><label className="label-tech block">Conta</label><input data-testid="input-invoice-account" className={field} value={c.invoice_account || ""} onChange={(e) => upd({ invoice_account: e.target.value })} /></div>
          <div><label className="label-tech block">API Key {c.invoice_api_key_set ? "(guardada)" : ""}</label><input data-testid="input-invoice-key" type="password" placeholder={c.invoice_api_key_set ? "••••• (deixa vazio p/ manter)" : "chave do fornecedor"} className={field} value={c.invoice_api_key || ""} onChange={(e) => upd({ invoice_api_key: e.target.value })} /></div>
        </div>
        <p className="text-xs text-muted-foreground">A ligação real ao fornecedor é feita quando fornecer a API key. Sem key ativa, a emissão gera um número sequencial SIMULADO.</p>
      </section>

      <button data-testid="btn-save-config" onClick={save} disabled={saving} className={btn + " flex items-center gap-2"}><Save className="w-4 h-4" /> {saving ? "A guardar..." : "Guardar configuração"}</button>
    </div>
  );
}
