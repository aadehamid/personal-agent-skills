# Calibrate mode

The full STE spec is too strict, and the best subset differs by person. This mode finds the rules that would have helped this user, based on real sessions. It then saves them so that later runs use them.

## Steps

1. **Sample sessions.** Run the bundled script from this skill folder:

   ```bash
   python3 scripts/sample_transcripts.py --days 7 --n 10
   ```

   If the user named a different window or count, use theirs. If fewer than five sessions come back, raise `--days` to 30 and tell the user how many you found. Do not include the current session.

2. **Read the replies as the user.** For each sampled Claude reply, look for the places where the user would have slowed down, misread, or had to ask a follow-up. The user's next message is the best evidence. Look for "what do you mean", repeated questions, corrections, or the user restating something Claude buried.

3. **Test each rule.** For each STE core rule (1 to 12 in SKILL.md) and each AI-tell group, decide:
   - **Helps:** applying it would have fixed real confusion you found. Quote the passage and give the rewrite.
   - **Neutral:** Claude already follows it, or it rarely applies.
   - **Hurts:** applying it would have made a good reply worse, for example by making nuanced reasoning stilted.

   Also look for problems that no rule covers. Write those as new candidate rules.

4. **Write `calibration.md`** in this skill folder (the same folder as SKILL.md), using the template below. If the file exists, merge the new findings into it. Keep the rules that earlier calibrations found, unless the new evidence contradicts them.

5. **Report to the user.** Show the top three rules with one before/after each. Say how many sessions you read. Ask if they also want a three-to-five-line summary added to `~/.claude/CLAUDE.md`, so the rules apply even when this skill does not trigger. Do not edit CLAUDE.md without a yes.

## Template for calibration.md

```markdown
# Personal calibration

Last run: YYYY-MM-DD. Sessions read: N (last D days).

## Emphasize
- Rule N (name): why, with a short quoted example from a session.

## Relax
- Rule N (name): why it hurt or did not apply for this user.

## Added rules
- New rule: description, plus the evidence.

## Register notes
- Anything about what this user mostly reads (for example, "mostly debugging reports; wants the answer in line one").
```

Keep the file under 60 lines. It is read on every run of the skill, so every line must earn its place.
