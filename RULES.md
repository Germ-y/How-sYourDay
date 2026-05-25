# Architecture Rules

These rules exist so Codex and human contributors keep the agent harness clean.

## Boundaries

- Frontend renders state and sends user input. It does not contain planning
  business logic.
- Agent layer orchestrates tools. It decides what to call and in what order.
- Tools are pure functions where possible. They should be easy to mock.
- Emotion scoring lives server-side.
- User preference updates live under `server/memory`.
- Provider integrations must be wrapped by tool modules before the agent calls
  them.

## Data Contracts

- Use typed request and response models.
- Return structured data from tools.
- Prefer small explicit fields over opaque text blobs.
- Every score should include a reason string.

## Implementation Style

- Keep MVP deterministic until external APIs are ready.
- Add real map/LLM providers behind interfaces, not directly in endpoints.
- Avoid hidden global state in tools.
- Keep prompts and scoring rules versioned in files.
- Tests should cover tool contracts and the agent run flow.

## Product Direction

- The product helps users decide their day. It should not sound like it
  replaces the user's agency.
- Emotion is a decision variable, not a decorative label.
- Cold start uses landmark and place-type heuristics.
- Personalization comes later from explicit route feedback.

