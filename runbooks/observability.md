# Shared observability stack

Every managed project, and anything else the owner builds, can send telemetry to
**one self-hosted observability stack on the server**, a home server whose
configuration lives in the server's configuration repo. Use it for three things:

1. **Checking health** of the server and its services (CPU, temperatures and
   throttling, memory pressure, disk, network, backups, service failures).
2. **Debugging** your software: its traces, logs and metrics, correlated.
3. **Instrumenting new projects** with OpenTelemetry from day one.

**Canonical guide:** the server configuration repo's observability guide
(a separate private repository; not a submodule of this copy).
It covers query recipes (PromQL/LogQL/TraceQL), OTel conventions, and
Python/Node/MCP quickstarts.

## Essentials
- **Grafana:** `https://your-host.tailXXXXXX.ts.net:8443` (placeholder; the
  real host and tailnet are set locally). Tailnet only,
  signed in by Tailscale identity.
- **Send telemetry (OTLP):** `OTEL_EXPORTER_OTLP_ENDPOINT=http://server:4318`
  (`http://127.0.0.1:4318` when running on the server), plus `OTEL_SERVICE_NAME`
  and `OTEL_RESOURCE_ATTRIBUTES=service.version=…,deployment.environment=…`.
  Make telemetry **env-driven and off when unset**, so tests and offline
  runs need nothing.
- **Query while debugging:** on the server, Prometheus `:9090`, Loki `:3100`
  and Tempo `:3200` answer on localhost. From other tailnet devices, use
  Grafana's datasource proxy
  (`…:8443/api/datasources/proxy/uid/{prometheus|loki|tempo}/…`).
- **Alerts** go to the owner's phone via ntfy. Add rules as code in the server's
  configuration repo (`modules/observability/alerting.nix`). Don't send ad-hoc pages.

## Rules for agents
- **Privacy is non-negotiable** (CLAUDE.md "Safety", and q-core's privacy
  rules for anything touching personal or financial data): no
  secrets, tokens, document text, financial values, account/card numbers,
  emails or names in span attributes, metric labels or log fields.
- Low-cardinality names and labels: routes, not raw URLs; no user ids as
  metric labels.
- New project? Fill the "Observability" section of its PROJECT.md (from
  `templates/project/PROJECT.md`) with its `service.name` and what it emits.
- Changing the stack itself (dashboards, rules, retention) is server-configuration
  work: open a PR on that repo, don't edit Grafana by hand. UI edits aren't persisted.
