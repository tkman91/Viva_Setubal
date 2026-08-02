# Credenciais de teste

## Admin (cargo "Administrador" — sistema, não eliminável)
- Email: admin@restaurante.pt
- Password: admin123

## Notas
- Cargos são dinâmicos (coleção `roles`). Migração automática no arranque:
  - "admin" → cargo **Administrador** (is_system, is_admin, todos os módulos)
  - "gestor" → cargo **Gestor** (is_supervisor)
  - "funcionario" → cargo **Funcionário**
- Permissões dos utilizadores derivam SEMPRE do cargo (campo `role_id`).
- Endpoints: `GET /api/roles` (auth), `POST/PUT/DELETE /api/roles` (admin).
  - Cargo `is_system=true` não pode ser editado nem eliminado (403).
  - Cargo em uso por funcionários não pode ser eliminado (400).
- Staff: `POST/PUT /api/staff` usa `role_id` (não mais `role`/`permissions`).
