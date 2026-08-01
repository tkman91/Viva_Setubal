# PRD — Gestão de Restaurante

## Problema original
"Cria uma aplicação para um restaurante que possa controlar stock, fazer picagem de pontos com geolocalização, integrar com sistema de faturação e controlar o staff (adicionar, gerir permissões e ver o que consomem)."

## Escolhas do utilizador
- Autenticação: login local (utilizador/password) — JWT Bearer.
- Faturação: apenas estrutura preparada para integrar depois.
- Picagem: definir localização do restaurante e validar por raio (haversine).
- Consumo do staff: refeições/produtos + valor associado.
- Idioma/moeda: Português (PT) + Euro (€).

## Arquitetura
- Backend: FastAPI + MongoDB (motor). Rotas sob `/api`. Auth JWT (bcrypt). `require_permission(module)` e `require_admin`.
- Frontend: React 19 + Tailwind (tema "Swiss Culinary Brutalism"), Recharts, sonner, shadcn/ui.
- Roles: admin, gestor, funcionario. Módulos: stock, picagem, consumo, staff, faturacao, relatorios.

## Personas
- Gestor/Admin: gere stock, staff, permissões, faturação, definições, vê tudo.
- Funcionário: pica ponto, regista/consulta o próprio consumo, acesso conforme permissões.

## Implementado (2026-07-25)
- Auth local por **cookie httpOnly** (secure/samesite configuráveis por env — HTTPS Emergent, HTTP self-host) + seed admin.
- **Modelo de permissões**: só `admin` tem tudo automaticamente; `gestor`/`funcionario` só têm o que o admin atribui por módulo. Gestão de staff e Definições = admin-only. `can_manage` dá visão de supervisão (ver todos os registos) a admin e a gestor com a permissão do módulo. Despromover de admin sem enviar permissões limpa as residuais.
- **Registadora (POS)** (substituiu Faturação): mesas abertas; cada item adicionado desconta do stock, remover devolve; fechar conta regista venda (status paga). Dashboard mostra Vendas Hoje e Mesas Abertas.
- Painel com KPIs (valor stock, produtos, staff, ativos agora, consumo hoje/total, stock baixo) + gráfico consumo 7 dias.
- Controlo de Stock: CRUD produtos, movimentos entrada/saída, alertas de stock baixo.
- Picagem de Ponto: geolocalização com validação de raio, radar animado, entrada/saída, histórico.
- Gestão de Staff: adicionar/editar/eliminar, definir role, salário/hora, permissões por módulo.
- Consumo Staff: registo com desconto de stock e valor; agregação por funcionário.
- Faturação: criar faturas com linhas/IVA (23/13/6/0%), totais, nº sequencial, "Emitir" (sync simulado — INTEGRAÇÃO EXTERNA POR LIGAR).
- Definições: localização do restaurante + raio.

## Versão Mobile (2026-08-01)
- **Navegação mobile**: top bar (`lg:hidden`) com botão hambúrguer → gaveta lateral (Sheet) com todos os módulos permitidos; sidebar desktop mantém-se (`hidden lg:flex`). Toque num item navega e fecha a gaveta.
- **PageHeader responsivo**: empilha no mobile (`flex-col sm:flex-row`), fica sticky abaixo da top bar (`top-14 lg:top-0`), data escondida em ecrãs pequenos.
- **Registadora no telemóvel**: diálogo da conta em ecrã dividido (menu em cima / conta em baixo, cada um com scroll), largura `96vw`; pagamento e modificadores usáveis a 390px.
- **Padding responsivo** em todas as páginas (`p-4 sm:p-8`); Login já colapsa para coluna única no mobile.
- Testado em viewport 390×844 (iPhone): 100% dos fluxos PASS (gaveta, Picagem, POS, Relatórios, Stock).
- Backlog a11y (dev-only): adicionar DialogDescription a alguns diálogos (avisos Radix não-fatais, só em modo dev).

## POS Configurável (2026-08-01)
- **Config POS** (nova página admin, `/config-pos`): tabs Zonas&Mesas, Categorias, Modificadores, Menus/Combos, Pagamentos·Talão·Geral.
- **Zonas & Mesas**: CRUD zonas (Sala/Esplanada/Balcão), mesas por zona (nome, lugares), criação em série (bulk).
- **Categorias**: CRUD com cor; produtos associam-se por `category_id`; botões de categoria no POS.
- **Modificadores**: grupos (min/max/obrigatório) + opções com `price_delta`; associados a produtos no Stock; escolhidos no POS via ModifierPicker.
- **Menus/Combos**: preço fixo, IVA próprio, componentes que descontam stock.
- **Config geral** (`pos_config` singleton): métodos de pagamento (Dinheiro/Multibanco/MB Way, editáveis), taxa de serviço %, IVA padrão, cabeçalho do talão (nome/NIF/morada/tel/rodapé), símbolo de moeda, casas decimais, arredondamento (nenhum/0,05/0,10), controlo de stock por defeito.
- **Registadora redesenhada**: tabs de zona → grelha de mesas (livre/ocupada c/ total), mesa avulsa/take-away, menu por categorias + combos, desconto (%/€), taxa de serviço, breakdown de IVA por taxa, dividir pagamento por métodos com troco, talão imprimível (janela de impressão → PDF do browser).
- **Produtos** estendidos: `category_id`, `vat_rate`, `track_stock`, `modifier_group_ids`.
- Endpoints: `/api/pos/config`, `/api/pos/zones`, `/api/pos/tables` (+bulk), `/api/pos/categories`, `/api/pos/modifier-groups`, `/api/pos/combos`; orders com `kind`(product/combo), modifiers, PATCH desconto/serviço, close com `payments`.
- Validado por curl: IVA (3,00€=2,44 base+0,56 IVA23%), pagamento/troco, desconto 10%, modificador soma preço, combo desconta componentes.

## Extensões POS (2026-08-01, parte 2)
- **Editar produtos**: Stock com botão editar (btn-edit-product) → PUT /products (categoria/IVA/stock/modificadores).
- **Cancelamento com registo**: POST /orders/{id}/cancel {reason} → soft-cancel (status='cancelada', cancel_reason, cancelled_by), devolve stock; DELETE /orders passou a admin-only (hard delete).
- **Relatórios POS** (`/relatorios`, módulo relatorios): GET /reports/pos?from&to → KPIs (vendas, contas, ticket médio, canceladas), gráfico por dia, por zona, por método, IVA liquidado.
- **Talão/Fatura em PDF** (servidor, reportlab): GET /orders/{id}/receipt.pdf — talão 80mm com cabeçalho, itens+modificadores, IVA, pagamentos, troco, nº fatura. Botões Imprimir/PDF/Emitir fatura no recibo.
- **Faturação configurável**: pos_config com invoice_provider (none/invoicexpress/moloni/outro), invoice_enabled, invoice_account, invoice_api_key (mascarada — nunca devolvida em plaintext; invoice_api_key_set bool). POST /orders/{id}/invoice gera nº sequencial FT ano/n — **SIMULADO** até ligar API key real do fornecedor.
- Validado: backend 105/105 pytest, frontend 100%. PDF renderizado e confirmado visualmente.

## Estado / testes

## Backlog / próximos passos
- P1: Integração real de faturação (InvoiceXpress/Moloni) — atualmente sync é simulado.
- P1: Relatórios (módulo "relatorios") — horas trabalhadas por funcionário + custo salarial, exportação.
- P2: Multi-restaurante / seleção de loja; PDF de faturas; validação de intervalo lat/lng.
- P2: Remover dica de credenciais no ecrã de login para produção.
