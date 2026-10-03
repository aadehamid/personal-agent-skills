# AI tells: full pattern list

These are the patterns that make text read as machine-written, with a fix for each. The ideas come from two versions of the unslop skill: the one in the Anthropic skills directory (rules 1 to 31) and the Cursor fork in cursor/plugins (rules 32 and 33, and the strict dash rule). The wording and examples here are our own. See `SOURCES.md` for links.

The numbers match unslop's numbering, so a note that cites "unslop rule 13" still applies here. Do not renumber. If a rule is removed, leave a gap.

How to use the list: scan the text for each group, fix what you find, then read the result once from start to finish. Rules 27 to 31 overlap with the STE core in SKILL.md, so apply them together.

## Content

1. **Inflated significance.** Phrases that make an event sound historic: "a watershed moment", "marks a turning point", "leaves a lasting legacy", "paves the way for". Say what happened and stop.
2. **Lists of outlets or names with no content.** "Covered by Reuters, Bloomberg, and the FT" tells the reader nothing. Pick one source and report what it said.
3. **Trailing -ing clauses that add a vague claim.** "The team migrated the historian, underscoring its commitment to reliability." Delete the clause, or replace it with a fact that has a source.
4. **Brochure words.** "world-class", "state-of-the-art", "breathtaking", "nestled", "iconic". Describe the thing in neutral terms, or give a number.
5. **Unnamed authorities.** "Many experts agree", "studies show", "critics have noted". Name who said it, or cut the sentence.
6. **The struggle-then-triumph template.** "Despite numerous obstacles, the project continues to flourish." Replace it with what the obstacles were and what the result was.

## Language

7. **Words that models overuse.** delve, crucial, pivotal, intricate, tapestry, testament, underscore, showcase, foster, garner, enhance, interplay, landscape (used abstractly), vibrant, additionally. Use the plain word, or cut it.
8. **Dressed-up "is" and "has".** "acts as", "serves as", "stands as", "boasts", "features". Write "is" or "has".
9. **"Not only X, but also Y" and "It's not X, it's Y".** This framing sets up a contrast nobody asked for. State Y directly.
10. **Automatic groups of three.** "fast, reliable, and scalable" when only one of these is true and relevant. Use as many items as the facts support.
11. **Rotating synonyms.** "the collector", then "the service", then "the agent", then "the ingestion layer", all for one thing. Choose one name and repeat it. (STE rule 3 says the same.)
12. **Ranges that are not ranges.** "from field sensors to boardroom dashboards" when no scale connects the two ends. List the actual items.

## Style

13. **Em dashes and en dashes.** Do not use them as punctuation, and do not fake them with a spaced hyphen. Use a period or a comma. When two thoughts need to be kept apart, make them two sentences. Keep parentheses for real asides such as units, abbreviations, or a short example, and use at most one per paragraph.
14. **Colons as connectors.** A colon before a list or an example is fine. A colon that joins two halves of a thought is a crutch. "Here's the thing: the RTU only stores 60 minutes" becomes "The RTU stores only 60 minutes of data."
15. **Too much bold.** Bold only what the reader must not miss, such as a warning. Do not bold every product name or acronym.
16. **Bold labels that repeat the line.** "**Latency:** Latency dropped by half." The label adds nothing, so write the sentence. A bold lead-in is fine when it ends with a period, names the item, and the text after it adds new information.
17. **Title Case Headings.** Use sentence case: "How the collector works", not "How The Collector Works".
18. **Decorative emoji.** Remove emoji from headings, bullets, and status lines.
19. **Curly quotes.** Use straight quotes (" and ').

## Chat habits

20. **Assistant filler.** "Happy to help!", "Hope this helps!", "Let me know if you need anything else", "Absolutely!" Cut it. End on the last useful sentence.
21. **Knowledge-cutoff hedges.** "As of my last update..." or "Detailed information is limited..." Find the information, or say plainly what you do not know.
22. **Flattery.** "Great question!", "You're absolutely right!" Answer the question.

## Filler

23. **Padding phrases.** Write "to" for "in order to" and "because" for "owing to the fact that". "It is worth noting that" and "It's important to remember that" get deleted.
24. **Stacked hedges.** "It could perhaps be argued that this might potentially help" becomes "This may help."
25. **Empty endings.** "Exciting times ahead!" or "The possibilities are endless." End with the next step, the open question, or the last fact.

## Jargon

26. **Metaphor nouns that pose as technical terms.** Examples: substrate, vector (for "way"), nexus, locus, primitive (as a noun), surface (as in "API surface"), scaffolding, bedrock, paradigm, modality, north star, flywheel, endgame, gold-plating, wedge. Each usually has a plain word: "base" for substrate, "way" or "method" for vector, "add" for "wedge in", "the last phase" for endgame, "more than the job needs" for gold-plating. Use the plain word.

## Plain speech

27. **Name the mechanism, not the feeling.** "Data flows effortlessly to the cloud" names a feeling. "Each site publishes a reading only when the value changes" names the mechanism. Ask what the reader should know or do, and write that. A useful test: would this sentence fit, word for word, in the README of an unrelated product? If so, it carries no information about yours, so remove it.
28. **Dense sentences.** If the reader must read a sentence twice, split it or drop a clause. One idea per sentence.
29. **Passive voice that hides the actor.** "The buffer is cleared" becomes "The collector clears the buffer" or "Delete the buffer files". Keep the passive only when nobody knows, or nobody cares, who did it.
30. **Adverbs that prop up weak verbs.** "significantly reduced" becomes the number: "cut from 40 s to 6 s". "quickly processes" becomes "processes in 2 ms" or "is fast". If the verb needs an adverb, find a better verb.
31. **Fancy words with plain equivalents.** Write "use" for utilize or leverage, "help" for facilitate, "start" for commence, "many" for numerous, and "if" for "in the event that".

## Style, continued

32. **Mannered prose.** Figures of speech where a literal phrase exists. This covers slogans ("ship it or kill it"), fragments for drama ("Simple. Fast. Done."), code described as a person ("the scheduler wants to retry"), and figurative verbs ("the config rides along with the build"). Write the literal version: "the build includes the config". Metaphor nouns are handled separately, in rule 26.
33. **Over-compression.** Notes that make the reader decode them: dropped articles, verbless fragments, arrows, and private abbreviations. "RTU buf full → drop oldest, no alert" becomes "When the RTU buffer is full, it drops the oldest readings and does not raise an alert." Write full sentences and spell out symbols. (STE rule 7 says the same.)
