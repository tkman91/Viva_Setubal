import { useState } from "react";
import { PageHeader } from "@/components/Layout";
import { useAuth } from "@/context/AuthContext";
import PunchPanel from "@/components/picagem/PunchPanel";
import HorarioTab from "@/components/picagem/HorarioTab";
import CorrecaoTab from "@/components/picagem/CorrecaoTab";

const tabBtn = (active) =>
  `px-4 py-2 text-sm font-semibold border-b-2 whitespace-nowrap transition-colors duration-150 ${
    active ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
  }`;

export default function Picagem() {
  const { canManage } = useAuth();
  const isManager = canManage("picagem");
  const [tab, setTab] = useState("picar");

  return (
    <div>
      <PageHeader title="Picagem de Ponto" subtitle="Validação por geolocalização" />
      <div className="px-4 sm:px-8 pt-4 flex gap-2 border-b border-border overflow-x-auto">
        <button data-testid="tab-picar" className={tabBtn(tab === "picar")} onClick={() => setTab("picar")}>Picar Ponto</button>
        {isManager && <button data-testid="tab-horario" className={tabBtn(tab === "horario")} onClick={() => setTab("horario")}>Horário</button>}
        {isManager && <button data-testid="tab-correcao" className={tabBtn(tab === "correcao")} onClick={() => setTab("correcao")}>Correção de Picagens</button>}
      </div>
      {tab === "picar" && <PunchPanel />}
      {tab === "horario" && isManager && <HorarioTab />}
      {tab === "correcao" && isManager && <CorrecaoTab />}
    </div>
  );
}
