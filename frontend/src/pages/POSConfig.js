import { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ZonesTables from "@/components/pos/config/ZonesTables";
import Categories from "@/components/pos/config/Categories";
import Modifiers from "@/components/pos/config/Modifiers";
import Combos from "@/components/pos/config/Combos";
import GeneralConfig from "@/components/pos/config/GeneralConfig";

export default function POSConfig() {
  const [config, setConfig] = useState(null);

  useEffect(() => { api.get("/pos/config").then((r) => setConfig(r.data)); }, []);

  return (
    <div>
      <PageHeader title="Config POS" subtitle="Zonas · menu · pagamentos · talão" />
      <div className="p-4 sm:p-8">
        <Tabs defaultValue="zones">
          <TabsList className="rounded-none flex-wrap h-auto">
            <TabsTrigger data-testid="tab-zones" value="zones" className="rounded-none">Zonas & Mesas</TabsTrigger>
            <TabsTrigger data-testid="tab-categories" value="categories" className="rounded-none">Categorias</TabsTrigger>
            <TabsTrigger data-testid="tab-modifiers" value="modifiers" className="rounded-none">Modificadores</TabsTrigger>
            <TabsTrigger data-testid="tab-combos" value="combos" className="rounded-none">Menus/Combos</TabsTrigger>
            <TabsTrigger data-testid="tab-general" value="general" className="rounded-none">Pagamentos · Talão · Geral</TabsTrigger>
          </TabsList>
          <div className="pt-6">
            <TabsContent value="zones"><ZonesTables /></TabsContent>
            <TabsContent value="categories"><Categories /></TabsContent>
            <TabsContent value="modifiers"><Modifiers config={config} /></TabsContent>
            <TabsContent value="combos"><Combos config={config} /></TabsContent>
            <TabsContent value="general">{config && <GeneralConfig config={config} setConfig={setConfig} />}</TabsContent>
          </div>
        </Tabs>
      </div>
    </div>
  );
}
