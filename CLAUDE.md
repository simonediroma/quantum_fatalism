# CLAUDE.md
## Guide to Replicating This Writing Process with Claude

This document describes how to use Claude to produce a philosophical or theoretical essay of publishable quality, starting from your own ideas and arriving at a rigorous, coherent, and critically tested text.

The process used to produce "The Universe at Minimum Energy" is replicable. It requires no special prompts or particular configurations. It requires a method.

---

## The Fundamental Principle

**Claude is a tool for formalization, not invention.**

Concepts must come from you. Claude can help you make them precise, find their implications, identify internal contradictions, and integrate relevant scientific and philosophical literature. It cannot invent the theory for you.

If you begin by asking Claude to "write an essay about X" without already having precise ideas about X, you will get a generic and superficial text. If you begin with your own ideas and use Claude to refine them, you get something different.

---

## Phase 1: Bring the Existing Material

Before writing, load all the material you have:

- Previous drafts, even incomplete or generated with other tools
- Notes, jottings, scattered thoughts
- Reference texts that inspired you
- Criticism you have previously received

Ask Claude to analyze the material:

```
Analyze these documents. Tell me what is here, what the central
strength is, and what the most serious structural problem is.
```

Do not accept a generic response. If the criticism is vague, ask for more specificity.

---

## Phase 2: Questions Before Writing

This is the most important phase. **Do not write anything before answering the fundamental questions.**

Ask Claude to ask you questions one at a time about the central concepts of your theory. The formula is:

```
Before writing the essay, ask me questions one at a time about
the fundamental concepts. Do not stop asking until you are
convinced we have analyzed everything. Start with the most
central concept.
```

Answer in your own words, even if they are imprecise or incomplete. Claude will formalize them. What matters is that they come from you.

The typical questions Claude will ask concern:

- **The heart of the thesis**: what exactly are you asserting? What does it deny?
- **Key terms**: what do you mean by X in your specific context?
- **Implications**: if X is true, what necessarily follows?
- **Edge cases**: how does the theory work when applied to extreme cases?
- **Contradictions**: you have used X in two different ways — which is correct?

---

## Phase 3: Build the Essay in Versions

Do not seek perfection in the first version. Build in layers.

```
Write a first version of the essay based on what we have discussed.
Use [format: markdown/docx]. Then I will tell you what is missing
or what needs changing.
```

After each version, identify what does not work and ask for specific changes. Do not ask Claude to "improve it" — ask for precise modifications:

```
In Chapter 2, concept X is introduced before being explained.
Move it or anticipate it in the introduction.
```

---

## Phase 4: The Critical Demolition

This is the phase that distinguishes a mediocre text from a solid one.

```
Now forget that you wrote this essay. Apply the most hostile
critical thinking you have. Demolish my theory.
```

Claude will identify real structural problems: logical circularity, undefined concepts, internal contradictions, problematic implications the author had not seen.

**Address each criticism one at a time.** Do not try to answer everything at once. For each demolition:

1. Understand exactly what it accuses
2. Respond with your position
3. Ask Claude to integrate the response into the essay

If a criticism is correct and you do not know how to respond to it, say so. Claude will help you understand whether the problem requires modifying the theory or only clarifying the text.

---

## Phase 5: Scientific Integration

If your theory has points of contact with existing scientific or philosophical literature, ask Claude to research and find precise parallels:

```
Research Friston's Free Energy Principle. Tell me if there are
convergences with my theory and what the equivalent concepts
are called in his terminology.
```

Use existing scientific terminology where it is more precise than your own, but do not abandon your original terms when they describe something different or more specific.

---

## Phase 6: Linguistic Revision

Only after the content is solid, work on form.

Ask Claude to identify:

- Terms used before being defined
- Unnecessary anglicisms with valid equivalent terms
- New age tone or value judgments disguised as descriptions
- Stylistic contradictions between chapters

```
Review the document looking for: framework concepts introduced
without explanation, terms with equivalent alternatives in the
target language, passages that sound prescriptive instead of
descriptive.
```

---

## Skills

The `/skills` folder contains three reusable skill files that formalize the core phases of this process. They can be loaded directly in Claude Code or referenced in any conversation.

### `skills/ask_before_writing.md`
Guides Claude through a structured pre-writing dialogue to extract, clarify, and formalize the author's concepts before a single word of the final text is written. Six phases: understand the project, identify the core claim, define key terms, explore implications, test edge cases, surface contradictions. Claude asks one question at a time and does not proceed to writing until the author confirms a complete summary.

```bash
claude "Read skills/ask_before_writing.md and then ask me what I want to write."
```

### `skills/demolish.md`
Guides Claude through an adaptive, hostile critical analysis of any text. Claude maps all potential vulnerabilities across seven categories, prioritizes by severity, and presents them one at a time. Each criticism is evaluated before moving to the next. Claude does not offer solutions during demolition.

```bash
claude "Read skills/demolish.md and then demolish the essay in essay.md"
```

### `skills/integrate.md`
Guides Claude through translating the author's responses to demolition criticisms into precise modifications to the text. For each response: proposes a specific before/after change, checks for cascading effects, and waits for explicit author confirmation before applying anything.

```bash
claude "Read skills/integrate.md. Here are my responses to the demolition: [your responses]. The current text is in essay.md."
```

### The full cycle

The three skills form a complete writing cycle:

```
ask_before_writing → draft → demolish → integrate → demolish → integrate → ...
```

Each demolition/integration round produces a stronger version. Stop when the demolition finds nothing new that materially damages the argument.

---

## Useful Commands for Claude Code

If you use Claude Code instead of the web interface, you can automate parts of the process:

```bash
# Analysis of existing material
cat draft.md | claude "Analyze this text. Identify the central
strength and the most serious structural problem."

# Generate the final docx
claude "Generate the essay in docx format with professional
formatting from essay.md"

# Critical revision
claude "Read essay.md and identify all concepts used before
being defined in the specific context of the theory"
```

---

## What to Expect

The described process produced an essay of ~20 pages in an extended session. Time is not measurable in a standard way because it depends on the depth of the concepts and the speed at which the author responds to questions.

The typical number of versions for a text of this complexity is 5-8. Each version resolves specific problems and introduces new ones, which are identified in the subsequent criticism phase.

The final result will be a text that reflects your voice and your thinking, formalized with a level of argumentative precision that would be difficult to achieve alone without a constant critical interlocutor.

---

## A Final Note

Claude has no point of view on your theory. It will not tell you it is beautiful or ugly, right or wrong. It will tell you where it is imprecise, where it is circular, where it contradicts itself. Use it as a critical mirror, not as a validator.

The theory is yours. The text is ours.

---

*Based on the writing process of "The Universe at Minimum Energy"*
*Author: [human author] in collaboration with Claude (Anthropic)*
