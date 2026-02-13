# RBAC Frontend (Angular)

## Objetivo
Remover permissões mockadas do frontend e usar capacidades reais do backend para:
- bloquear rotas (`permissionGuard`)
- renderizar ações condicionais (`appCan`)
- filtrar menus (tenant + control panel)

## Fontes de permissão

### Tenant
- Endpoint: `GET /api/auth/capabilities/`
- Formato esperado:

```json
{
  "tenant_code": "acme",
  "role": "MANAGER",
  "capabilities": {
    "customers": {
      "list": true,
      "retrieve": true,
      "create": true,
      "update": true,
      "partial_update": true,
      "delete": false
    }
  }
}
```

O frontend transforma isso em permissões string:
- `customers.list`, `customers.retrieve`, `customers.create`, ...
- atalhos: `customers.read` e `customers.write`
- papéis: `tenant.role.member`, `tenant.role.manager`, `tenant.role.owner`

### Control Panel
Não há endpoint granular de RBAC no backend para CP.
O frontend usa validação real por:
1. `GET /api/auth/me/` (usuário autenticado)
2. probe `GET /api/control-panel/plans/?page=1&page_size=1`

Se o probe retornar acesso, o frontend habilita o conjunto `cp.*` compatível com as regras atuais do backend (com `cp.superadmin` para `is_superuser`).

## Cache
`CapabilitiesService` mantém cache por contexto de sessão:
- memória
- `localStorage` (opcional)
- TTL curto: 5 minutos

Chave de contexto: `portal:username:tenantCode`.

## Alias canônico
Arquivo único: `src/app/core/auth/permission-aliases.ts`

Esse mapa converte permissões canônicas do front para strings reais, por exemplo:
- `tenant.apolices.view` -> `apolices.list` / `policies.list`
- `tenant.fiscal.view` -> `invoices.list`
- `control_panel.audit.read` -> `cp.audit.view`

## Fluxo de execução
1. Login salva sessão/token.
2. `PermissionService.loadPermissions()` resolve permissões reais via `CapabilitiesService`.
3. `permissionGuard` bloqueia navegação sem permissão.
4. `appCan` mostra/esconde elementos por permissão.
5. Menus são filtrados por permissão no `AppComponent` e no layout do Control Panel.

## Fallback de segurança
Em falha de carregamento de capabilities:
- acesso é negado por padrão
- `permissionGuard` exibe mensagem e redireciona para login
