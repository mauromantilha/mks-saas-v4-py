# MKS UI (Frontend)

Frontend Angular criado do zero no caminho `frontend/mks-ui`.

## Regras aplicadas

- Sem reaproveitar arquivos de projetos antigos.
- Nada de `mks-saas-v3`.

## O que já está pronto

- Scaffold Angular (configuração e estrutura de app).
- Roteamento com:
  - `/login` (username/password/tenant code)
  - `/tenant/members` (protegida por sessão)
  - `/tenant/rbac` (protegida por sessão)
- Sessão com persistência em `localStorage`.
- Interceptor global para enviar `Authorization: Token ...` e `X-Tenant-ID`.
- Serviço para:
  - `GET /api/auth/tenant-members/`
  - `POST /api/auth/tenant-members/`
  - `PATCH /api/auth/tenant-members/{id}/`
  - `DELETE /api/auth/tenant-members/{id}/`
- Serviço para:
  - `GET /api/auth/tenant-rbac/`
  - `PUT /api/auth/tenant-rbac/`
  - `PATCH /api/auth/tenant-rbac/`
- Serviço para:
  - `POST /api/auth/token/`
  - `GET /api/auth/tenant-me/`
  - `GET /api/auth/capabilities/`
- Proxy local para backend Django em `http://127.0.0.1:8002`.

## Executar local

```bash
cd frontend/mks-ui
npm install
npm start
```

Acesse:

- `http://localhost:4200/login`

## Backend esperado

Com backend rodando, o front chama via proxy:

- `/api/*` -> `http://127.0.0.1:8002/api/*`

Se quiser outro backend local, edite `proxy.conf.json`.
