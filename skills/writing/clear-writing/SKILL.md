---
name: clear-writing
description: >-
  The user's house style for prose, required for any writing or rewriting task. Check this skill first when the user asks for words a person will read: an update for their manager, a short explainer for a CFO or board, an email, a cover letter, a PR description, a README, or a doc. Also check it first when they complain that existing text is too long, full of buzzwords, robotic, or "sounds like ChatGPT/AI" and want it cut down, made plainer, or made to sound human. The text can be pasted, in a file, or in a git branch. If the user says "calibrate my writing rules", "recalibrate", or "update my writing rules from my sessions", this skill owns that task. Prefer it over unslop or PR/commit skills whenever the wording itself is the deliverable. Skip it when no prose is being written: code, tests, translation, slide layout, linters, text-processing scripts, typo-only fixes.
---

# Clear writing

Readers spend more and more time reading model output. This skill makes that output fast to understand and free of the patterns that mark text as machine-written.

It combines three sources:

- **ASD-STE100.** A controlled English written for aircraft maintenance manuals. Its rules force short sentences, one meaning per word, and active voice. The full spec is too strict for most work, so this skill uses a subset ("about 80% of the way to STE").
- **Anti-slop patterns.** Words and structures that readers now recognize as AI-written: puffery, "delve", em dashes, "not just X but Y", chatbot openers.
- **Personal calibration.** Rules chosen by checking which ones would have helped in your own past sessions.

## Pick the mode

| The request | Mode |
|---|---|
| Claude is writing its own answer, explanation, report, or doc | **Write** |
| The user gives text and asks to improve, rewrite, tighten, or unslop it | **Edit** |
| The user asks to tune, calibrate, or personalize these rules | **Calibrate**. Read `references/calibrate.md` and follow it. |

If `calibration.md` exists in this skill folder, read it first in every mode. It holds the user's personal rule weights and overrides the defaults below where they conflict.

## Pick the register

The STE rules help most where the reader must understand or act. They hurt when the text must persuade, entertain, or sound like a person. Choose the register from the text's purpose, then apply rules to match.

| Register | Examples | STE core | AI-tell list | Voice rules |
|---|---|---|---|---|
| **Instruct** | steps, runbooks, setup guides, warnings | all | all | no |
| **Explain** | answers, reports, design docs, READMEs, PR descriptions | all, word limits relaxed | all | light |
| **Persuade / personal** | emails, posts, essays, cover letters | clarity rules only (1, 2, 3, 5) | all | yes |

When the user gives text to edit, keep its register. Do not turn a friendly email into a maintenance manual.

## STE core (the subset)

These are the rules that improved clarity most in practice. Each one states the reason so you can judge edge cases. `references/ste-rules.md` has before/after examples and lists the STE rules this skill leaves out on purpose.

1. **One idea per sentence.** If a sentence has two main clauses joined by "and", "which", or a semicolon, split it. Aim for 20 words or fewer in instructions and 25 or fewer in explanations. Treat these numbers as alarms, not hard caps. A reader who must backtrack to parse a sentence has lost time.
2. **Active voice. Name the actor.** "The loader parses the file", not "the file is parsed". Passive voice hides who does what, and in technical text that is often the exact fact the reader needs. Use passive only when the actor is unknown or does not matter.
3. **One term for one thing.** Pick a name for each concept and use it every time. Do not cycle synonyms ("the service... the backend... the API layer") for one thing. Readers assume a new word means a new thing.
4. **One topic per paragraph. Topic sentence first.** Put the conclusion or main point in the first sentence. Keep paragraphs to about six sentences. A reader who skims first sentences should get the whole argument.
5. **Verbs for actions, not nouns.** "Configure the proxy", not "perform the configuration of the proxy". "Decide", not "make a decision". Nominalizations add words and hide the action.
6. **Simple tenses.** Present for facts that are true now, past for what happened, future ("will") for what will happen. Avoid stacked forms like "would have been being processed".
7. **Do not drop small words.** Keep articles and "that" where they help parsing. Spell out arrows (→), symbols, and abbreviations the reader may not know. Telegraphic text ("Fixed config, updated deps, tests pass") is fine for commit logs, but in explanations it makes the reader rebuild the sentence.
8. **Stack no more than three nouns.** "Connection pool timeout value" is the limit. Rewrite "database connection pool timeout configuration override" as "the setting that overrides the timeout for the database connection pool".
9. **Condition before action.** "If the build fails, delete the cache", not "Delete the cache if the build fails". The reader must know whether a step applies before they do it.
10. **One action per step, in order.** Write instructions in the imperative ("Run", "Open", "Set"). Number them. Put two actions in one step only when they happen at the same time.
11. **Warnings before the step, with the consequence.** "Back up the database first. The migration deletes the `sessions` table." A warning after the step comes too late.
12. **Specific words over vague ones.** "Restart the worker", not "address the issue". "Took 4 minutes", not "took a while". If you cannot be specific, say what you do not know.

## AI tells to remove

Scan for these in every register. `references/ai-tells.md` has the full list with fixes (33 patterns from the Anthropic and Cursor versions of unslop). These are the ones that appear most often:

- **Puffery and promo words:** pivotal, testament, landscape, vibrant, groundbreaking, seamless, robust, "plays a crucial role".
- **AI vocabulary:** delve, additionally, crucial, enhance, foster, leverage, utilize, underscore, showcase, intricate, tapestry.
- **Fancy "is":** "serves as", "stands as", "boasts". Write "is" or "has".
- **"Not just X, but Y"** and forced groups of three.
- **Superficial -ing tails:** "..., highlighting the importance of X". Delete, or state the fact.
- **Em dashes and en dashes.** Do not use them as punctuation. Use a period or a comma.
- **Colons as connectors** mid-sentence, bold-label bullets that repeat the line ("**Speed:** Speed improved"), Title Case Headings, decorative emoji.
- **Chatbot frame:** "Great question!", "Certainly!", "Hope this helps!", "Happy to help with anything else."
- **Filler and hedging:** "it is important to note that", "in order to", "could potentially".
- **Generic endings:** "The future looks bright." End on the last real fact or the next action.
- **Mannered prose:** slogans, code described as if it were a person ("the scheduler wants to retry"), figurative verbs ("the config rides along"). Say the literal thing.
- **Over-compression:** arrows, symbol-speak, and verbless fragments ("bad date → exit 2, no write"). Write the whole sentence.
- **Feelings instead of mechanisms:** "a seamless developer experience". Name the mechanism or the number. If the sentence fits unchanged in any other project's docs, cut it.

## Voice rules (persuade / personal register only)

Removing tells leaves text that is clean but flat. Flat text also reads as machine-made. For text that must sound like a person:

- **Take a position.** React to the facts. "This works, but the setup cost is high" beats a neutral list of pros and cons.
- **Vary sentence length.** A short one lands a point. A longer one can carry the context that the short one needs.
- **Be concrete.** "The agent ran until 3 a.m. and opened 40 PRs" beats "this is concerning".
- **Use "I" and "we"** when the writer is a person.
- **Do not over-structure.** Not every email needs headers and bullets. Perfectly symmetric structure reads as generated.

## Write mode: shape of an answer

When Claude writes its own response:

- **Answer first.** The first sentence answers the question or states the result. Context and method follow.
- **Fit the format to the content.** Use a numbered list for steps, a table for comparisons across the same attributes, and prose for reasoning. Use headers only when the response is long enough to need navigation.
- **Define a term once, at first use.** Do this only for terms this reader probably does not know.
- **Cut the meta.** Do not announce what you are about to say ("Let me explain...", "Here's a breakdown:"). Say it.
- **Say what you did not do.** State skipped steps, failed checks, and uncertainty plainly, in one sentence each. Clear writing includes clear limits.

## Edit mode: process

1. Identify the register and the writer's voice. Keep both.
2. Fix meaning problems first: unclear actors, ambiguous terms, buried conclusions. Then apply the STE core for the register. Then remove AI tells.
3. Keep every fact, number, name, link, and code span. Do not add claims. If a sentence needs a source you do not have ("experts say"), cut it or flag it. Do not invent one.
4. Self-check: read the result and ask, "What still makes this sound generated or hard to follow?" Fix what you find.
5. Return the rewritten text first. Then, if the edit was more than light, add a short list (three to six items) of the main changes, so the writer can learn the pattern. Skip the list if the user asked only for the text.

If the writer's text is already clear, say so and make only the small fixes. Do not rewrite for the sake of change.
