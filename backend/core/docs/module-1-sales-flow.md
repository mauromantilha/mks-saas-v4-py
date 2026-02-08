# Module 1: Sales Flow (Commercial Pipeline)

Endpoints (tenant-scoped, requires `Authorization: Token ...` and `X-Tenant-ID`):

- `GET /api/leads/`
- `GET /api/leads/{id}/`
- `POST /api/leads/{id}/qualify/`
- `POST /api/leads/{id}/disqualify/`
- `POST /api/leads/{id}/convert/`

- `GET /api/opportunities/`
- `GET /api/opportunities/{id}/`
- `POST /api/opportunities/{id}/stage/`

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
- lead must have customer, or request payload must provide a tenant-valid customer

Example payloads:

```json
{
  "title": "Opportunity from website lead",
  "amount": "5000.00",
  "stage": "DISCOVERY",
  "expected_close_date": "2026-03-15"
}
```

```json
{
  "stage": "PROPOSAL"
}
```
