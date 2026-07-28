import { useEffect, useState } from "react";
import api, { eur, num } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { Package, Users, Coffee, AlertTriangle, Wallet, Clock, ShoppingCart, Table2 } from "lucide-react";

function Kpi({ label, value, icon: Icon, tone = "primary", testid }) {
  return (
    <div data-testid={testid} className="bg-card border border-border p-6 fade-up">
      <div className="flex items-center justify-between mb-4">
        <div className="label-tech">{label}</div>
        <Icon className={`w-5 h-5 text-${tone}`} style={{ color: `hsl(var(--${tone}))` }} />
      </div>
      <div className="font-display text-4xl sm:text-5xl font-black tracking-tighter leading-none">{value}</div>
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/dashboard").then((r) => setData(r.data)).catch(() => {});
  }, []);

  if (!data) return <div className="p-8 text-muted-foreground">A carregar...</div>;

  return (
    <div>
      <PageHeader title="Painel" subtitle="Visão geral da operação" />
      <div className="p-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-1 bg-border mb-1">
          <Kpi label="Valor de Stock" value={eur(data.stock_value)} icon={Wallet} testid="kpi-stock-value" />
          <Kpi label="Produtos" value={num(data.products_count)} icon={Package} testid="kpi-products" />
          <Kpi label="Staff Ativo" value={num(data.staff_count)} icon={Users} testid="kpi-staff" />
          <Kpi label="A trabalhar agora" value={num(data.active_now)} icon={Clock} testid="kpi-active-now" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-1 bg-border">
          <Kpi label="Vendas Hoje" value={eur(data.today_sales)} icon={ShoppingCart} tone="primary" testid="kpi-sales-today" />
          <Kpi label="Mesas Abertas" value={num(data.open_tables)} icon={Table2} tone="accent" testid="kpi-open-tables" />
          <Kpi label="Consumo Hoje" value={eur(data.today_consumption)} icon={Coffee} tone="accent" testid="kpi-consumo-hoje" />
          <Kpi label="Stock Baixo" value={num(data.low_stock_count)} icon={AlertTriangle} tone="destructive" testid="kpi-low-stock" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-1 bg-border mt-1">
          <div className="lg:col-span-2 bg-card border border-border p-6">
            <div className="label-tech mb-6">Consumo do Staff · últimos 7 dias</div>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={data.trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis dataKey="day" stroke="hsl(var(--muted-foreground))" fontSize={11} fontFamily="IBM Plex Mono" />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} fontFamily="IBM Plex Mono" />
                <Tooltip
                  formatter={(v) => eur(v)}
                  contentStyle={{ borderRadius: 0, border: "1px solid hsl(var(--border))", fontFamily: "IBM Plex Mono", fontSize: 12 }}
                />
                <Bar dataKey="value" fill="hsl(var(--primary))" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-card border border-border p-6">
            <div className="label-tech mb-4 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-destructive" /> Alertas de Stock
            </div>
            {data.low_stock.length === 0 && <p className="text-sm text-muted-foreground">Sem alertas.</p>}
            <div className="space-y-2">
              {data.low_stock.map((p) => (
                <div key={p.id} className="flex items-center justify-between p-2 bg-destructive/10 border border-destructive/30">
                  <span className="text-sm font-medium">{p.name}</span>
                  <span className="mono text-sm text-destructive font-semibold">
                    {num(p.quantity)} / {num(p.min_quantity)} {p.unit}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
