# Module 1: Sales Flow (Commercial Pipeline)

Endpoints (tenant-scoped, requires `Authorization: Token ...` and `X-Tenant-ID`):

- `GET /api/leads/`
- `GET /api/leads/{id}/`
- `POST /api/leads/{id}/qualify/`
- `POST /api/leads/{id}/disqualify/`
- `POST /api/leads/{id}/convert/`
- `POST /api/leads/{id}/ai-insights/`
- `POST /api/leads/{id}/ai-enrich-cnpj/`

- `GET /api/opportunities/`
- `GET /api/opportunities/{id}/`
- `POST /api/opportunities/{id}/stage/`
- `POST /api/opportunities/{id}/ai-insights/`
- `GET /api/sales/metrics/`

- `GET /api/customers/`
- `GET /api/customers/{id}/`
- `POST /api/customers/{id}/ai-insights/`
- `POST /api/customers/{id}/ai-enrich-cnpj/`

- `POST /api/apolices/{id}/ai-insights/`
- `POST /api/endossos/{id}/ai-insights/`

## Business Rules

Lead status transitions:

- `NEW -> QUALIFIED | DISQUALIFIED`
- `QUALIFIED -> CONVERTED | DISQUALIFIED`
- `DISQUALIFIED` final
- `CONVERTED` final

Opportunity stage transitions:

- `DISCOVERY -> PROPOSAL | LOST`
- `PROPOSAL -> NEGOTIATION | LOST`
- `NEGOTIATION -> WON | LOST`
- `WON` final
- `LOST` final

Lead conversion (`/convert/`) requires:

- lead status = `QUALIFIED`
- if lead has no customer:
  - can use request payload customer (`customer=<id>`) OR
  - can auto-create customer from lead data (`create_customer_if_missing=true`, default)
  - auto-create requires lead email filled

Example payloads:

```json
{
  "title": "Opportunity from website lead",
  "amount": "5000.00",
  "stage": "DISCOVERY",
  "expected_close_date": "2026-03-15",
  "create_customer_if_missing": true
}
```

```json
{
  "stage": "PROPOSAL"
}
```

## Sales Metrics Filters

`GET /api/sales/metrics/` supports optional query parameters:

- `from=YYYY-MM-DD`
- `to=YYYY-MM-DD`
- `assigned_to=<user_id>` (filters only activity KPIs by assignee)

Example:

`/api/sales/metrics/?from=2026-02-01&to=2026-02-28&assigned_to=15`

Response includes:

- `period` (applied filters)
- `lead_funnel`
- `opportunity_funnel`
- `activities`
- `activities_by_priority`
- `pipeline_value` (open/won/lost totals and expected close in next 30 days)
- `conversion`

## Detailed Commercial Data

`Customer`, `Lead`, `Opportunity` and `CommercialActivity` now include richer sales fields:

- customer lifecycle, legal/company data, primary/secondary contacts, billing, address,
  social links and assignment
- lead qualification details, CNPJ, social links, estimated budget and follow-up dates
- opportunity probability, competitors, next step and loss reason
- activity channel, outcome, duration, meeting metadata and SLA tracking

## Commercial AI

AI is available in all major commercial modules:

- Lead, Customer, Opportunity, Apólice, Endosso insights endpoints
- CNPJ enrichment endpoints for Lead and Customer
- `ai_insights` persisted in tenant-scoped records for audit/history

Provider behavior:

- Vertex AI when `VERTEX_AI_ENABLED=true` and project/model are configured
- secure heuristic fallback when Vertex is unavailable
