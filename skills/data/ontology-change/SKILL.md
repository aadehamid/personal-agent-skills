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

**The release's guides are the only source for commands.** Every command and option is in `HANDOUT.md` at the top of the release folder, or in the section of `HOW-TO-UPDATE.md` or `kpi-intake/README.md` that this skill or the handout names. Run them as written there, and read what each command prints: its own output says what it found and what to do next. This skill gives no command of its own. It names the guides' sections by their headings; the handout numbers its sections ("3. Make an everyday change with a form"), and this skill leaves the number out.

The person is usually not an ontology builder. Say what a step does in their words, with one sentence each, and name a file by its path.

## Before the steps: is this a change with a form?

- **No filled form yet** (the person asks to add a KPI, a measure, a system, a role, a process or a module): tell them which form fits, from the table in the handout's "Make an everyday change with a form", and where the blank forms are, as that section says. Who signs depends on the form and its route: take it from the form's own section, the one that section's table names in `HOW-TO-UPDATE.md`. For a KPI, `kpi-intake/README.md`, "Who does what" and "How an interview runs", say how the interview fills the form. Stop until a filled form comes back.
- **The person wants an AI's help with a form or with new modelling:** follow the handout's "Let an AI help" only as far as the signatures: in "Suggestions for a form", until the form holds the answers the person accepted and the signers have signed it; in "A draft of new modelling", through its step 4, where the three signers sign. Do not run that section's propose-and-apply step. With the signed form, start the steps below at step 1, so the person sees the plan and says yes before anything is applied.
- **The person changed the forms' settings** (`kpi-intake/settings.toml`): follow the handout's "After you change the forms' settings" instead of these steps.
- **The person has a newer release:** follow the handout's "Upgrade the tools from a newer release" instead of these steps.

## The steps

1. **Find the release and the form.** Read the handout's "What is inside the release" and "The conventions". Then find the row for the change in the table of "Make an everyday change with a form" (a new module: "Add a module"), and read the section of `HOW-TO-UPDATE.md` it names. With a KPI form and the forms it waits on, read each form's section and "Propose a KPI with the forms it waits on".
   Done when you can name the release folder, the filled form, the form's kind, and the guide section for it, and the form sits in a folder beside the release folder, not inside it. If it is inside, ask the person to move it; do not move it yourself.
2. **Check each form.** Run the form check that step 1 of the handout's "Make an everyday change with a form" gives, once per form. It changes nothing. A form filled in the workbook is checked by naming the form with `--form`, as `kpi-intake/README.md`, "Where an answer routes the request", shows.
   Done when each form's check prints the line the handout shows for a complete, signed form (a line about the next step follows it), with one exception: a KPI form whose only open items are routes from question 1.5 (a domain, to a domain activation) or from questions 1.1 to 1.3 (a business area, a process or a step, to a process map request). Its check then prints "Result: not complete", names each route and the form it needs, and exits with status 1. A route from 6.1 (a new role) or 6.3 (a new value stream step) is not part of the exception: `HOW-TO-UPDATE.md`, "Propose a KPI with the forms it waits on", says it still needs a specialist, so tell the person that and stop. Check those forms too; when each of them is complete and signed, the KPI form goes on with them to step 3. When a routed form is missing, tell the person which form to fill and who signs it, as the check says. For anything else the check names as missing, tell the person, and stop until the form comes back. Never answer a question or sign for anyone.
3. **Turn the forms into proposals.** Run the propose step of the same section. It changes nothing in the ontology. A KPI form that waits on other forms goes in one propose run with those forms, as `HOW-TO-UPDATE.md`, "Propose a KPI with the forms it waits on", shows; every other form gets a run of its own. A propose or apply run can take several minutes: wait for it to end, and never start a second run beside it.
   Done when it has named each proposal folder it wrote. When it prints an order to apply them in, write that order down exactly: step 5 follows it.
4. **Show the plan, and get a yes.** Read each proposal's `summary.txt`. Tell the person what the change adds, which modules it reaches and their route (patch, minor or major), who signed, the apply order when there is one, and every note that the summaries and the step 2 checks address to the Architect or raise about the form. Say when there is none. Ask about anything else in a form that looks wrong to you, such as an answer that reads as copied from an example; the person decides. The handout asks the Architect to read the summary too.
   Then stop and wait: end your turn with the plan and the question.
   Done when the person has said yes to these proposals in this conversation, after seeing the plan. A yes to an earlier change does not carry over.
5. **Apply, one proposal per run, in the printed order.** Run the apply step with each proposal folder. It works in a temporary copy and writes and commits the release only when every check passes.
   Run each apply once, without a pipe, so its exit status and last lines are its own, and show the last commit after each. If you are not sure whether a run happened, look at the last commit first: a proposal whose commit is there is applied.
   Done when each run prints a line that starts `Done.` and names what changed, and after it a line that says what to run next; and the last commit, shown as the handout's step "See the commit" shows it, names the proposal.
6. **Check the release and load the stores, once, after the last apply.** Follow the handout's section "Check the release and recover", its part "After every change", in its order: the full check, the load, the store check. Only when the line after `Done.` said that no store needs loading, for every apply, is the full check enough; one such line among others is not.
   Done when each step ends on the line the handout names for it.
7. **Give people the new forms.** Follow the handout's "Refresh what people use", its part "After a change of sections 3 to 5: give people the new forms". Ask the person for the path of the team's shared folder; do not guess it.
   Done when that part's last step ends on the line the handout names.

## When a command refuses or fails

A refusal changes nothing; the release is as it was. Do this, in this order:

1. Quote the line that refused, word for word, to the person.
2. Find what it means: the refusal usually says the next step itself (for example, which proposal to apply first). If not, read the guide section of step 1 and, for a store run, the handout's "When a run fails" and the runbook section it names.
3. Tell the person the next step in one or two sentences, and do it only when it is one of the steps above. Anything else (a changed form, an edited setting, a skipped check) is the person's decision: say what you would do and wait.

Never get past a refusal another way: no other option, no edit of a table, a Turtle file or a generated file, no rerun with a check left out unless the handout's "When a run fails" says so for that case and the person agrees.

## Rules at every step

- **Never replace or reset a store on your own.** The handout's "Replace what a store holds, or reset every store" deletes data and needs written authorization for the exact environment first. Run it only when the person asks for it and has that authorization. The reset asks for a typed word: only the person types it.
- **Keep secrets out of the conversation.** Never print the local settings file or a sign-in file; name a key when you need to, never its value.
- **Filled forms, proposals, passwords and local settings files stay outside the release folder.** The handout's "The conventions" says so for passwords, settings files and filled forms, because the release folder is zipped and uploaded; each form's section of `HOW-TO-UPDATE.md` says so for the filled form and its proposals, because the apply refuses a release with files that are not committed. The blank forms and the forms' settings, `kpi-intake/settings.toml`, belong to the release. The release's commands rebuild the forms (an apply, a correction's cut); the person changes the settings only as the handout's "After you change the forms' settings" says. Never edit either by hand yourself.
