import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { fmtMoney } from "@/lib/api";

const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

export default function ModifierPicker({ product, groups, config, onConfirm, onClose }) {
  const productGroups = groups.filter((g) => (product?.modifier_group_ids || []).includes(g.id));
  const [selected, setSelected] = useState({}); // groupId -> [optionId]
  const [qty, setQty] = useState(1);

  const toggle = (group, optId) => {
    setSelected((prev) => {
      const cur = prev[group.id] || [];
      const max = group.max || 1;
      let next;
      if (cur.includes(optId)) next = cur.filter((x) => x !== optId);
      else if (max === 1) next = [optId];
      else next = cur.length < max ? [...cur, optId] : cur;
      return { ...prev, [group.id]: next };
    });
  };

  const confirm = () => {
    const mods = [];
    for (const g of productGroups) {
      for (const optId of selected[g.id] || []) mods.push({ group_id: g.id, option_id: optId });
    }
    onConfirm({ modifiers: mods, quantity: Number(qty) || 1 });
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="rounded-none max-w-md" data-testid="modifier-dialog">
        <DialogHeader><DialogTitle className="font-display tracking-tight">{product?.name}</DialogTitle></DialogHeader>
        <div className="space-y-4 max-h-[60vh] overflow-y-auto">
          {productGroups.map((g) => (
            <div key={g.id}>
              <div className="label-tech mb-2">{g.name}{g.required ? " *" : ""} · máx {g.max}</div>
              <div className="grid grid-cols-2 gap-1">
                {g.options.map((o) => {
                  const on = (selected[g.id] || []).includes(o.id);
                  return (
                    <button key={o.id} data-testid={`mod-opt-${o.id}`} onClick={() => toggle(g, o.id)}
                      className={`px-3 py-2 border text-sm text-left transition-colors duration-150 ${on ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-secondary"}`}>
                      {o.name} {o.price_delta ? <span className="mono text-xs">({o.price_delta > 0 ? "+" : ""}{fmtMoney(o.price_delta, config)})</span> : null}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
          <div className="flex items-center gap-2">
            <span className="label-tech">Qtd</span>
            <input data-testid="modifier-qty" type="number" min="1" step="1" value={qty} onChange={(e) => setQty(e.target.value)}
              className="w-24 px-3 py-2 bg-background border border-input text-sm" />
          </div>
        </div>
        <button data-testid="modifier-confirm" onClick={confirm} className={btnPrimary + " w-full"}>Adicionar</button>
      </DialogContent>
    </Dialog>
  );
}
