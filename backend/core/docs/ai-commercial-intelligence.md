# Commercial AI (Vertex AI + CNPJ Enrichment)

## Objective

Apply AI-driven analysis across commercial modules with strict tenant isolation:

- lead qualification and next-best-actions
- customer account intelligence
- opportunity risk/opportunity analysis
- policy (`apolice`) and endorsement (`endosso`) intelligence notes
- CNPJ enrichment for lead/customer records

## Endpoints

Tenant-scoped (`Authorization: Token ...` + `X-Tenant-ID` or tenant subdomain):

- `POST /api/leads/{id}/ai-insights/`
- `POST /api/customers/{id}/ai-insights/`
- `POST /api/opportunities/{id}/ai-insights/`
- `POST /api/apolices/{id}/ai-insights/`
- `POST /api/endossos/{id}/ai-insights/`
- `POST /api/leads/{id}/ai-enrich-cnpj/`
- `POST /api/customers/{id}/ai-enrich-cnpj/`

Request payload (insights):

```json
{
  "focus": "estratégia para fechamento com diretor financeiro",
  "include_cnpj_enrichment": true
}
```

Request payload (CNPJ enrichment):

```json
{
  "cnpj": "12.888.877/0001-90"
}
```

`cnpj` is optional if already present on the target record.

## Settings

Add to `.env`:

```env
VERTEX_AI_ENABLED=false
VERTEX_AI_PROJECT_ID=mks-saas-enterprise-py
VERTEX_AI_LOCATION=us-central1
VERTEX_AI_MODEL=gemini-1.5-pro-002
VERTEX_AI_TEMPERATURE=0.2

CNPJ_LOOKUP_ENDPOINT=https://brasilapi.com.br/api/cnpj/v1/{cnpj}
CNPJ_LOOKUP_TIMEOUT_SECONDS=8
```

## Provider Strategy

- If `VERTEX_AI_ENABLED=true`, backend uses Vertex AI model generation.
- If Vertex fails or is disabled, backend returns deterministic heuristic insights.
- CNPJ lookup uses configurable HTTP provider via `CNPJ_LOOKUP_ENDPOINT`.

## Persistence

`ai_insights` is stored on tenant-scoped entities (lead/customer/opportunity/activity/apolice/endosso),
with `latest` and rolling `history` for traceability.
