# Recorded answers, 2026-11-22: a skill that drives the ontology update

Copied from the project thread of the KPI Store 1.2 work. The agent received the owner's messages directly. The
times were not recorded; the messages are in the order they were sent. The agent's messages are quoted in full
with their bold markers removed. The owner's are exact.

## The owner

```text
release folder is enough.

Also given what we have done, will it be beneficial to vcreate an agent skill to drive this ontology update? let me know.
```

## The agent

```text
On the skill: yes, I think it would help, as long as it stays thin. The release repo already ships agent skills in `skills/`: `ontology`, `ontology-to-lpg`, `ontology-visualization`, `rdf-store` and `clear-writing`. All of them are about building the ontology or loading it. None of them covers what your team will do most often, which is taking a filled-in KPI form and getting the change into the ontology.

What the skill would add over the handout alone
- It runs the steps in the right order. With #40, `propose` can print an order such as "apply the domain activation, then the process map request, then the KPI, one run each". A person can easily get that wrong. An agent follows it exactly.
- It explains refusals. The commands refuse rather than guess, for example "the proposal X follows Y, which this release has not applied". Someone who has never built an ontology needs that turned into "do this next". An agent can read the refusal and the handout and say it plainly.
- It shows the plan before anything changes. The agent shows the proposed change in plain words and asks for a yes before it runs `apply`.

How I would keep it safe
- No rules of its own. The skill points to the handout and the commands, so there is still one source of truth and nothing to drift. It would be short: when to use it, which handout section covers each step, and "stop and explain when a command refuses".
- Tested by a real run. The doc test can't run a skill. So the check would be a fresh agent following the skill on the rehearsal forms, from intake form to applied change, with the result checked by `check.sh`.

The cost is one more pull request plus a rehearsal run, about one review cycle.

What I don't know is whether your team will work with an agent such as Claude Code or Codex. If they won't, the handout already covers everything and the skill adds nothing for them.

My recommendation is to add it to 1.2 as its own pull request. It would go after the folder rename and before the version rename, so it ships in the 1.2 zip. This changes the plan, so it's your call: should I add it?
```

## The owner

```text
yes, add the skill to 1.2
```

## The owner

```text
We probably should also update the master personal agent report. That's the personal agent skill repo, and then we copy from there to this release
```

## The owner

```text
The reason why we removed Docker when we copied the skill over to the release folder was because in the target Windows environment that we are going to use we did not have Docker right so in this 1.2 1.2 as well we are developing not based on Docker so the personal agent skill should also have a master skill but when it's going to 1.2 right it should not have docker container in it does this make sense
```
