# Claude Code instructions

Read `AGENTS.md` first. It holds the roles, the non-negotiable rules, the layout, the commands,
and the Definition of Done for this repository. Everything there applies to you as the builder.

Builder-specific reminders:
- Before implementing a review finding from `docs/reviews/`, verify it yourself. Record the
  disposition (accepted / rejected with reason / deferred) in the same review file.
- Run the fast test suite before every commit. Run the full suite before every deploy.
- Never weaken a test to make it pass. If a rule in `AGENTS.md` blocks a change, stop and ask.
