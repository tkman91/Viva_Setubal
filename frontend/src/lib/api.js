import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const api = axios.create({ baseURL: API, withCredentials: true });

export function formatApiError(detail) {
  if (detail == null) return "Ocorreu um erro. Tente novamente.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && e.msg ? e.msg : JSON.stringify(e))).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export function eur(v) {
  return new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" }).format(v || 0);
}

export function num(v) {
  return new Intl.NumberFormat("pt-PT", { maximumFractionDigits: 2 }).format(v || 0);
}

export function fmtMoney(v, cfg) {
  const d = cfg?.decimals ?? 2;
  const sym = cfg?.currency_symbol ?? "€";
  const n = new Intl.NumberFormat("pt-PT", { minimumFractionDigits: d, maximumFractionDigits: d }).format(v || 0);
  return `${n} ${sym}`;
}

export default api;
