# Test Credentials

## Admin (gestor total)
- Email: admin@restaurante.pt
- Password: admin123
- Role: admin (todas as permissões)

## Notas
- Login: POST /api/auth/login  { email, password } -> { token, user }
- Autenticação por Bearer token (Authorization: Bearer <token>)
- Roles: admin, gestor, funcionario
- Módulos/permissões: stock, picagem, staff, consumo, faturacao, relatorios
- Novos funcionários são criados pelo admin em Gestão de Staff (definindo password e permissões).
- Picagem de ponto requer configurar a localização do restaurante em Definições.
