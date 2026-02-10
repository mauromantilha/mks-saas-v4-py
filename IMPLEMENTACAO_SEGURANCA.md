# 🔒 Implementação de Correções de Segurança

## Data de Implementação: Fevereiro 2026

Este documento resume as correções de segurança implementadas no projeto MKS SaaS Enterprise.

---

## ✅ Correções Implementadas

### 1. **CRÍTICA - Isolamento de Tenant em QuerySets** ✓

**Arquivo**: `operational/views.py`

**Mudança**: Implementado filtro obrigatório de `company` em `TenantScopedAPIViewMixin.get_queryset()`

```python
def get_queryset(self):
    """Filter queryset by current tenant company (SECURITY: prevent cross-tenant data access)."""
    company = getattr(self.request, "company", None)
    if company is None:
        # Return empty queryset if tenant context is missing
        return self.model.objects.none()
    
    queryset = self.model.objects.filter(company=company)
    if self.ordering:
        return queryset.order_by(*self.ordering)
    return queryset
```

**Benefício**: Impede que usuários de um tenant acessem dados de outro tenant em operações LIST/GET.

**Views Afetadas**: 20+ views que herdam de `TenantScopedAPIViewMixin`
- `LeadListCreateAPIView`
- `CustomerListCreateAPIView`
- `OpportunityListCreateAPIView`
- `ApoliceListCreateAPIView`
- E mais...

---

### 2. **CRÍTICA - Validação de Tenant em get_object_or_404** ✓

**Arquivo**: `operational/views.py`

**Mudanças**: Adicionado filtro de `company` em 8 chamadas de `get_object_or_404()`:

```python
# ANTES (INSEGURO):
lead = get_object_or_404(Lead.objects.all(), pk=pk)

# DEPOIS (SEGURO):
lead = get_object_or_404(Lead.objects.filter(company=request.company), pk=pk)
```

**Views Corrigidas**:
1. `LeadQualifyAPIView.post()` (linha 395)
2. `LeadDisqualifyAPIView.post()` (linha 423)
3. `LeadConvertAPIView.post()` (linha 477)
4. `CommercialActivityCompleteAPIView.post()` (linha 962)
5. `CommercialActivityReopenAPIView.post()` (linha 986)
6. `CommercialActivityMarkRemindedAPIView.post()` (linha 1030)
7. `LeadHistoryAPIView.get()` (linha 1055)
8. `OpportunityHistoryAPIView.get()` (linha 1075)

**Benefício**: Garante que operações DETAIL (GET/PATCH/DELETE) validem ownership do tenant.

---

### 3. **CRÍTICA - Validação de Contexto de Tenant** ✓

**Arquivo**: `operational/views.py`

**Mudança**: Adicionado método `dispatch()` em `TenantScopedAPIViewMixin`:

```python
def dispatch(self, request, *args, **kwargs):
    """Validate tenant context is present before processing request."""
    if not hasattr(request, 'company') or request.company is None:
        return Response(
            {"detail": "Tenant context not found or invalid"},
            status=403
        )
    return super().dispatch(request, *args, **kwargs)
```

**Benefício**: Falha rápido se o middleware não configurou o contexto de tenant.

---

### 4. **MÉDIO - Força obrigatória do SECRET_KEY** ✓

**Arquivo**: `mks_backend/settings.py`

**Mudança**: Implementada validação que força `SECRET_KEY` ser configurado:

```python
SECRET_KEY = env("SECRET_KEY", default="")
if not SECRET_KEY:
    SECRET_KEY = read_secret_from_manager(
        env("DJANGO_SECRET_KEY_SECRET", default=""),
        default_value=None,
    )

if not SECRET_KEY:
    import sys
    if "runserver" not in sys.argv and "test" not in sys.argv:
        raise RuntimeError(
            "FATAL: SECRET_KEY must be set via environment variable or DJANGO_SECRET_KEY_SECRET "
            "(GCP Secret Manager). Using a default SECRET_KEY is a critical security vulnerability."
        )
    SECRET_KEY = "django-insecure-dev-only-change-me-in-production"
```

**Benefício**: Evita deploy accidental com SECRET_KEY padrão em produção.

---

### 5. **MÉDIO - Validação de ALLOWED_HOSTS, CORS e CSRF em Produção** ✓

**Arquivo**: `mks_backend/settings.py`

**Mudanças**:

```python
# Validate ALLOWED_HOSTS is not empty in non-debug mode
if not DEBUG and not ALLOWED_HOSTS:
    raise RuntimeError(
        "FATAL: ALLOWED_HOSTS must be configured in production. "
        "Set ALLOWED_HOSTS environment variable with a comma-separated list."
    )

# Validate CORS origins are configured in production
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
if not DEBUG and not CORS_ALLOWED_ORIGINS:
    raise RuntimeError(
        "FATAL: CORS_ALLOWED_ORIGINS must be configured in production. "
        "Set CORS_ALLOWED_ORIGINS environment variable with valid origins."
    )

CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
if not DEBUG and not CSRF_TRUSTED_ORIGINS:
    raise RuntimeError(
        "FATAL: CSRF_TRUSTED_ORIGINS must be configured in production. "
        "Set CSRF_TRUSTED_ORIGINS environment variable with valid origins."
    )
```

**Benefício**: Previne deploy com valores padrão (localhost) em produção.

---

### 6. **MÉDIO - DEBUG=False por Padrão** ✓

**Arquivo**: `.env.example`

**Mudança**:
```diff
- DEBUG=True
+ DEBUG=False
```

**Benefício**: Novos desenvolvedores herdam sensatos por padrão.

---

### 7. **MÉDIO - CORS e CSRF com Exemplo de Produção** ✓

**Arquivo**: `.env.example`

**Mudança**:
```diff
- # CORS / CSRF
- CORS_ALLOWED_ORIGINS=http://localhost:4200,http://127.0.0.1:4200
- CSRF_TRUSTED_ORIGINS=http://localhost:4200,http://127.0.0.1:4200

+ # CORS / CSRF - MUST be configured for production
+ # Only allow your frontend domain(s)
+ CORS_ALLOWED_ORIGINS=https://app.example.com
+ CSRF_TRUSTED_ORIGINS=https://app.example.com,https://www.example.com
```

**Benefício**: Melhor documentação e exemplo seguro.

---

### 8. **AVISO - Tratamento Seguro de Exceções de Banco de Dados** ✓

**Arquivo**: `control_plane/views.py`

**Mudança**: Não expor mensagens de erro de banco de dados:

```python
except IntegrityError as exc:
    # SECURITY: Do not expose database error details to client
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Tenant creation integrity error: {exc}")
    return Response(
        {"detail": "Tenant name, code, or subdomain already exists. Please use a unique identifier."},
        status=status.HTTP_400_BAD_REQUEST,
    )
```

**Benefício**: Evita information disclosure via error messages.

---

## 📋 Checklist de Testes

Antes de fazer merge para produção, execute:

### Testes Unitários
```bash
python manage.py test operational.tests.test_isolation_tenant
python manage.py test control_plane.tests
```

### Testes de Segurança Específicos

1. **Teste de Cross-Tenant Access**:
```python
# Criar dois users em companies diferentes
user_a = create_user("user_a", company=company_a)
user_b = create_user("user_b", company=company_b)

# User A não deve conseguir acessar dados de User B
response_a = client_a.get(f"/api/leads/{lead_b.id}/")
assert response_a.status_code == 404  # lead_b não pertence a company_a
```

2. **Teste de SECRET_KEY em Produção**:
```bash
export DEBUG=False
export SECRET_KEY=  # vazio
python manage.py check
# Deve falhar com mensagem clara de erro
```

3. **Teste de ALLOWED_HOSTS**:
```bash
export DEBUG=False
export ALLOWED_HOSTS=  # vazio
export CORS_ALLOWED_ORIGINS=https://app.example.com
export CSRF_TRUSTED_ORIGINS=https://app.example.com
python manage.py check
# Deve falhar com mensagem clara de erro
```

4. **Teste de CORS/CSRF**:
```bash
export DEBUG=False
export SECRET_KEY=actual-secret
export ALLOWED_HOSTS=app.example.com
export CORS_ALLOWED_ORIGINS=  # vazio
python manage.py check
# Deve falhar com mensagem clara de erro
```

---

## 🚀 Guia de Deploy

### Pré-Deploy

1. **Configurar Variáveis de Ambiente**:
   ```bash
   export DEBUG=False
   export SECRET_KEY=$(openssl rand -base64 50)
   export ALLOWED_HOSTS=app.example.com,www.example.com
   export CORS_ALLOWED_ORIGINS=https://app.example.com,https://www.example.com
   export CSRF_TRUSTED_ORIGINS=https://app.example.com,https://www.example.com
   ```

2. **Ou usar Google Secret Manager**:
   ```bash
   export DJANGO_SECRET_KEY_SECRET=projects/PROJECT_ID/secrets/django-secret-key
   ```

3. **Validar Configuração**:
   ```bash
   python manage.py check --deploy
   ```

4. **Executar Testes de Segurança**:
   ```bash
   pytest --cov=operational tests/security/test_tenant_isolation.py -v
   pytest --cov=control_plane tests/security/ -v
   ```

---

## 📚 Documentação de Segurança Adicional

### Como Verificar Isolamento de Tenant

1. **Via Admin Django**:
   - Acessar `/admin/` como superuser
   - Verificar que cada modelo tem campo `company`
   - Confirmar que QuerySets filtram por company

2. **Via Testes**:
   - Ver `operational/tests/test_isolation_tenant.py`
   - Executar: `python manage.py test operational.tests.test_isolation_tenant`

3. **Via Logs**:
   - Procurar por avisos de tenant mismatch
   - Logs de IntegrityError são registrados sem expor detalhes

### Boas Práticas para Continuar

1. **Sempre adicionar `.filter(company=request.company)` em QuerySets de views tenant-scoped**
2. **Usar `get_object_or_404(...filter(company=request.company), pk=pk)`**
3. **Nunca fazer `.objects.all()` em views que servem tenants**
4. **Testar cross-tenant access em todos os testes de integração**

---

## 📞 Suporte

Para questões sobre essas mudanças de segurança:
1. Consulte `AUDITORIA_SEGURANCA.md` para detalhes completos
2. Veja comentários de código com `SECURITY:` para anotações inline
3. Execute testes com `pytest -v -k security` para validar

---

**Status**: ✅ Implementado  
**Data**: Fevereiro 2026  
**Próxima Revisão**: 90 dias (ou após mudanças significativas)
