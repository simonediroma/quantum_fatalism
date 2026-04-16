# Skill: Integrate Responses After Demolition

## Purpose

This skill guides Claude through the process of taking the author's responses to critical demolition and translating them into precise modifications to the text. It ensures that every integration is evaluated, formalized, and confirmed by the author before being applied.

Nothing is modified without the author's explicit approval.

---

## Core Principle

A response to a criticism is not yet a modification. Between the author's answer and the updated text, there are three steps: understanding what the response actually says, determining exactly where and how it changes the text, and confirming with the author that the proposed change captures their intent.

Claude's job in this skill is translation — from the author's thinking to precise, integrated prose.

---

## Phase 0: Collect the Material

Before beginning integration, Claude needs:

1. The current version of the text
2. The list of criticisms from the demolition phase
3. The author's response to each criticism
4. For each criticism: was it resolved, deferred, or declared out of scope?

If any of this is missing, ask for it before proceeding.

Organize the material into three categories:
- **To integrate**: criticisms with strong responses that require changes to the text
- **To declare**: criticisms that are out of scope and should be acknowledged explicitly in the text
- **Deferred**: criticisms the author wants to address later

---

## Phase 1: One Integration at a Time

Work through the "to integrate" list one item at a time. For each:

**Step 1: Summarize the response**

Restate the author's response in your own words, as precisely as possible:
> Your response to [criticism] was: [summary]. Is this an accurate reading of what you said?

Wait for confirmation before continuing.

**Step 2: Identify the implication for the text**

Determine what the response requires:
- A new definition
- A new section or paragraph
- A modification to an existing paragraph
- A narrowing of a claim's scope
- A clarification of a term
- An explicit acknowledgment of a limitation

State this explicitly:
> To integrate this response, the text needs: [specific change]. This would go in [location]. Here is a draft: [proposed text].

**Step 3: Present the draft**

Write the proposed modification. Keep it as minimal as possible — change only what the response requires, nothing more. Do not take the opportunity to improve other aspects of the text.

Present it clearly:

---
**Proposed change in [section/paragraph]:**

*Current text:*
> [original passage]

*Proposed text:*
> [modified passage]

*What changed and why:*
[one sentence explanation]

---

**Step 4: Wait for feedback**

Ask:
> Does this capture what you wanted to say? Should anything be adjusted before I apply this change?

Do not apply any change until the author explicitly confirms it.

If the author modifies the proposed text, restate the final version and confirm once more:
> So the final version is: [text]. Confirmed?

Only after confirmation, apply the change.

---

## Phase 2: Cascading Effects

After each integration, check whether the change creates consistency problems elsewhere in the text.

Ask yourself:
- Does this change contradict anything else in the text?
- Does this change require a corresponding update to the introduction or conclusion?
- Does this change affect any term that is used elsewhere with a different meaning?
- Does this change require updating the bibliography or references?

If cascading effects exist, flag them:
> This change also affects [other section], because [reason]. Proposed adjustment: [draft]. Do you want to address this now or later?

---

## Phase 3: Declarations

For criticisms that were declared out of scope, the text should explicitly acknowledge its own limits. Readers who notice the gap will trust the text more if it has already addressed it honestly.

For each declared limitation, propose an acknowledgment:
> You declared [criticism] outside the scope of this theory. I suggest adding an explicit acknowledgment in [location]: [proposed text]. This will preempt the criticism from readers. Do you want to include it?

The author may decline. Note it and move on.

---

## Phase 4: The Final Review

After all integrations are complete, read the full modified text and check:

- Does the text now address every resolved criticism?
- Is the text internally consistent — no new contradictions introduced by the changes?
- Do the changes flow naturally, or do they read as patches?
- Is the tone consistent throughout?

If any section reads as a patch — visibly different in register or style from the surrounding text — flag it and offer to smooth it:
> The integration in [section] reads as slightly discontinuous with the surrounding text. Would you like me to smooth the transition while preserving the substance?

Wait for confirmation before smoothing.

---

## Phase 5: Summary

When all integrations are complete, present a summary:

> Here is what changed in this round of integration:
> - [Change 1]: [one line description]
> - [Change 2]: [one line description]
> - [...]
>
> These criticisms were declared out of scope and acknowledged in the text: [list]
>
> These criticisms were deferred: [list]
>
> The text is now at version [n]. Do you want to run another round of demolition, or is this the final version?

---

## Rules

- Never apply a change without explicit author confirmation.
- One integration at a time.
- Keep changes minimal — address only what the response requires.
- Always check for cascading effects after each change.
- Distinguish between changes that modify the theory and changes that clarify the text.
- If the author's response is unclear, ask for clarification before proposing any change.
- The author's words take precedence over Claude's formalization. If the author prefers their phrasing, use it.
- Track version numbers. After each complete round of integration, the text advances one version.
