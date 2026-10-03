# STE core: examples and exclusions

ASD-STE100 (Simplified Technical English) is the controlled language for aerospace maintenance documentation. The full spec has about 60 writing rules and a dictionary of about 900 approved words. This file shows the subset this skill uses, with examples, and explains which parts it leaves out.

## Contents

- Rule examples (1 to 12)
- Rules left out, and why

## Rule examples

### 1. One idea per sentence

Before: "The cache is invalidated on deploy, which means the first requests after a release are slower, and this is why we see latency spikes at 2 p.m. on Tuesdays."

After: "Each deploy clears the cache. The first requests after a release are slower. We deploy at 2 p.m. on Tuesdays, so latency spikes then."

### 2. Active voice, name the actor

Before: "The request is rejected if the token is expired."

After: "If the token is expired, the gateway rejects the request."

Passive is acceptable when the actor is unknown or irrelevant: "The bridge was built in 1932."

### 3. One term for one thing

Before: "The worker pulls jobs from the queue. When the consumer fails, the processor restarts it."

(Is the consumer the worker? Is the processor something else?)

After: "The worker pulls jobs from the queue. When the worker fails, the supervisor restarts it."

### 4. One topic per paragraph, topic sentence first

Before: "We looked at three vendors. Vendor A had the best API but no SSO. Vendor B was cheapest. In the end we recommend Vendor C because it is the only one with SSO and an acceptable price."

After: "We recommend Vendor C. It is the only vendor with SSO at an acceptable price. Vendor A has a better API but no SSO. Vendor B is cheaper but also has no SSO."

### 5. Verbs for actions, not nouns

| Noun form | Verb form |
|---|---|
| perform an analysis of | analyze |
| make a decision | decide |
| carry out the installation of | install |
| provide an explanation | explain |
| is in need of | needs |

### 6. Simple tenses

Before: "The job would have been being retried if the flag had been set."

After: "If the flag was set, the job retried. It was not set."

### 7. Do not drop small words

Before (telegraphic): "Root cause: race in init. Fix: lock before read. Verified locally, CI pending."

After (explanation register): "The root cause is a race condition during startup. Two threads read the config before it finishes loading. The fix adds a lock before the read. I tested it locally. CI is still running."

Telegraphic style is fine in commit messages, changelogs, and tables.

### 8. Three nouns maximum in a stack

Before: "user session token refresh failure handler"

After: "the handler for failures when the user's session token refreshes"

In code identifiers and product names, stacks are fine. The rule applies to prose.

### 9. Condition before action

Before: "Restart the service if memory exceeds 2 GB."

After: "If memory exceeds 2 GB, restart the service."

### 10. One action per step, imperative, numbered

Before: "You'll want to clone the repo and then install deps, after which the tests can be run."

After:
1. Clone the repository.
2. Install the dependencies: `npm install`.
3. Run the tests: `npm test`.

### 11. Warnings first, with the consequence

Before: "3. Run `migrate --reset`. Note that this will delete all data."

After: "3. Warning: the next command deletes all data in the database. Back it up first. Then run `migrate --reset`."

### 12. Specific over vague

| Vague | Specific |
|---|---|
| addressed the issue | removed the duplicate cron entry |
| significantly faster | 4.1 s to 0.9 s |
| some users | 3% of users on Android 12 |
| in the near future | in the 1.4 release (planned for Nov 12) |

## Rules left out, and why

Testing showed that the full spec hurts knowledge work. It makes nuanced explanations stilted and forces long workarounds. This skill leaves out these parts of STE:

- **The approved dictionary.** STE limits writers to about 900 words, each with one meaning. That is too narrow for technical discussion outside maintenance. Keep the spirit: prefer the common word and use each word in one sense.
- **The full ban on -ing forms.** STE bans most -ing words. This skill bans only the vague trailing -ing clause (", highlighting the need for..."), because that is the common AI tell. "The running process" is fine.
- **Hard word limits.** STE caps instruction sentences at 20 words and descriptive sentences at 25. Here these are warning thresholds. A 28-word sentence that reads cleanly can stay.
- **The ban on phrasal verbs.** "Set up", "roll back", and "log in" are the normal terms in software. Keep them.
- **Mandatory vertical lists for all sequences.** Short sequences of two items read better in a sentence.
