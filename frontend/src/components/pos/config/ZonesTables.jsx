import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Layers, MapPin } from "lucide-react";

const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btn = "px-3 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

export default function ZonesTables() {
  const [zones, setZones] = useState([]);
  const [tables, setTables] = useState([]);
  const [zoneName, setZoneName] = useState("");
  const [bulk, setBulk] = useState({ zone_id: "", count: 4, prefix: "Mesa" });

  const load = useCallback(async () => {
    const [z, t] = await Promise.all([api.get("/pos/zones"), api.get("/pos/tables")]);
    setZones(z.data); setTables(t.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const addZone = async (e) => {
    e.preventDefault();
    try { await api.post("/pos/zones", { name: zoneName, order: zones.length }); setZoneName(""); load(); toast.success("Zona criada"); }
    catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };
  const delZone = async (id) => { await api.delete(`/pos/zones/${id}`); load(); toast.success("Zona e mesas removidas"); };

  const addTable = async (zoneId) => {
    try { await api.post("/pos/tables", { name: `Mesa ${tables.length + 1}`, zone_id: zoneId, seats: 4, order: tables.length }); load(); }
    catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };
  const addBulk = async (e) => {
    e.preventDefault();
    if (!bulk.zone_id) return toast.error("Escolhe uma zona");
    try {
      await api.post(`/pos/tables/bulk?zone_id=${bulk.zone_id}&count=${bulk.count}&prefix=${encodeURIComponent(bulk.prefix)}`);
      load(); toast.success(`${bulk.count} mesas criadas`);
    } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
  };
  const delTable = async (id) => { await api.delete(`/pos/tables/${id}`); load(); };
  const saveTable = async (t, patch) => { await api.put(`/pos/tables/${t.id}`, { ...t, ...patch }); load(); };

  return (
    <div className="space-y-6">
      <form onSubmit={addZone} className="flex gap-2">
        <input data-testid="input-zone-name" required placeholder="Nova zona (ex: Esplanada)" className={field} value={zoneName} onChange={(e) => setZoneName(e.target.value)} />
        <button data-testid="btn-add-zone" className={btn}><Plus className="w-4 h-4" /></button>
      </form>

      <form onSubmit={addBulk} className="flex flex-wrap items-end gap-2 border border-border p-3">
        <div><label className="label-tech block">Zona</label>
          <select data-testid="bulk-zone" className={field} value={bulk.zone_id} onChange={(e) => setBulk({ ...bulk, zone_id: e.target.value })}>
            <option value="">Selecionar...</option>
            {zones.map((z) => <option key={z.id} value={z.id}>{z.name}</option>)}
          </select>
        </div>
        <div><label className="label-tech block">Nº mesas</label><input data-testid="bulk-count" type="number" min="1" className={field + " w-24"} value={bulk.count} onChange={(e) => setBulk({ ...bulk, count: Number(e.target.value) })} /></div>
        <div><label className="label-tech block">Prefixo</label><input className={field + " w-28"} value={bulk.prefix} onChange={(e) => setBulk({ ...bulk, prefix: e.target.value })} /></div>
        <button data-testid="btn-bulk-tables" className={btn}>Criar em série</button>
      </form>

      {zones.map((z) => (
        <div key={z.id} className="border border-border">
          <div className="flex items-center justify-between px-4 py-3 bg-secondary/50">
            <div className="flex items-center gap-2 font-display font-bold tracking-tight"><Layers className="w-4 h-4 text-primary" /> {z.name}</div>
            <div className="flex items-center gap-2">
              <button data-testid={`btn-add-table-${z.id}`} onClick={() => addTable(z.id)} className="text-sm border border-border px-2 py-1 hover:bg-secondary"><Plus className="w-3.5 h-3.5 inline" /> mesa</button>
              <button data-testid={`btn-del-zone-${z.id}`} onClick={() => delZone(z.id)} className="text-destructive"><Trash2 className="w-4 h-4" /></button>
            </div>
          </div>
          <div className="p-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
            {tables.filter((t) => t.zone_id === z.id).map((t) => (
              <div key={t.id} data-testid={`table-item-${t.id}`} className="border border-border p-2 space-y-1">
                <input className="w-full bg-background border border-input px-2 py-1 text-sm" defaultValue={t.name} onBlur={(e) => e.target.value !== t.name && saveTable(t, { name: e.target.value })} />
                <div className="flex items-center gap-1">
                  <input type="number" min="1" className="w-16 bg-background border border-input px-2 py-1 text-xs mono" defaultValue={t.seats} onBlur={(e) => Number(e.target.value) !== t.seats && saveTable(t, { seats: Number(e.target.value) })} />
                  <span className="label-tech" style={{ fontSize: "0.55rem" }}>lug.</span>
                  <button onClick={() => delTable(t.id)} className="ml-auto text-destructive"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
      {zones.length === 0 && <p className="text-sm text-muted-foreground flex items-center gap-2"><MapPin className="w-4 h-4" /> Cria a primeira zona para organizar as mesas.</p>}
    </div>
  );
}
