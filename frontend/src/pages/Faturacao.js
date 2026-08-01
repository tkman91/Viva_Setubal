import { useEffect, useState, useCallback } from "react";
import api, { fmtMoney, num, formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Plus, Trash2, Table2, Utensils, Printer, Percent, ConciergeBell, FileText, Download } from "lucide-react";
import ModifierPicker from "@/components/pos/ModifierPicker";
import PaymentDialog from "@/components/pos/PaymentDialog";
import { printReceipt } from "@/components/pos/receipt";

const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";
const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";

export default function Registadora() {
  const [config, setConfig] = useState(null);
  const [zones, setZones] = useState([]);
  const [tables, setTables] = useState([]);
  const [products, setProducts] = useState([]);
  const [combos, setCombos] = useState([]);
  const [groups, setGroups] = useState([]);
  const [categories, setCategories] = useState([]);
  const [openOrders, setOpenOrders] = useState([]);
  const [activeZone, setActiveZone] = useState("all");
  const [selected, setSelected] = useState(null);
  const [modProduct, setModProduct] = useState(null);
  const [payOpen, setPayOpen] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [walkName, setWalkName] = useState("");
  const [activeCat, setActiveCat] = useState("all");
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");

  const m = useCallback((v) => fmtMoney(v, config), [config]);

  const loadOrders = useCallback(async () => {
    const { data } = await api.get("/orders?status=aberta");
    setOpenOrders(data);
    return data;
  }, []);

  useEffect(() => {
    (async () => {
      const [cfg, z, t, p, c, g, cat, o] = await Promise.all([
        api.get("/pos/config"), api.get("/pos/zones"), api.get("/pos/tables"),
        api.get("/products"), api.get("/pos/combos"), api.get("/pos/modifier-groups"),
        api.get("/pos/categories"), api.get("/orders?status=aberta"),
      ]);
      setConfig(cfg.data); setZones(z.data); setTables(t.data); setProducts(p.data);
      setCombos(c.data.filter((x) => x.active !== false)); setGroups(g.data);
      setCategories(cat.data); setOpenOrders(o.data);
    })().catch(() => toast.error("Falha ao carregar POS"));
  }, []);

  const orderForTable = (tableId) => openOrders.find((o) => o.table_id === tableId);

  const openTable = async (table) => {
    try {
      const { data } = await api.post("/orders", { table_id: table.id });
      await loadOrders();
      setSelected(data);
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const openWalkIn = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/orders", { table_name: walkName });
      setWalkName("");
      await loadOrders();
      setSelected(data);
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const refresh = async (id) => {
    const list = await loadOrders();
    setSelected(list.find((x) => x.id === id) || null);
  };

  const addProduct = async (product) => {
    if ((product.modifier_group_ids || []).length > 0) { setModProduct(product); return; }
    await doAdd({ kind: "product", ref_id: product.id, quantity: 1 });
  };

  const doAdd = async (payload) => {
    try {
      const { data } = await api.post(`/orders/${selected.id}/items`, payload);
      setSelected(data);
      loadOrders();
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const addCombo = (combo) => doAdd({ kind: "combo", ref_id: combo.id, quantity: 1 });

  const removeItem = async (itemId) => {
    try {
      const { data } = await api.delete(`/orders/${selected.id}/items/${itemId}`);
      setSelected(data);
      loadOrders();
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const patchOrder = async (patch) => {
    try {
      const { data } = await api.patch(`/orders/${selected.id}`, patch);
      setSelected(data);
      loadOrders();
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const cancelOrder = async () => {
    try {
      await api.post(`/orders/${selected.id}/cancel`, { reason: cancelReason });
      toast.success("Mesa cancelada · stock devolvido");
      setCancelOpen(false); setCancelReason("");
      setSelected(null);
      loadOrders();
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const emitInvoice = async () => {
    try {
      const { data } = await api.post(`/orders/${receipt.id}/invoice`);
      setReceipt((r) => ({ ...r, invoice: data }));
      toast.success(`Fatura emitida: ${data.number}`);
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const openPdf = () => window.open(`${process.env.REACT_APP_BACKEND_URL}/api/orders/${receipt.id}/receipt.pdf`, "_blank");

  const confirmPayment = async (payments) => {
    try {
      const { data } = await api.post(`/orders/${selected.id}/close`, { payments });
      setPayOpen(false);
      setSelected(null);
      setReceipt(data);
      loadOrders();
      toast.success(`Conta fechada · ${m(data.total)}`);
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };

  const shownTables = tables.filter((t) => activeZone === "all" || t.zone_id === activeZone);
  const shownProducts = products.filter((p) => activeCat === "all" || p.category_id === activeCat);

  if (!config) return <div className="p-4 sm:p-8 text-muted-foreground">A carregar...</div>;

  return (
    <div>
      <PageHeader title="Registadora" subtitle="Zonas · mesas · IVA · pagamento">
        <form onSubmit={openWalkIn} className="flex items-center gap-2">
          <input data-testid="input-walkin" placeholder="Mesa avulsa / take-away" value={walkName} onChange={(e) => setWalkName(e.target.value)} className={field + " w-40 sm:w-48"} />
          <button data-testid="btn-open-walkin" className={btnPrimary}><Plus className="w-4 h-4 inline mr-1" />Abrir</button>
        </form>
      </PageHeader>

      <div className="p-4 sm:p-8 space-y-4">
        <div className="flex flex-wrap gap-1">
          <button data-testid="zone-all" onClick={() => setActiveZone("all")} className={`px-4 py-2 text-sm font-semibold border ${activeZone === "all" ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-secondary"}`}>Todas</button>
          {zones.map((z) => (
            <button key={z.id} data-testid={`zone-${z.id}`} onClick={() => setActiveZone(z.id)} className={`px-4 py-2 text-sm font-semibold border ${activeZone === z.id ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-secondary"}`}>{z.name}</button>
          ))}
        </div>

        {tables.length === 0 && openOrders.filter((o) => !o.table_id).length === 0 && (
          <div className="text-center text-muted-foreground py-16 border border-dashed border-border">
            <Table2 className="w-10 h-10 mx-auto mb-3" /> Sem mesas configuradas. Cria zonas e mesas em <span className="font-semibold">Config POS</span>, ou abre uma mesa avulsa acima.
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-1 bg-border">
          {shownTables.map((t) => {
            const o = orderForTable(t.id);
            return (
              <button key={t.id} data-testid={`table-card-${t.id}`} onClick={() => openTable(t)}
                className={`p-5 text-left transition-colors duration-150 ${o ? "bg-accent text-accent-foreground" : "bg-card hover:bg-secondary"}`}>
                <div className="flex items-center gap-2 font-display text-lg font-bold tracking-tight"><Utensils className="w-4 h-4" /> {t.name}</div>
                <div className="label-tech" style={{ fontSize: "0.6rem" }}>{t.seats} lug.</div>
                {o ? <div className="font-display text-2xl font-black tracking-tighter mono mt-1">{m(o.total)}</div> : <div className="text-xs text-muted-foreground mt-1">livre</div>}
              </button>
            );
          })}
          {activeZone === "all" && openOrders.filter((o) => !o.table_id).map((o) => (
            <button key={o.id} data-testid={`walkin-card-${o.id}`} onClick={() => setSelected(o)} className="p-5 text-left bg-accent text-accent-foreground">
              <div className="flex items-center gap-2 font-display text-lg font-bold tracking-tight"><Utensils className="w-4 h-4" /> {o.table_name}</div>
              <div className="label-tech" style={{ fontSize: "0.6rem" }}>avulsa</div>
              <div className="font-display text-2xl font-black tracking-tighter mono mt-1">{m(o.total)}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Painel da encomenda */}
      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="rounded-none max-w-5xl max-h-[92vh] overflow-hidden p-0">
          <div className="grid grid-cols-1 lg:grid-cols-2 h-[92vh]">
            {/* Menu */}
            <div className="border-r border-border flex flex-col min-h-0">
              <div className="p-4 border-b border-border flex flex-wrap gap-1">
                <button onClick={() => setActiveCat("all")} className={`px-3 py-1.5 text-xs font-semibold border ${activeCat === "all" ? "bg-primary text-primary-foreground border-primary" : "border-border"}`}>Todos</button>
                {categories.map((c) => (
                  <button key={c.id} data-testid={`cat-${c.id}`} onClick={() => setActiveCat(c.id)} className={`px-3 py-1.5 text-xs font-semibold border ${activeCat === c.id ? "text-white border-transparent" : "border-border"}`} style={activeCat === c.id ? { backgroundColor: c.color } : {}}>{c.name}</button>
                ))}
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-1">
                  {shownProducts.map((p) => (
                    <button key={p.id} data-testid={`pos-product-${p.id}`} disabled={p.track_stock !== false && p.quantity <= 0} onClick={() => addProduct(p)}
                      className="border border-border p-3 text-left hover:bg-secondary transition-colors duration-150 disabled:opacity-40">
                      <div className="text-sm font-semibold leading-tight">{p.name}</div>
                      <div className="mono text-xs mt-1">{m(p.sale_price)}</div>
                      {p.track_stock !== false && <div className="label-tech" style={{ fontSize: "0.55rem" }}>stock {num(p.quantity)}</div>}
                    </button>
                  ))}
                </div>
                {combos.length > 0 && (
                  <>
                    <div className="label-tech mt-4 mb-2">Menus / Combos</div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-1">
                      {combos.map((c) => (
                        <button key={c.id} data-testid={`pos-combo-${c.id}`} onClick={() => addCombo(c)} className="border border-primary p-3 text-left hover:bg-secondary transition-colors duration-150">
                          <div className="text-sm font-semibold leading-tight">{c.name}</div>
                          <div className="mono text-xs mt-1">{m(c.price)}</div>
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Conta */}
            <div className="flex flex-col min-h-0 basis-1/2 lg:basis-auto">
              <DialogHeader className="p-4 border-b border-border">
                <DialogTitle className="font-display tracking-tight flex items-center gap-2">
                  <Utensils className="w-5 h-5 text-primary" /> {selected?.table_name}{selected?.zone_name ? ` · ${selected.zone_name}` : ""}
                </DialogTitle>
              </DialogHeader>
              <div className="flex-1 overflow-y-auto p-4 space-y-1">
                {selected?.items?.length === 0 && <p className="text-sm text-muted-foreground">Sem itens. Toca em produtos à esquerda.</p>}
                {selected?.items?.map((it) => (
                  <div key={it.id} data-testid={`order-item-${it.id}`} className="flex items-start justify-between py-2 border-b border-border text-sm">
                    <div>
                      <div><span className="mono">{num(it.quantity)}×</span> {it.product_name}</div>
                      {(it.modifiers || []).length > 0 && <div className="text-xs text-muted-foreground pl-4">{it.modifiers.map((x) => x.name).join(", ")}</div>}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="mono font-semibold">{m(it.line_total)}</span>
                      <button data-testid={`btn-remove-item-${it.id}`} onClick={() => removeItem(it.id)} className="text-destructive hover:opacity-70"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Ajustes + totais */}
              <div className="border-t border-border p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Percent className="w-4 h-4 text-muted-foreground" />
                  <select data-testid="discount-type" value={selected?.discount_type || "none"} onChange={(e) => patchOrder({ discount_type: e.target.value, discount_value: selected?.discount_value || 0 })} className="px-2 py-1.5 bg-background border border-input text-sm">
                    <option value="none">Sem desconto</option>
                    <option value="percent">Desconto %</option>
                    <option value="fixed">Desconto €</option>
                  </select>
                  {selected?.discount_type !== "none" && (
                    <input data-testid="discount-value" type="number" step="any" min="0" value={selected?.discount_value || 0}
                      onChange={(e) => patchOrder({ discount_type: selected.discount_type, discount_value: Number(e.target.value) })}
                      className="w-24 px-2 py-1.5 bg-background border border-input text-sm mono" />
                  )}
                  {config.service_charge_percent > 0 && (
                    <button data-testid="toggle-service" onClick={() => patchOrder({ service_charge_enabled: !selected?.service_charge_enabled })}
                      className={`ml-auto px-2 py-1.5 border text-xs font-semibold flex items-center gap-1 ${selected?.service_charge_enabled ? "bg-primary text-primary-foreground border-primary" : "border-border"}`}>
                      <ConciergeBell className="w-3.5 h-3.5" /> Serviço {config.service_charge_percent}%
                    </button>
                  )}
                </div>

                <div className="text-sm space-y-0.5">
                  <div className="flex justify-between text-muted-foreground"><span>Subtotal</span><span className="mono">{m(selected?.subtotal)}</span></div>
                  {selected?.discount_amount > 0 && <div className="flex justify-between text-muted-foreground"><span>Desconto</span><span className="mono">-{m(selected?.discount_amount)}</span></div>}
                  {selected?.service_charge_amount > 0 && <div className="flex justify-between text-muted-foreground"><span>Serviço</span><span className="mono">{m(selected?.service_charge_amount)}</span></div>}
                  {(selected?.vat_breakdown || []).map((v) => (
                    <div key={v.rate} className="flex justify-between text-muted-foreground" style={{ fontSize: "0.7rem" }}><span>IVA {v.rate}%</span><span className="mono">{m(v.vat)}</span></div>
                  ))}
                </div>

                <div className="flex items-center justify-between">
                  <span className="label-tech">Total</span>
                  <span data-testid="order-total" className="font-display text-4xl font-black tracking-tighter mono">{m(selected?.total)}</span>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <button data-testid="btn-cancel-order" onClick={() => setCancelOpen(true)} className="py-2.5 border border-destructive text-destructive font-semibold text-sm hover:bg-destructive/10 transition-colors duration-150">Cancelar mesa</button>
                  <button data-testid="btn-pay" disabled={!selected?.items?.length} onClick={() => setPayOpen(true)} className={btnPrimary + " disabled:opacity-40"}>Pagar</button>
                </div>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {modProduct && (
        <ModifierPicker product={modProduct} groups={groups} config={config}
          onConfirm={({ modifiers, quantity }) => { doAdd({ kind: "product", ref_id: modProduct.id, quantity, modifiers }); setModProduct(null); }}
          onClose={() => setModProduct(null)} />
      )}

      {payOpen && selected && (
        <PaymentDialog order={selected} config={config} onConfirm={confirmPayment} onClose={() => setPayOpen(false)} />
      )}

      {/* Cancelar mesa */}
      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent className="rounded-none max-w-sm" data-testid="cancel-dialog">
          <DialogHeader><DialogTitle className="font-display tracking-tight">Cancelar mesa</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">O stock é devolvido e a conta fica registada como cancelada (para auditoria).</p>
            <input data-testid="cancel-reason" placeholder="Motivo (opcional)" className={field} value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} />
            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => setCancelOpen(false)} className="py-2.5 border border-border font-semibold text-sm hover:bg-secondary transition-colors duration-150">Voltar</button>
              <button data-testid="btn-confirm-cancel" onClick={cancelOrder} className="py-2.5 bg-destructive text-destructive-foreground font-semibold text-sm hover:opacity-90 transition-opacity duration-150">Confirmar</button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Recibo */}
      <Dialog open={!!receipt} onOpenChange={(o) => !o && setReceipt(null)}>
        <DialogContent className="rounded-none max-w-sm" data-testid="receipt-dialog">
          <DialogHeader><DialogTitle className="font-display tracking-tight">Conta fechada</DialogTitle></DialogHeader>
          {receipt && (
            <div className="space-y-3">
              <div className="text-center">
                <div className="label-tech">Total</div>
                <div className="font-display text-5xl font-black tracking-tighter mono">{m(receipt.total)}</div>
                {receipt.change > 0 && <div className="text-sm text-muted-foreground">Troco: <span className="mono">{m(receipt.change)}</span></div>}
                {receipt.invoice && <div className="text-sm mt-1">Fatura: <span className="mono font-semibold">{receipt.invoice.number}</span></div>}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button data-testid="btn-print-receipt" onClick={() => printReceipt(receipt, config)} className="py-2.5 border border-border font-semibold text-sm hover:bg-secondary transition-colors duration-150 flex items-center justify-center gap-2"><Printer className="w-4 h-4" /> Imprimir</button>
                <button data-testid="btn-pdf-receipt" onClick={openPdf} className="py-2.5 border border-border font-semibold text-sm hover:bg-secondary transition-colors duration-150 flex items-center justify-center gap-2"><Download className="w-4 h-4" /> PDF</button>
              </div>
              {config.invoice_enabled && !receipt.invoice && (
                <button data-testid="btn-emit-invoice" onClick={emitInvoice} className={btnPrimary + " w-full flex items-center justify-center gap-2"}><FileText className="w-4 h-4" /> Emitir fatura</button>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
