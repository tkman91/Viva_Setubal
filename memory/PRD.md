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
- Auth local + seed admin (admin@restaurante.pt / admin123).
- Painel com KPIs (valor stock, produtos, staff, ativos agora, consumo hoje/total, stock baixo) + gráfico consumo 7 dias.
- Controlo de Stock: CRUD produtos, movimentos entrada/saída, alertas de stock baixo.
- Picagem de Ponto: geolocalização com validação de raio, radar animado, entrada/saída, histórico.
- Gestão de Staff: adicionar/editar/eliminar, definir role, salário/hora, permissões por módulo.
- Consumo Staff: registo com desconto de stock e valor; agregação por funcionário.
- Faturação: criar faturas com linhas/IVA (23/13/6/0%), totais, nº sequencial, "Emitir" (sync simulado — INTEGRAÇÃO EXTERNA POR LIGAR).
- Definições: localização do restaurante + raio.

## Estado / testes
- Backend 33/33 testes PASS. Frontend smoke 100%.

## Backlog / próximos passos
- P1: Integração real de faturação (InvoiceXpress/Moloni) — atualmente sync é simulado.
- P1: Relatórios (módulo "relatorios") — horas trabalhadas por funcionário + custo salarial, exportação.
- P2: Multi-restaurante / seleção de loja; PDF de faturas; validação de intervalo lat/lng.
- P2: Remover dica de credenciais no ecrã de login para produção.
