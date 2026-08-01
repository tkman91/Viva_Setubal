import { fmtMoney } from "@/lib/api";

export function buildReceiptHTML(order, config) {
  const r = config?.receipt || {};
  const m = (v) => fmtMoney(v, config);
  const itemsRows = (order.items || [])
    .map((it) => {
      const mods = (it.modifiers || []).length
        ? `<div class="mods">${it.modifiers.map((x) => `+ ${x.name}`).join(", ")}</div>`
        : "";
      return `<tr><td>${it.quantity}× ${it.product_name}${mods}</td><td class="r">${m(it.line_total)}</td></tr>`;
    })
    .join("");
  const vatRows = (order.vat_breakdown || [])
    .map((v) => `<tr><td>IVA ${v.rate}% (base ${m(v.base)})</td><td class="r">${m(v.vat)}</td></tr>`)
    .join("");
  const payRows = (order.payments || [])
    .map((p) => `<tr><td>${p.method}</td><td class="r">${m(p.amount)}</td></tr>`)
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>Talão</title>
  <style>
    *{font-family:'Courier New',monospace;color:#000}
    body{width:280px;margin:0 auto;padding:8px;font-size:12px}
    h1{font-size:15px;text-align:center;margin:0 0 2px}
    .c{text-align:center}.r{text-align:right}
    table{width:100%;border-collapse:collapse}
    td{padding:1px 0;vertical-align:top}
    .mods{font-size:10px;color:#333;padding-left:8px}
    hr{border:none;border-top:1px dashed #000;margin:6px 0}
    .tot{font-size:15px;font-weight:bold}
    .foot{text-align:center;margin-top:8px;font-size:11px}
  </style></head><body>
    <h1>${r.name || "Restaurante"}</h1>
    ${r.address ? `<div class="c">${r.address}</div>` : ""}
    ${r.nif ? `<div class="c">NIF: ${r.nif}</div>` : ""}
    ${r.phone ? `<div class="c">${r.phone}</div>` : ""}
    <hr>
    <div>Mesa: ${order.table_name || "-"}${order.zone_name ? " · " + order.zone_name : ""}</div>
    <div>${new Date(order.closed_at || Date.now()).toLocaleString("pt-PT")}</div>
    <hr>
    <table>${itemsRows}</table>
    <hr>
    <table>
      <tr><td>Subtotal</td><td class="r">${m(order.subtotal)}</td></tr>
      ${order.discount_amount ? `<tr><td>Desconto</td><td class="r">-${m(order.discount_amount)}</td></tr>` : ""}
      ${order.service_charge_amount ? `<tr><td>Serviço</td><td class="r">${m(order.service_charge_amount)}</td></tr>` : ""}
    </table>
    <hr>
    <table class="tot"><tr><td>TOTAL</td><td class="r">${m(order.total)}</td></tr></table>
    <hr>
    <table>${vatRows}</table>
    ${payRows ? `<hr><table>${payRows}${order.change ? `<tr><td>Troco</td><td class="r">${m(order.change)}</td></tr>` : ""}</table>` : ""}
    <div class="foot">${r.footer || ""}</div>
  </body></html>`;
}

export function printReceipt(order, config) {
  const w = window.open("", "_blank", "width=360,height=640");
  if (!w) return;
  w.document.write(buildReceiptHTML(order, config));
  w.document.close();
  w.focus();
  setTimeout(() => {
    w.print();
  }, 300);
}
