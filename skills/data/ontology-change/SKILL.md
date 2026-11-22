---
name: ontology-change
description: >-
  Drives a change to a released ontology from a filled change form to a checked, committed release, with the
  release's own commands: check the form, turn it into a proposal, show the plan to the person, apply it, run the
  release's check, load and check the stores, and give people the new forms. Use when someone hands you a filled
  form (a KPI intake, a term change, a reference item, a domain activation, a process map request, a new module)
  for an ontology release that ships a handout of its commands (HANDOUT.md), asks you to add a KPI, a measure, a
  system, a role, a process or a module to that ontology, or asks what a refusal from the release's propose or
  apply command means. Not for building an ontology from nothing (the ontology skill) or loading one into Neo4j or
  a triple store by hand (ontology-to-lpg, rdf-store).
---

# Ontology change

You drive the release's commands; you never do their work. The commands check, build and release the ontology, and they refuse rather than guess. Your job is to run them in the right order, show the person what each will do before it changes anything, and turn each refusal into the next thing to do, in plain words.

**The release's handout is the only source for commands.** Every command, option and expected line is in `HANDOUT.md` at the top of the release folder, and in the sections of the guides it names. Run them as written there. This skill names the handout's parts by their headings; it holds no command of its own.

The person is usually not an ontology builder. Say what a step does in their words, with one sentence each, and name a file by its path.

## The steps

1. **Find the release and the form.** Read the handout's "What is inside the release" and "The conventions". Then find the row for the change in the table of "Make an everyday change with a form" (a new module: "Add a module"), and read the section of `HOW-TO-UPDATE.md` it names.
   Done when you can name the release folder, the filled form, the form's kind, and the guide section for it, and the form sits in a folder beside the release folder, not inside it. If it is inside, ask the person to move it; do not move it yourself.
2. **Check the form.** Run the form check the handout's first step gives. It changes nothing.
   Done when it ends with the line the handout shows for a complete, signed form. If it does not, tell the person which answers or signatures are missing, as the check names them, and stop until the form comes back. Never answer a question or sign for anyone.
3. **Turn the form into a proposal.** Run the propose step. It changes nothing in the ontology.
   Done when it has named the proposal folder it wrote. When a KPI form waits on a domain activation or a process map request, the propose step takes the forms together and prints the order to apply them in, one run each: copy that order exactly, and see `HOW-TO-UPDATE.md`, "Propose a KPI with the forms it waits on".
4. **Show the plan, and get a yes.** Read each proposal's `summary.txt`. Tell the person what the change adds, which modules it reaches and their route (patch, minor or major), who signed, and what the Architect must still do outside the form. The handout asks the Architect to read the summary too.
   Done when the person has said yes to these proposals in this conversation, after seeing the summary. A yes to an earlier change does not carry over.
5. **Apply, one proposal per run, in the printed order.** Run the apply step with each proposal folder. It works in a temporary copy and writes and commits the release only when every check passes.
   Done when each run ends with the line that starts `Done.` and names the changed modules and their versions, and the last commit, shown as the handout's step "See the commit" shows it, names the proposal.
6. **Check the release and load the stores.** Follow the handout's "Check the release and recover", "After every change", in its order: the full check, the load, the store check.
   Done when each step ends on the line the handout names for it.
7. **Give people the new forms.** Follow the handout's "Refresh what people use", the part that fits the change.
   Done when that part's last step ends on the line the handout names.

## When a command refuses or fails

A refusal changes nothing; the release is as it was. Do this, in this order:

1. Quote the line that refused, word for word, to the person.
2. Find what it means: the refusal usually says the next step itself (for example, which proposal to apply first). If not, read the guide section of step 1 and, for a store run, the handout's "When a run fails" and the runbook section it names.
3. Tell the person the next step in one or two sentences, and do it only when it is one of the steps above. Anything else (a changed form, an edited setting, a skipped check) is the person's decision: say what you would do and wait.

Never get past a refusal another way: no other option, no edit of a table, a Turtle file or a generated file, no rerun with a check left out unless the handout's "When a run fails" says so for that case and the person agrees.

## Rules at every step

- **Ask before anything that empties or replaces a store.** The handout's "Replace what a store holds, or reset every store" types a word to confirm; only the person gives it.
- **Keep secrets out of the conversation.** Never print the local settings file or a sign-in file; name a key when you need to, never its value.
- **Forms and proposals stay outside the release folder,** as the handout says, so an upgrade never touches them.
- **Upgrades are not changes.** When the person has a newer release, follow the handout's "Upgrade the tools from a newer release" instead of these steps.
