# Recorded answers, 2026-11-22: the Antigravity lock

## Relayed by the project's assistant, as chosen at 15:20 UTC

The agent that wrote this file did not receive this itself. The card's question and its other options were not received, so they cannot be quoted. The option chosen on
the card, which the assistant said was about agy's `allowNonWorkspaceAccess`:

```text
Turn it off for reviews
```

## Relayed by the project's assistant, as written in the project chat at 17:59:22 UTC

```text
Okay ship it.
```

## 18:02:52 UTC

The message it answered, sent by the agent at about 18:00 UTC, in full. Markdown markers are stripped.

```text
Hamid, reply "ship it" in this thread and I'll ship the Antigravity lock straight away. I got your "Okay ship it." only as a copy in the assistant's note, because project-chat messages aren't forwarded to me on your Mac. I don't push on a relayed yes when the bot can merge by itself. Sorry for the extra step.

Since you asked "What are we shipping?", here it is simply. When Antigravity reviews your code, it currently can read any file on your Mac and can run cp and git clone without asking, so what it reads could reach Google. The change puts each review in a locked room: it reads only a copy of the repo plus files handed to it, and can't run commands, use MCP tools or write files. Your own Antigravity sessions and saved settings don't change.

Three limits: web search stays open (only the prompt forbids it), a review that tries to reach outside is cancelled and the next reviewer takes over, and the other reviewers have no such lock.

It's ready as of 17:59:49 UTC: branch at 8b87b5a, main unchanged at 235f0c7, check.sh passing, proof passed, nothing pushed, repo private. After your reply it takes about 15 minutes: record your words, check, push, one public window for CI, merge by the bot, back to private, pull your checkout.

To the thread: please don't relay this one again or ship it from elsewhere. Just point Hamid to reply here.
```

The owner's reply, received directly:

```text
Ship it
```
