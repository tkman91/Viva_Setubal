import { useState, useMemo } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { fmtMoney } from "@/lib/api";
import { Trash2 } from "lucide-react";

const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

export default function PaymentDialog({ order, config, onConfirm, onClose }) {
  const methods = (config?.payment_methods || []).filter((m) => m.enabled);
  const [payments, setPayments] = useState([]);
  const total = order?.total || 0;

  const paid = useMemo(() => payments.reduce((s, p) => s + (Number(p.amount) || 0), 0), [payments]);
  const remaining = Math.max(total - paid, 0);
  const change = Math.max(paid - total, 0);

  const addPayment = (method, amount) => setPayments((p) => [...p, { method, amount: Number(amount) || 0 }]);
  const removePayment = (i) => setPayments((p) => p.filter((_, idx) => idx !== i));

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="rounded-none max-w-md" data-testid="payment-dialog">
        <DialogHeader><DialogTitle className="font-display tracking-tight">Pagamento</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="label-tech">Total a pagar</span>
            <span data-testid="payment-total" className="font-display text-3xl font-black tracking-tighter mono">{fmtMoney(total, config)}</span>
          </div>

          <div className="grid grid-cols-2 gap-1">
            {methods.map((m) => (
              <button key={m.id} data-testid={`pay-method-${m.name}`} onClick={() => addPayment(m.name, remaining || total)}
                className="px-3 py-3 border border-border text-sm font-semibold hover:bg-secondary transition-colors duration-150">
                {m.name}
              </button>
            ))}
          </div>

          {payments.length > 0 && (
            <div className="space-y-1 border-t border-border pt-2">
              {payments.map((p, i) => (
                <div key={i} data-testid={`payment-row-${i}`} className="flex items-center justify-between text-sm">
                  <span>{p.method}</span>
                  <div className="flex items-center gap-2">
                    <input type="number" step="any" value={p.amount}
                      onChange={(e) => setPayments((arr) => arr.map((x, idx) => idx === i ? { ...x, amount: e.target.value } : x))}
                      className="w-24 px-2 py-1 bg-background border border-input text-right mono" />
                    <button onClick={() => removePayment(i)} className="text-destructive"><Trash2 className="w-4 h-4" /></button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="text-sm space-y-1 border-t border-border pt-2">
            <div className="flex justify-between"><span>Pago</span><span className="mono">{fmtMoney(paid, config)}</span></div>
            <div className="flex justify-between"><span>Falta</span><span className="mono">{fmtMoney(remaining, config)}</span></div>
            <div className="flex justify-between font-semibold"><span>Troco</span><span data-testid="payment-change" className="mono">{fmtMoney(change, config)}</span></div>
          </div>

          <button data-testid="payment-confirm" disabled={payments.length > 0 && paid + 0.01 < total}
            onClick={() => onConfirm(payments)}
            className={btnPrimary + " w-full disabled:opacity-40 disabled:cursor-not-allowed"}>
            {payments.length === 0 ? "Fechar sem registar pagamento" : "Confirmar pagamento"}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
