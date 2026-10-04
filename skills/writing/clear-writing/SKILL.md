---
name: clear-writing
description: >-
  The user's house style for prose, required for any writing or rewriting task. Check this skill first when the user asks for words a person will read: an update for their manager, a short explainer for a CFO or board, an email, a cover letter, a PR description, a README, or a doc. Also check it first when they complain that existing text is too long, full of buzzwords, robotic, or "sounds like ChatGPT/AI" and want it cut down, made plainer, or made to sound human. The text can be pasted, in a file, or in a git branch. When the user says "wait what", "I don't follow", or asks you to explain your last message again, this skill re-pitches it. If the user says "calibrate my writing rules", "recalibrate", or "update my writing rules from my sessions", this skill owns that task. Skip it when no prose for people is being written: code, tests, translation, slide layout, linters, text-processing scripts, typo-only fixes, and documents an agent reads (skills, CLAUDE.md, AGENTS.md), which writing-for-agents covers.
---

# Clear writing

Readers spend more and more time reading model output. This skill makes that output fast to understand and plain enough that nothing in it reads as machine-written.

It combines three sources:

- **ASD-STE100.** A controlled English written for aircraft maintenance manuals. Its rules give short sentences, one meaning per word, and active voice. The full spec is too strict for most work, so this skill uses a subset ("about 80% of the way to STE").
- **Plain-style targets.** The habits of a careful human writer, written as targets. The patterns that mark text as AI-written are listed in `references/ai-tells.md`, which you read only for the final check.
- **Personal calibration.** Rules chosen by checking which ones would have helped in the user's own past sessions.

## Pick the mode

| The request | Mode |
|---|---|
| Claude is writing its own answer, explanation, report, or doc | **Write** |
| The user gives text and asks to improve, rewrite, tighten, or unslop it | **Edit** |
| The user did not understand a message ("wait what", "I don't follow", "huh?", "explain that again", `/wait-what`) | **Re-pitch** |
| The user asks to tune, calibrate, or personalize these rules | **Calibrate**. Read `references/calibrate.md` and follow it. |

If `calibration.md` exists in this skill folder, read it first in every mode. It holds the user's personal rule weights and overrides the defaults below where they conflict.

Documents that an agent reads (a skill, CLAUDE.md, AGENTS.md, a prompt) belong to the writing-for-agents skill. Use that skill for them.

## Pick the register

The STE rules help most where the reader must understand or act. They hurt when the text must persuade, entertain, or sound like a person. Choose the register from the text's purpose, then apply rules to match.

| Register | Examples | STE core | Plain-style targets | Voice rules |
|---|---|---|---|---|
| **Instruct** | steps, runbooks, setup guides, warnings | all | all | no |
| **Explain** | answers, reports, design docs, READMEs, PR descriptions | all, word limits relaxed | all | light |
| **Persuade / personal** | emails, posts, essays, cover letters | clarity rules only (1, 2, 3, 5) | all | yes |

When you edit, keep the register of the original. A friendly email stays friendly.

## STE core (the subset)

These are the rules that improved clarity most in practice. Each one states the reason so you can judge edge cases. `references/ste-rules.md` has before/after examples and lists the STE rules this skill leaves out on purpose.

1. **One idea per sentence.** When a sentence holds two main clauses, make it two sentences. Aim for 20 words or fewer in instructions and 25 or fewer in explanations. Treat these numbers as alarms, not hard caps. A reader who must backtrack to parse a sentence has lost time.
2. **Active voice. Name the actor.** "The loader parses the file." In technical text, who does what is often the exact fact the reader needs. Keep the passive only when the actor is unknown or does not matter.
3. **The reader's terms, one per concept.** Use the names the reader already knows, in this order: the project's `GLOSSARY.md` (if the repo has several, `GLOSSARY-MAP.md` says which one applies), the names in the code and docs, then the words the user has used in this conversation. When you need a term the reader has not seen, define it in plain words at first use, or describe the thing instead. An internal label, such as a skill's mode name or a variable name, counts as a term the reader has not seen. Once a concept has a name, repeat that exact name. Readers take a new word to mean a new thing.
4. **One topic per paragraph. Topic sentence first.** Put the conclusion or main point in the first sentence. Keep paragraphs to about six sentences. A reader who reads only the first sentences should get the whole argument.
5. **Verbs for actions.** "Configure the proxy." "Decide." A verb names the action in one word where a noun phrase ("perform the configuration of") needs four.
6. **Simple tenses.** Present for facts that are true now, past for what happened, "will" for what will happen.
7. **Complete sentences.** Write sentences with their articles, verbs, and "that" where it helps parsing. Spell out arrows, symbols, and abbreviations the reader may not know. Note style ("Fixed config, updated deps") suits commit logs. In explanations, give the reader the whole sentence.
8. **Three nouns in a row at most.** "Connection pool timeout value" is the limit. For a longer stack, unpack it: "the setting that overrides the timeout for the database connection pool".
9. **Condition before action.** "If the build fails, delete the cache." The reader must know whether a step applies before they do it.
10. **One action per step, in order.** Write instructions in the imperative ("Run", "Open", "Set"). Number them. Put two actions in one step only when they happen at the same time.
11. **Warnings before the step, with the consequence.** "Back up the database first. The migration deletes the `sessions` table."
12. **Specific words.** "Restart the worker." "Took 4 minutes." When you cannot be specific, say what you do not know.

## Plain-style targets

Write the way a careful human expert writes. These targets apply in every register:

- **Plain words.** "use", "help", "start", "many", "is", "has". Describe events by what happened, without adjectives that grade their importance.
- **The point, stated directly.** Say what a thing is, without first saying what it is not. List as many items as the facts support, whether that is one, two, or five.
- **Mechanisms and numbers.** Name what the thing does ("each site sends a reading only when the value changes") or give the measurement. A sentence that would fit unchanged in another project's docs has nothing to say about this one, so replace it with a fact.
- **Literal phrasing.** Describe code and systems as what they are and do. Use the plain noun and verb.
- **Named sources.** Attribute a claim to a named person, document, or dataset, or state it as your own view.
- **Periods and commas for separation.** End the sentence when two thoughts need to be apart. Use a colon only to introduce a list or an example.
- **Quiet formatting.** Sentence-case headings. Bold only what the reader must not miss, such as a warning. Plain text in headings and bullets. Straight quotes.
- **A direct start and a useful end.** Begin with the content. End on the last fact, the open question, or the next action.
- **Measured confidence.** State a claim once, with one hedge at most when the doubt is real.

## Voice rules (persuade / personal register only)

Plain text can still be flat, and flat text also reads as machine-made. For text that must sound like a person:

- **Take a position.** React to the facts. "This works, but the setup cost is high."
- **Vary sentence length.** A short one lands a point. A longer one can carry the context that the short one needs.
- **Be concrete.** "The agent ran until 3 a.m. and opened 40 PRs."
- **Use "I" and "we"** when the writer is a person.
- **Match structure to length.** A short email is a few paragraphs of prose. Save headers and bullets for documents that need navigation.

## Final check

Read `references/ai-tells.md` and check the draft against each of its 33 patterns. Fix every match. Run this check in Edit mode, and in Write mode for a deliverable (a file, an email, a post, a doc). For a chat reply, the targets above are enough.

## Write mode

When Claude writes its own response:

- **Answer first.** The first sentence answers the question or states the result. Context and method follow. A yes/no question gets a yes or a no in the first sentence.
- **Fit the format to the content.** A numbered list for steps, a table for comparisons across the same attributes, prose for reasoning. Headers only when the response is long enough to need navigation.
- **Report limits plainly.** State skipped steps, failed checks, and uncertainty, one sentence each.

**Done when:** the first sentence states the answer or result, every term is one the reader knows or is defined at first use, and (for a deliverable) the final check finds no pattern.

## Edit mode

1. Identify the register and the writer's voice. Keep both.
2. Fix meaning first: unclear actors, ambiguous terms, buried conclusions. Then apply the STE core for the register. Then the plain-style targets.
3. Keep every fact, number, name, link, and code span. Add no new claims. A sentence that leans on a source you do not have ("experts say") gets cut or flagged for the writer.
4. Run the final check.
5. Return the rewritten text first. If the edit was more than light, add a short list (three to six items) of the main changes, so the writer can learn the pattern. Skip the list if the user asked only for the text.

If the text is already clear, say so and make only the fixes that improve it.

**Done when:** every paragraph has been checked against the STE rules for its register, the final check finds no pattern, and every fact, number, name, link, and code span from the original is still present.

## Re-pitch mode

The user did not understand a message, usually your last one. Explain the same content again so that it lands this time.

1. Find the message that did not land and the point it was trying to make.
2. Start with context in one or two sentences: where the work stands and why this point matters now.
3. State the point in the Instruct register: full STE core, sentences of 20 words or fewer.
4. Use the reader's terms (STE rule 3). Replace every internal label from the original with its plain meaning.
5. If the user must decide or do something, end with that, in one sentence. For a yes/no question, give the yes or no.

Make the re-pitch shorter than the original. A new explanation works better than the old one reworded, so pick a new angle: a concrete example, the one fact the rest depends on, or a before/after.

**Done when:** the reply has the context sentence, the point in sentences of 20 words or fewer, no term the user has not seen without a definition, and the decision or action (if there is one) as its last sentence.
