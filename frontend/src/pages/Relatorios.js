import { useEffect, useState, useCallback } from "react";
import api, { fmtMoney } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Euro, ShoppingBag, TrendingUp, XCircle, Clock, Download } from "lucide-react";

const field = "px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";

export default function Relatorios() {
  const [config, setConfig] = useState(null);
  const iso = (d) => d.toISOString().slice(0, 10);
  const [range, setRange] = useState({ from: iso(new Date(Date.now() - 29 * 864e5)), to: iso(new Date()) });
  const [data, setData] = useState(null);
  const [hours, setHours] = useState(null);
  const m = (v) => fmtMoney(v, config);

  const load = useCallback(async () => {
    const { data } = await api.get(`/reports/pos?from=${range.from}&to=${range.to}`);
    setData(data);
    try {
      const h = await api.get(`/reports/hours?from=${range.from}&to=${range.to}`);
      setHours(h.data);
    } catch (e) { setHours(null); }
  }, [range]);

  const exportCSV = () => {
    if (!hours) return;
    const rows = [["Funcionário", "Horas", "€/hora", "Custo (€)"], ...hours.items.map((i) => [i.user_name, i.hours, i.hourly_wage, i.cost])];
    rows.push(["TOTAL", hours.total_hours, "", hours.total_cost]);
    const csv = rows.map((r) => r.join(";")).join("\n");
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `horas_${range.from}_${range.to}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  useEffect(() => { api.get("/pos/config").then((r) => setConfig(r.data)); }, []);
  useEffect(() => { load(); }, [load]);

  const kpis = data ? [
    { label: "Vendas", value: m(data.total_sales), icon: Euro },
    { label: "Contas", value: data.order_count, icon: ShoppingBag },
    { label: "Ticket médio", value: m(data.avg_ticket), icon: TrendingUp },
    { label: "Canceladas", value: data.cancelled_count, icon: XCircle },
  ] : [];

  return (
    <div>
      <PageHeader title="Relatórios" subtitle="Vendas por zona, método e período">
        <div className="flex items-end gap-2">
          <div><label className="label-tech block">De</label><input data-testid="report-from" type="date" className={field} value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })} /></div>
          <div><label className="label-tech block">Até</label><input data-testid="report-to" type="date" className={field} value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} /></div>
        </div>
      </PageHeader>

      <div className="p-4 sm:p-8 space-y-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-1 bg-border">
          {kpis.map((k) => {
            const Icon = k.icon;
            return (
              <div key={k.label} data-testid={`kpi-${k.label}`} className="bg-card p-6">
                <div className="flex items-center gap-2 label-tech mb-2"><Icon className="w-4 h-4 text-primary" /> {k.label}</div>
                <div className="font-display text-3xl font-black tracking-tighter mono">{k.value}</div>
              </div>
            );
          })}
        </div>

        <div className="grid lg:grid-cols-2 gap-1 bg-border">
          <div className="bg-card p-6">
            <div className="label-tech mb-4">Vendas por dia</div>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={data?.by_day || []}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v) => m(v)} />
                <Bar dataKey="total" fill="var(--primary, #14532d)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="bg-card p-6 space-y-6">
            <div>
              <div className="label-tech mb-2">Por zona</div>
              {(data?.by_zone || []).map((z) => (
                <div key={z.zone} data-testid={`zone-total-${z.zone}`} className="flex justify-between text-sm py-1 border-b border-border"><span>{z.zone}</span><span className="mono font-semibold">{m(z.total)}</span></div>
              ))}
              {(!data?.by_zone?.length) && <p className="text-sm text-muted-foreground">Sem dados no período.</p>}
            </div>
            <div>
              <div className="label-tech mb-2">Por método de pagamento</div>
              {(data?.by_method || []).map((p) => (
                <div key={p.method} data-testid={`method-total-${p.method}`} className="flex justify-between text-sm py-1 border-b border-border"><span>{p.method}</span><span className="mono font-semibold">{m(p.total)}</span></div>
              ))}
              {(!data?.by_method?.length) && <p className="text-sm text-muted-foreground">Sem pagamentos registados.</p>}
            </div>
            <div>
              <div className="label-tech mb-2">IVA liquidado</div>
              {(data?.by_vat || []).map((v) => (
                <div key={v.rate} className="flex justify-between text-sm py-1 border-b border-border"><span>IVA {v.rate}%</span><span className="mono font-semibold">{m(v.vat)}</span></div>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-card border border-border p-6">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
            <div className="label-tech flex items-center gap-2"><Clock className="w-4 h-4 text-primary" /> Horas trabalhadas & custo salarial</div>
            <button data-testid="btn-export-hours" onClick={exportCSV} disabled={!hours?.items?.length} className="text-sm border border-border px-3 py-2 hover:bg-secondary transition-colors duration-150 inline-flex items-center gap-2 disabled:opacity-50"><Download className="w-4 h-4" /> Exportar CSV</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border label-tech text-left">
                  <th className="px-3 py-2">Funcionário</th>
                  <th className="px-3 py-2 text-right">Horas</th>
                  <th className="px-3 py-2 text-right">€/hora</th>
                  <th className="px-3 py-2 text-right">Custo</th>
                </tr>
              </thead>
              <tbody>
                {(hours?.items || []).map((i) => (
                  <tr key={i.user_id} data-testid={`hours-row-${i.user_id}`} className="border-b border-border">
                    <td className="px-3 py-2 font-medium">{i.user_name}</td>
                    <td className="px-3 py-2 text-right mono">{i.hours.toFixed(2)}h</td>
                    <td className="px-3 py-2 text-right mono">{m(i.hourly_wage)}</td>
                    <td className="px-3 py-2 text-right mono font-semibold">{m(i.cost)}</td>
                  </tr>
                ))}
                {(!hours?.items?.length) && <tr><td colSpan={4} className="px-3 py-8 text-center text-muted-foreground">Sem horas no período.</td></tr>}
              </tbody>
              {hours?.items?.length ? (
                <tfoot>
                  <tr className="border-t-2 border-border font-semibold">
                    <td className="px-3 py-2">Total</td>
                    <td data-testid="hours-total" className="px-3 py-2 text-right mono">{hours.total_hours.toFixed(2)}h</td>
                    <td></td>
                    <td data-testid="cost-total" className="px-3 py-2 text-right mono">{m(hours.total_cost)}</td>
                  </tr>
                </tfoot>
              ) : null}
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
