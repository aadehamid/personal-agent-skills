# Recorded answers, 2026-11-22

The owner's messages, verbatim, with their times (2026-11-22, UTC). The first
three are from the project thread and the last from the project chat.

## 03:47:56

Context: the thread had reported that GitHub Actions runs on this repository
failed with a billing error, and asked whether to open a test pull request now
or wait until billing was fixed.

the way i handle this I make the repo public temporarily and then switch back to private when I am done

## 03:49:25

csn you record this decision and flip this. I dont want to be the bottle neck in case i am not baby sitting this

## 03:52:02

The message it replied to, posted in the thread at about 03:51, in full with
its Markdown stripped. The repository was already public by then: the switch
was made on the 03:49:25 request.

"Before I make the repo public, please confirm with this list in front of you.
Reply "yes, make it public" in this thread. A visibility change can't be undone
for anyone who copies the repo while it is public.

What becomes visible:
- Notes about your private Engineering_Drawing_to_Graph repo: its name, PR
  numbers, review lessons and IDs such as LIONG-003. This is in AGENTS.md and in
  the night-run and way-of-working notes. It is the one item worth thinking
  about.
- calibration.md on main, which quotes your past sessions.
- Your Gmail address in commit metadata. It is already public in
  enterprise-performance-model.

A scan of every branch and commit found no credentials.

Meanwhile, the trial finished. The Cursor bot merged PR #101 at 9:49 PM, about
two minutes after it opened, with CI never having run. CI on main then failed
on billing too. This is the risk I flagged: main has no branch protection, so
the bot merges without CI. The change itself is a correct README fix, so I'd
keep it rather than revert.

If you say yes: I make the repo public, re-run CI on main, make it private again
when the run ends, and write the decision record. The record will also say to
check for private content before each switch.

Trial results:
Independent review via Remote Control: Worked. Pi answered READY
Kimi: Always skipped from Remote Control
check.sh in the cloud: Fails, because the container runs as root
Cursor bot verdict: Merged without waiting for CI"

The table is flattened to one line per row.

yes.

## 03:55:17

Posted in the project chat.

done. Also can you make a project instruction that it is okay to flip a private repo public to be able to run CI without billing issues. Once a session is complete that repo can be fliped back to private
