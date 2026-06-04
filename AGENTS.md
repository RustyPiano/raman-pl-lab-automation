# AGENTS.md

Guidance for agents working in this repository.

## Project Context

- This repository is for laboratory automation around Raman/PL experiments.
- Prefer wrapping documented hardware APIs and SDKs over GUI automation.
- Treat vendor SDKs, drivers, examples, and manuals as reference artifacts. Do not reformat or rewrite them unless explicitly requested.
- Do not import or reuse vendor demo code as the project adapter. Use C headers and protocol PDFs for raw bindings, then wrap them in a small adapter layer.
- Keep SDK rough edges inside the boundary layer: native function names and protocol strings stay in raw bindings; workflow code only sees clean Python APIs.
- Default implementation and tests should support dry-run or simulated mode before touching real hardware.
- Hardware movement, light-source control, and mapping workflows must include explicit safety assumptions and verifiable pass/fail criteria.

## 1. Think Before Coding

Do not assume. Do not hide confusion. Surface tradeoffs.

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them instead of picking silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop, name what is confusing, and ask.

## 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No flexibility or configurability that was not requested.
- No error handling for impossible scenarios.
- If 200 lines could be 50, rewrite it.

Ask: would a senior engineer say this is overcomplicated? If yes, simplify.

## 3. Surgical Changes

Touch only what is necessary. Clean up only your own changes.

When editing existing code:
- Do not improve adjacent code, comments, or formatting.
- Do not refactor things that are not broken.
- Match existing style, even if you would do it differently.
- If you notice unrelated dead code, mention it instead of deleting it.

When your changes create orphans:
- Remove imports, variables, or functions that your changes made unused.
- Do not remove pre-existing dead code unless asked.

Every changed line should trace directly to the request.

## 4. Goal-Driven Execution

Define success criteria and loop until verified.

For multi-step tasks, state a brief plan:

```text
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
3. [Step] -> verify: [check]
```

Strong success criteria enable independent execution. Weak criteria require clarification.
