import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { toast } from "sonner";
import { MapPin, Crosshair } from "lucide-react";

const field = "w-full px-3 py-2 bg-background border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm";
const btnPrimary = "px-4 py-2 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150";

export default function Settings() {
  const [form, setForm] = useState({ restaurant_name: "", lat: "", lng: "", radius_m: 100 });

  useEffect(() => {
    api.get("/settings").then((r) => { if (r.data && r.data.lat) setForm(r.data); });
  }, []);

  const useMyLocation = () => {
    if (!navigator.geolocation) return toast.error("Geolocalização não suportada");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setForm((f) => ({ ...f, lat: pos.coords.latitude, lng: pos.coords.longitude }));
        toast.success("Coordenadas atuais preenchidas");
      },
      () => toast.error("Não foi possível obter a localização"),
      { enableHighAccuracy: true }
    );
  };

  const save = async (e) => {
    e.preventDefault();
    try {
      await api.put("/settings", {
        restaurant_name: form.restaurant_name,
        lat: Number(form.lat),
        lng: Number(form.lng),
        radius_m: Number(form.radius_m),
      });
      toast.success("Definições guardadas");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  };

  return (
    <div>
      <PageHeader title="Definições" subtitle="Localização do restaurante para picagem de ponto" />
      <div className="p-4 sm:p-8 max-w-xl">
        <form onSubmit={save} className="bg-card border border-border p-6 space-y-4">
          <div className="flex items-center gap-2 text-primary mb-2"><MapPin className="w-5 h-5" /><span className="font-display font-bold tracking-tight text-lg">Localização</span></div>
          <div>
            <label className="label-tech block mb-1">Nome do restaurante</label>
            <input data-testid="input-restaurant-name" required className={field} value={form.restaurant_name} onChange={(e) => setForm({ ...form, restaurant_name: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label-tech block mb-1">Latitude</label><input data-testid="input-lat" required type="number" step="any" className={field} value={form.lat} onChange={(e) => setForm({ ...form, lat: e.target.value })} /></div>
            <div><label className="label-tech block mb-1">Longitude</label><input data-testid="input-lng" required type="number" step="any" className={field} value={form.lng} onChange={(e) => setForm({ ...form, lng: e.target.value })} /></div>
          </div>
          <button type="button" data-testid="btn-use-location" onClick={useMyLocation} className="text-sm border border-border px-3 py-2 hover:bg-secondary transition-colors duration-150 inline-flex items-center gap-2"><Crosshair className="w-4 h-4" /> Usar a minha localização atual</button>
          <div>
            <label className="label-tech block mb-1">Raio permitido (metros)</label>
            <input data-testid="input-radius" required type="number" className={field} value={form.radius_m} onChange={(e) => setForm({ ...form, radius_m: e.target.value })} />
          </div>
          <button data-testid="btn-save-settings" className={btnPrimary + " w-full"}>Guardar definições</button>
        </form>
      </div>
    </div>
  );
}
