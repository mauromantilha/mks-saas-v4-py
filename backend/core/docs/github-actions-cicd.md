# CI/CD com GitHub Actions (push na main)

Este projeto usa o workflow `.github/workflows/ci-cd-main.yml` com 3 etapas:

1. `backend-ci`: instala dependências e executa `manage.py check` + `manage.py test`.
2. `frontend-ci`: executa `npm ci` e `npm run build`.
3. `deploy`: builda imagem do backend no Artifact Registry, executa migrações via Cloud Run Job e publica no Cloud Run Service.

## Secrets obrigatórios no GitHub

Configure em `Settings > Secrets and variables > Actions > Secrets`:

1. `GCP_SA_KEY`: JSON da service account com permissões de deploy.

Se você optar por Workload Identity Federation, pode usar:

1. `Variables`: `GCP_WORKLOAD_IDENTITY_PROVIDER`
2. `Variables`: `GCP_SERVICE_ACCOUNT`

Nesse caso, o `GCP_SA_KEY` deixa de ser necessário.

## Variables recomendadas (com defaults já definidos)

Configure em `Settings > Secrets and variables > Actions > Variables`:

1. `GCP_PROJECT_ID` (default: `mks-saas-enterprise-py`)
2. `GCP_REGION` (default: `us-central1`)
3. `CLOUD_RUN_SERVICE` (default: `mks-backend`)
4. `CLOUD_RUN_MIGRATION_JOB` (default: `mks-backend`)
5. `ARTIFACT_REGISTRY_REPOSITORY` (default: `mks-backend`)
6. `BACKEND_IMAGE_NAME` (default: `mks-backend`)
7. `CLOUD_SQL_INSTANCE` (default: `mks-db-instance`)
8. `CLOUD_STORAGE_BUCKET` (default: `mks-storage-mks-saas-enterprise-py`)
9. `DATABASE_NAME` (default: `mks_db`)
10. `DATABASE_USER` (default: `mks_user`)
11. `TENANT_BASE_DOMAIN` (default: `mksbrasil.com`)
12. `CONTROL_PLANE_SUBDOMAIN` (default: `sistema`)
13. `DJANGO_SECRET_KEY_SECRET_NAME` (default: `django-secret-key`)
14. `DB_PASSWORD_SECRET_NAME` (default: `mks-db-password`)

## Permissões mínimas da Service Account

Conceda os papéis no projeto GCP:

1. `roles/run.admin`
2. `roles/run.developer`
3. `roles/iam.serviceAccountUser` (na runtime service account do Cloud Run)
4. `roles/cloudbuild.builds.editor`
5. `roles/artifactregistry.admin` (ou writer + reader)
6. `roles/cloudsql.client`
7. `roles/secretmanager.secretAccessor`
8. `roles/serviceusage.serviceUsageAdmin` (se mantiver `gcloud services enable` no workflow)

## Fluxo de uso

1. Faça `git push origin main`.
2. O workflow roda CI backend + frontend.
3. Em sucesso, builda a imagem, roda migração e faz deploy do serviço.
4. A URL publicada aparece no resumo da execução (`GitHub Actions > Summary`).
