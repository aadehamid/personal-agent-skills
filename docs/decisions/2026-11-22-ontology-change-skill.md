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

## Implementation choices

These are the agent's choices, not the owner's words.

- The skill is `skills/data/ontology-change`. It names the release's handout and guide sections by heading and
  gives no command of its own, so the release's doc test keeps the commands right and this repository holds no
  consuming project's data.
- It needs no Docker, so the release copy and this master are the same files.
- A fresh agent rehearses it on a scratch copy of the release before each release that ships it.
