# Contracts with q-core

`q-core-factory-contract.json` is a copy of q-core's
`contracts/factory-contract.json`: the ticket statuses and MCP tools (with
parameter names) that this repository's skills tell a model to use. q-core
regenerates its copy and fails its suite when the file drifts from its code.

When q-core changes that surface, copy the new file here in the same change
set. `tests/test_q_core_contract.py` then pins the factory skills against it,
so a skill naming a status or tool q-core no longer has fails here.
