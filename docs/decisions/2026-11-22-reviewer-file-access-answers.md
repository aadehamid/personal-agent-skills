# Recorded answers, 2026-11-22: what reviewers may read

Copied from the project thread. The agent received the owner's messages directly. Times are UTC. The agent's
messages are quoted in full with their bold markers removed. The owner's are exact.

## 13:47:07, the owner

```text
What if pi needs to access file  that an agentcreats outside of the repo.
```

## 13:47:21, the agent

```text
Then Pi should get that file, so "stay inside the clone" was too strict as I proposed it. The better rule is that Pi reads the clone plus whatever it is handed, and doesn't go searching for anything else.

Today `pi-review.sh` has no way to hand Pi a file. The agent can only mention a path in the review request, and Pi can read anywhere on your Mac.

I'd change it in three ways:
1. Add an `--attach <path>` option, which the agent repeats for each outside file, such as a generated report, a log or a test output.
2. Have the script copy those files into an evidence folder beside the clone before Pi starts. Pi then reviews a fixed copy, even if the agent later changes the original, and the copy is deleted with the clone.
3. Tell Pi to read only the clone, that folder and its own scratch files. If it needs something else, it names the missing file in its report. The agent then attaches it and reruns, which took 46 to 87 seconds for the scoped reviews last night.

Think of handing an auditor a folder of documents instead of the keys to the filing room.

Two limits apply. Anything attached goes to Pi's cloud model, so agents must not attach secrets. And point 3 is an instruction Pi could ignore. Truly blocking other folders needs a sandbox (the operating system refusing the read), which is a bigger change I'd only make if Pi strays again.

Reply "yes" and I'll build this version, with tests, as a pull request after Antigravity ships.
```

## 13:48:56, the owner

```text
Shouldn’t this apply to all agents
```

## 13:49:10, the agent

```text
Yes, it should. The rule for every agent would be: read what the task gives you, name what's missing, and don't go searching your personal folders for it. It works slightly differently for reviewers and working agents.

Reviewers (Pi, Kimi, Codex, Cursor CLI) get the strict version: the repo, the review skill's own files, their scratch files and whatever was attached. All four can wander today. Kimi runs with no sandbox and never asks permission, and the Codex sandbox as we configure it limits writing but not reading. All four review scripts would get the same `--attach` option and instruction. The Cursor bot on GitHub needs no change, because it runs in the cloud and can't see your Mac.

Working agents (Claude and any other agent doing the task) need more room, because they move between your repos. They could read the task's repos, the paths you or the task name, their own temporary files, and tool and skill folders. For anything else they would ask you before searching broadly. I would have tripped this rule myself last night, when I searched your agent session logs for your November 8 words without asking.

The rule would live once in `way-of-working`, which agents load before repo work. The scripts would carry the short reviewer version, with a test that fails if the four copies drift apart. It is still an instruction rather than a hard block.

It fits in one pull request, with your words saved as the decision record. Reply "yes" to approve both versions, or "reviewers only" for the first. I'll start after Antigravity ships.
```

## 13:50:45, the owner

```text
Working agents should have access to files and folders outside if the repo
```

## 13:50:50, the agent

```text
Agreed. Working agents keep their access to files and folders outside the repo, with no new rule and no need to ask you first. I've dropped that half of the proposal.

That leaves reviewers only. Pi, Kimi, Codex and Cursor CLI would read the repo, their skill and scratch files, and whatever the working agent attaches with `--attach`. The working agent can attach a file from anywhere, so a reviewer can still get an outside file when it needs one.

Shall I build that reviewers-only version after Antigravity ships? A "yes" is enough.
```

## 13:51:20, the owner

```text
Yes
```

## 13:51:47, the agent, after the answer

```text
Your yes is saved. Antigravity hasn't shipped yet: pull request 105 is open and being handled in Set up reviews and speed up CI. I'm watching for its merge for the next 4 hours and will start from the new main when it lands, since both changes edit the same files.

That pull request adds Antigravity as a reviewer with its own script, so I'll include it in the reviewer rule, making five scripts instead of four. Working agents are untouched. You don't need to do anything.
```

The two links in that last message are shown as their titles.
