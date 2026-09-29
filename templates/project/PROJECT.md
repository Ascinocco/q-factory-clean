# <Project name>

This is the project's authoritative technical guide. Replace the angle-bracket
fields during adoption; they are template prompts, not runnable commands.
Record “not configured” with a reason when a capability does not exist. Do not
invent a successful build, deployment target or test suite.

## Purpose and scope

<Who uses this project, what problem it solves, current supported behavior,
and what is explicitly deferred.>

## Architecture entry points

<Source directories and entry files; component boundaries; where requirements,
architecture decisions and contribution guidance live. Link existing documents
rather than copying their contents.>

## Prerequisites and setup

<Required platform/toolchain and version constraints, dependency installation,
configuration examples and the exact setup commands from the repository root.
Document credential acquisition without recording secret values or private paths.>

## Run

<Exact development command, working directory, expected readiness signal and
how to stop it. If unavailable, state why.>

## Validate and build

<Exact test, lint/typecheck and build commands; required fixtures/services;
expected success signals; checks requiring a particular platform. State what
is missing. Keep the canonical commands here or link their existing location.>

## Deployment and operations

<Supported release/deployment targets, procedures, required authority and
verification/rollback instructions. Explicitly state when deployment is not
configured. Development and passing tests do not imply permission to deploy.>

## Observability

<`service.name`(s) this project emits; what is traced (routes, MCP tools,
jobs); key metrics; where logs go. Telemetry is configured only by
`OTEL_*` env vars and is off when unset. Send to the shared stack on the server
(`OTEL_EXPORTER_OTLP_ENDPOINT=http://server:4318`). Guide: the server's
observability guide. Never put secrets or personal or
financial data in attributes, labels or log fields. Write "not
instrumented yet" if that's the case.>

## Project conventions

<Style, generated files, compatibility commitments, security/data constraints
and any repository-local skills. List actual files or dependencies; do not
assume an external skill is installed.>

## Coordination

<Where work is tracked and how contributors find requirements. If managed by
q-factory, reference its project/board identifiers when useful, never its private
records or a developer's absolute checkout path. This repository must remain
understandable when cloned independently.>
