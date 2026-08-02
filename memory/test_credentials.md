# Credenciais de teste

## Admin (cargo "Administrador" — sistema, rank 100, topo, não eliminável)
- Email: admin@restaurante.pt
- Password: admin123

## Notas — RBAC / Cargos com hierarquia
- Coleção `roles`: `{id, name, modules[], is_admin, is_supervisor, is_system, rank, created_at}`.
- **Dois cargos de sistema de topo (protegidos, controlo total, is_admin=true, is_system=true):**
  - **Administrador** — rank 100 (mais alto).
  - **Dono/a** — rank 90.
- Permissões derivam SEMPRE do cargo (`role_id`), re-avaliadas por pedido em `enrich_role` (inclui `rank`).
- Hierarquia (rank):
  - Não se pode atribuir/criar um funcionário com cargo de rank SUPERIOR ao do próprio (evita escalonamento). Ex: Dono não pode criar/atribuir Administrador → 403.
  - Não se pode editar/eliminar contas cujo cargo tenha rank SUPERIOR ao próprio. Ex: Dono não gere contas Administrador → 403. Administrador gere Dono (200).
  - Cargos `is_system=true` (Administrador e Dono/a) não são editáveis nem elimináveis (403 — "cargo de sistema").
- Staff: `POST/PUT /api/staff` usam `role_id`.
- Migração automática no arranque: admin→Administrador; gestor→Gestor; funcionario→Funcionário.
