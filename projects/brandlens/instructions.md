# Agent Instructions

This is BrandLens — a GEO/AIO analytics PWA. Key things to remember:

- The user provided detailed source docs: 001_schema.sql, data-contracts.schema.json, GEO_Metrics_Golden_Standard_v2.md, pipeline-documentation.md. These are in the project root — read them when your task references original schemas or contracts.
- Frontend and backend are separate apps in a Turborepo monorepo. They communicate via HTTP only. Never import across apps.
- Plan enforcement happens in THREE places: backend API (rejects requests), RLS (blocks DB access), frontend (hides UI). All three must agree.
- All 10 metrics are always computed by the backend, even for free users. The API response omits locked metric details — the frontend never receives them.
- No emoji anywhere in the UI. Use Lucide icons. Line art aesthetic with blue+gray palette.
- Paddle is the billing provider — it handles payments externally. We only sync subscription state via webhooks.
