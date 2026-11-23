# A skill that drives a change to a released ontology

Status: Decided  
Date: 2026-11-22  
Answers: [2026-11-22-ontology-change-skill-answers.md](2026-11-22-ontology-change-skill-answers.md)

## Context

The KPI Store release ships a handout, `HANDOUT.md`, whose commands take a filled change form to a released
change. The people who will use it have never built an ontology. The agent recommended a thin skill that runs
those commands in order, shows the plan before an apply, and explains a refusal, while holding no command of its
own (the answers file has the recommendation in full).

## Decision

The owner answered "yes, add the skill to 1.2". The owner then set where it lives: "We probably should also
update the master personal agent report. That's the personal agent skill repo, and then we copy from there to
this release". For a skill copied into the release, the owner added that the copy "should not have docker
container in it".

## Alternatives considered

- **The handout alone, with no skill.** It holds every command, and the release's doc test keeps them right. The
  agent's recommendation names the limit: a person who has never built an ontology can get the apply order wrong
  and cannot always turn a refusal into the next step. It also says the skill adds nothing when the team does
  not work with an agent.
- **A skill that holds the commands itself.** The recommendation chose against it: pointing to the handout keeps
  "one source of truth and nothing to drift". The release's doc test checks the handout's commands; it cannot
  check a copy in a skill.

## Evidence

- The recommendation and the owner's answers, in the answers file.
- The rehearsals of 2026-11-22: fresh agents followed the skill on scratch copies of the release, with a KPI form
  routed to a domain activation and a process map request, and with no form at all.
  `skills/data/ontology-change/README.md`, "Status", says what each showed and what was not rehearsed.

## Implementation choices

These are the agent's choices, not the owner's words.

- The skill is `skills/data/ontology-change`. It names the release's handout and guide sections by heading and
  gives no command of its own, so the release's doc test keeps the commands right and this repository holds no
  consuming project's data.
- It needs no Docker, so the release copy and this master are the same files.
- A fresh agent rehearses it on a scratch copy of the release before each release that ships it.
