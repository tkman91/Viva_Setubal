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

## PWA — App instalável (2026-08-01)
- `public/manifest.json` (name, short_name, standalone, theme #14532d, ícones 192/512/maskable), `public/sw.js` (service worker network-first, seguro em dev e produção: salta `/api` e HMR), ícones gerados (fork/knife em verde) + favicon.
- `index.html`: link manifest, apple-touch-icon, theme-color, apple/mobile web-app-capable, `viewport-fit=cover`.
- `index.js`: regista o service worker (requer HTTPS — já garantido via DuckDNS).
- Instalável no telemóvel ("Adicionar ao ecrã principal") → abre em ecrã cheio. Verificado: todos os assets servidos 200.
- Nota: offline completo fica melhor com `yarn build` servido pelo Nginx; em `yarn start` funciona (instalável + fallback offline via network-first).

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

## Cargos / RBAC dinâmico (2026-08-02)
- **Coleção `roles`**: `{id, name, modules[], is_admin, is_supervisor, is_system, created_at}`. Permissões dos utilizadores derivam SEMPRE do cargo (`role_id`), re-avaliadas a cada pedido via `enrich_role()` (fonte de verdade — não vão no JWT).
- **Cargo "Administrador"** (is_system=true): acesso total, **não pode ser editado nem eliminado** (403). Só alterável no código.
- **Migração automática no arranque**: "admin"→Administrador; "gestor"→cargo Gestor (is_supervisor); "funcionario"→cargo Funcionário. Remove campo `permissions` legado dos utilizadores.
- **Endpoints**: `GET /api/roles` (auth), `POST/PUT/DELETE /api/roles` (admin). Delete bloqueado se cargo em uso (400) ou de sistema (403). Nome duplicado (400).
- **Staff**: `POST/PUT /api/staff` usam `role_id` (removido `role`/`permissions` do input). `list_staff` enriquece cada funcionário com nome do cargo + módulos.
- **Frontend**: nova página `/cargos` (admin-only, `Cargos.js`) — CRUD de cargos com seleção de módulos + toggle supervisão; cargo de sistema mostrado como protegido (sem botões). `Staff.js` passa a usar dropdown de cargo dinâmico com pré-visualização dos módulos. `AuthContext` usa `user.is_admin`/`is_supervisor`. Confirmação nativa ao eliminar cargo.
- **Bug corrigido**: resposta de `POST /auth/login` agora também passa por `enrich_role()` (antes a sidebar admin ficava escondida até refresh).
- Testado: backend 10/10 pytest (`tests/test_cargos_rbac.py`), frontend 12/12 fluxos RBAC — 100%.

## Hierarquia de cargos: Administrador + Dono/a (2026-08-02, parte 2)
- Dois cargos de sistema de topo, ambos com **controlo total** (is_admin, todos os módulos) e protegidos (is_system, não editáveis/elimináveis): **Administrador** (rank 100) e **Dono/a** (rank 90).
- Campo `rank` nos cargos. Regras aplicadas no backend (staff): não atribuir cargo de rank superior ao próprio (anti-escalonamento); não gerir/eliminar contas de rank superior. Assim o Dono não apaga/edita o Administrador (cargo nem contas), mas o Administrador está acima e gere o Dono.
- Frontend (`Staff.js`): dropdown de cargo mostra apenas cargos ≤ rank do próprio; botões Gerir/Eliminar escondidos para contas de rank superior.
- Verificado por curl: Dono is_admin+controlo total; Dono→apagar cargo/conta Administrador = 403; Dono→atribuir Administrador = 403; Administrador→apagar Dono = 200.

## Picagem — fecho automático por geolocalização (2026-08-07)
- **Entrada manual** (botão, dentro do raio, como antes). **Saída automática ao sair do raio**: enquanto em serviço, a app segue a localização (`watchPosition`) e envia heartbeats.
- Novo endpoint `POST /api/timeclock/heartbeat {lat,lng}`: se estiver fora do raio fecha o ponto (`auto_checkout=true`, `checkout_reason="out_of_radius"`); dentro do raio atualiza `last_seen`/`last_lat/lng`.
- **Sem sinal / app fechada**: worker em segundo plano (`auto_checkout_worker`, corre a cada 60s) fecha pontos sem heartbeat há > `AUTO_CHECKOUT_GRACE_SECONDS` (**5 min**), com `checkout_reason="no_signal"`, usando a última posição/hora conhecida como saída.
- Saídas manuais ficam com `checkout_reason="manual"`, `auto_checkout=false`.
- Frontend (`Picagem.js`): indicador "A monitorizar localização", intervalo de heartbeat a 45s, aviso de saída automática e **badge "auto"** + motivo no histórico.
- Verificado: heartbeat fora do raio a 1412m → fecho `out_of_radius`; entrada obsoleta (10 min) → worker fechou como `no_signal` na última posição. Frontend renderiza e compila.

## Picagem em separadores: Horário + Correção (2026-08-07, parte 2)
- Página Picagem organizada em 3 separadores: **Picar Ponto** (todos com módulo picagem), **Horário** e **Correção de Picagens** (só gestores/supervisores + Administrador/Dono). Extraído para `components/picagem/{PunchPanel,HorarioTab,CorrecaoTab}.js`.
- **Horário semanal** (coleção `schedules`): por funcionário e dia da semana (Seg–Dom) com hora de entrada/saída ou Folga. `GET/PUT /api/schedules` (require_manage picagem).
- **Cumprimento** (`GET /api/schedules/compliance?date=`): compara o turno com a 1ª picagem do dia (fuso Europe/Lisbon) e assinala **Presente / Atraso (+min, tolerância 5m) / Falta**.
- **Correção** (`PUT /api/timeclock/entries/{id}`, require_manage): fechar ponto aberto e editar horas (entrada/saída); valida saída ≥ entrada; converte hora local→UTC; marca `checkout_reason="correction"`. `DELETE /api/timeclock/entries/{id}` **só para cargos de sistema** (`is_system` — Administrador/Dono).
- `enrich_role` passa a expor `is_system`. Verificado por curl: schedule PUT/compliance OK; correção fecha/edita com duração correta; saída<entrada→400; delete por admin(is_system)→200, por não-sistema→403.

## Horas/Salário, Resumo Semanal, Avisos e Tempos Configuráveis (2026-08-07, parte 3)
- **Horas & Salário** (`GET /api/reports/hours?from&to`, módulo relatorios): soma horas trabalhadas por funcionário a partir das picagens fechadas e custo = horas × salário/hora; tabela + totais no módulo Relatórios com **exportação CSV** (separador ';').
- **Resumo Semanal** (`GET /api/schedules/weekly-summary`): horas previstas (turnos) vs. efetivas por funcionário na semana atual, mostrado no separador Horário.
- **Avisos** (coleção `notifications`): **atraso** criado na picagem de entrada quando entra após tolerância; **falta** detetada pelo worker (a cada 60s) quando passou início+tolerância sem picagem. `GET/POST /api/notifications(/read)` (require_manage picagem). Sino de notificações (`NotificationsBell`) na sidebar/topbar só para gestores, com contador de não lidos.
- **Tempos configuráveis** em Definições: `late_tolerance_min` e `no_signal_minutes` (antes fixos em 5). Usados por compliance, _check_late_on_entry, _detect_faltas e auto_checkout_worker.
- Testado: backend 8/8 pytest + frontend 4/4 fluxos + regressão (100%). Tester corrigiu NameError latente de `tol` em schedule_compliance.

## Registadora: Menus & Combos como página própria (2026-08-07, parte 4)
- Novo módulo de permissão **`menus`** (configurável por cargo). Administrador/Dono têm acesso total automático.
- Nova página **`/menus` "Menus & Combos"** (estilo Cargos): CRUD completo de combos (nome, preço, IVA, componentes que descontam stock, ativo). Endpoints `POST/PUT/DELETE /api/pos/combos` passaram de `require_admin` para `require_permission("menus")`.
- Gestão de menus/combos **removida do Config POS** (separador "Menus/Combos" retirado).
- **Registadora** passa a vender **apenas os menus/combos** criados (removida a grelha de produtos de stock em bruto e os filtros de categoria/modificadores da venda). Stock continua a ser gerido só no separador Controlo de Stock.
- Verificado por curl: `menus` nas permissões do admin; criar/editar/eliminar combo 200. Frontend compila.

## Categorias nos Menus/Combos (2026-08-10)
- `ComboInput` passa a ter `category_id` (opcional, reutiliza `pos_categories` de Config POS → Categorias).
- Página **Menus & Combos**: seletor de categoria no diálogo + etiqueta da categoria no cartão.
- **Registadora**: barra de separadores por categoria (Todos + categorias) que filtra os menus/combos, para encontrar mais depressa quando há muitos.
- Verificado por curl: `category_id` guarda e persiste na criação/listagem de combos; frontend compila.

## Backlog / próximos passos
- P1: Integração real de faturação (InvoiceXpress/Moloni) — atualmente sync é simulado.
- P1: Relatórios (módulo "relatorios") — horas trabalhadas por funcionário + custo salarial, exportação.
- P2: Multi-restaurante / seleção de loja; PDF de faturas; validação de intervalo lat/lng.
- P2: Remover dica de credenciais no ecrã de login para produção.
