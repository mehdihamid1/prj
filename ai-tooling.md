# AI Tooling Disclosure

## Tools used

Codex created the initial project scaffold: FastAPI endpoints, local RAG implementation, synthetic policy corpus and mock data, FastMCP tool definitions, tests, CI workflow, and documentation.

Claude is intended for the next refinement pass: review the initial design, improve the UI and policy corpus, add a model-backed planner if desired, expand evaluation coverage, and help prepare deployment/demo material.

## What worked well

AI assistance accelerated creation of a consistent project structure and repetitive synthetic documents, while the MCP tool boundary and automated tests made the generated code easier to inspect.

## What required review

Generated code and policy language must be tested and reviewed before submission. In particular, evaluation results must be measured rather than invented, policy content must remain clearly hypothetical, secrets must stay out of Git, and deployment configuration must be verified on the selected host.
