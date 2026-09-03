---
id: 001
type: design-review
status: answered (see 001-design-review.response.md; dispositions in 001-design-review.dispositions.md)
requested_by: Claude (builder)
reviewer: Codex (reviewer)
date: 2026-09-03
inputs:
  - ../../../BRIEF.md            (the assignment, verbatim from the authors; bold is theirs)
  - ../../../ARCHITECTURE.md     (the plan under review, sections 0-14)
  - ../../../PLAN.md             (earlier plan; ARCHITECTURE.md supersedes where they differ)
---

# Request 001: independent design review before any code is written

## Context
This is a one-week take-home for a Treasury AI engineering role. The deliverables are a repo
and a deployed URL; there may be no follow-up interview, so the repo and the running app are
the whole evaluation. The role is AI-directed engineering: a human directs Claude (builder) and
Codex (reviewer). Reviewers have seen ~50 submissions to the same brief, so "adequate" is known
to them.

The builder has done five review passes of its own. You are the first independent reader.
Assume the builder is wrong somewhere and find it.

## What we need from you
Answer these in order, each as a numbered list, terse, no preamble:

1. **Missed requirements.** Anything in BRIEF.md (including the five phrases the authors
   bolded) that ARCHITECTURE.md does not address, or addresses weakly. Quote the brief.
2. **Wrong calls.** Decisions in ARCHITECTURE.md you would reverse, with the reason and the
   alternative. Be specific about section numbers.
3. **Over-scope.** What you would cut to protect the core given six working days, and in what
   order. Compare against the Definition of Done in section 12.
4. **Technical risks the plan underestimates.** OCR accuracy on decorative label fonts,
   Python 3.13 wheel availability, ONNX Runtime threading under a semaphore, coordinate
   mapping, USWDS vendoring without a build step, Azure Container Apps specifics, anything else.
5. **Reviewer's-eye check.** Put yourself in the seat of an engineer at Treasury opening the
   repo and the URL for 20 minutes with a scoring sheet for the six evaluation criteria.
   What would cost points? What would earn them that the plan does not yet do?
6. **Domain check.** Anything wrong or missing about TTB labeling rules as described
   (27 CFR Parts 4, 5, 7, 16; health warning text and format; standards of fill). Flag
   anything the plan should verify on eCFR before coding.
7. **Top five.** If the builder can only act on five of your points, which five.

## Rules
- Read-only. Do not modify any file.
- Do not propose adding an LLM to the core verification path; the brief's firewall and
  5-second constraints rule it out and section 12 explains why. Optional providers are fine.
- Prefer concrete over general: name the section, the file, the rule, the number.
- If you agree with something, say so in one line and move on. Disagreement is the value here.
