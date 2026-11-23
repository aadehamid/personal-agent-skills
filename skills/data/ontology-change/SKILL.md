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

1. **Find the release and the form.** Read the handout's "What is inside the release" and "The conventions". Then find the row for the change in the table of "Make an everyday change with a form" (a new module: "Add a module"), and read the section of `HOW-TO-UPDATE.md` it names. With a KPI form and the forms it waits on, read each form's section and "Propose a KPI with the forms it waits on".
   Done when you can name the release folder, the filled form, the form's kind, and the guide section for it, and the form sits in a folder beside the release folder, not inside it. If it is inside, ask the person to move it; do not move it yourself.
2. **Check each form.** Run the form check the handout's first step gives, once per form. It changes nothing.
   Done when each form's check ends with the line the handout shows for a complete, signed form, with one exception: a KPI form whose only things to settle are routes to a domain activation or a process map request (the check lists them under "Routing", and ends "not complete" with exit status 1). Check those forms too; when each of them is complete and signed, the KPI form goes on with them to step 3. When a routed form is missing, tell the person which form to fill and who signs it, as the check says. For anything else the check names as missing, tell the person, and stop until the form comes back. Never answer a question or sign for anyone.
3. **Turn the forms into proposals.** Run the propose step. It changes nothing in the ontology. A KPI form that waits on other forms goes in one propose run with those forms, as `HOW-TO-UPDATE.md`, "Propose a KPI with the forms it waits on", shows; every other form gets a run of its own. A propose or apply run can take several minutes: wait for it to end, and never start a second run beside it.
   Done when it has named each proposal folder it wrote. When it prints an order to apply them in, write that order down exactly: step 5 follows it.
4. **Show the plan, and get a yes.** Read each proposal's `summary.txt`. Tell the person what the change adds, which modules it reaches and their route (patch, minor or major), who signed, the apply order when there is one, and every line the summaries and the step 2 checks address to the Architect or flag about the form (such as "For the Architect" or "Checks against the ontology"). Say when there is none. The handout asks the Architect to read the summary too.
   Then stop and wait: end your turn with the plan and the question.
   Done when the person has said yes to these proposals in this conversation, after seeing the plan. A yes to an earlier change does not carry over.
5. **Apply, one proposal per run, in the printed order.** Run the apply step with each proposal folder. It works in a temporary copy and writes and commits the release only when every check passes.
   Run each apply once. If you are not sure whether a run happened, look at the last commit first: a proposal whose commit is there is applied.
   Done when each run ends with the line that starts `Done.` and names what changed, and the last commit, shown as the handout's step "See the commit" shows it, names the proposal.
6. **Check the release and load the stores, once, after the last apply.** Follow the handout's section "Check the release and recover", its part "After every change", in its order: the full check, the load, the store check. When every apply's last line said no store needs loading, the full check is enough.
   Done when each step ends on the line the handout names for it.
7. **Give people the new forms.** Follow the handout's "Refresh what people use": after a change made with a form, its part "After a change of sections 3 to 5"; after the person changed the forms' settings, its part "After you change the forms' settings". Ask the person for the path of the team's shared folder; do not guess it.
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
