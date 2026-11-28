// Write one episode, the entities it mentions, and the facts taken from it,
// in one transaction: a failing statement rolls back the whole episode.
// Parameter $m: {episode: {id, session, agent, kind, at, text},
//                mentions: [{key, name}], facts: [{id, text, slot, about: [key], validFrom}],
//                fingerprint}
// scripts/memory.sh adds the fingerprint, a hash of the whole episode.
// recordedAt is the write time, so the latest write to a slot is its current
// fact whatever order the episodes' `at` times arrive in.
.begin
// Guards. They run under the writer lock, so no other writer can slip in
// between check and write. A guard that matches divides by zero, which fails
// the statement and rolls back the transaction.
OPTIONAL MATCH (old:Episode {id: $m.episode.id})
WITH old WHERE old IS NOT NULL AND (old.fingerprint IS NULL OR old.fingerprint <> $m.fingerprint)
RETURN 1 / 0 AS episode_id_already_used_for_different_content;

UNWIND $m.facts AS f
MATCH (x:Fact {id: f.id})
WHERE NOT EXISTS { (x)-[:FROM]->(:Episode {id: $m.episode.id}) }
RETURN 1 / 0 AS fact_id_belongs_to_another_episode;

MERGE (ep:Episode {id: $m.episode.id})
  ON CREATE SET ep.session = $m.episode.session, ep.agent = $m.episode.agent,
                ep.kind = $m.episode.kind, ep.at = datetime($m.episode.at),
                ep.text = $m.episode.text, ep.fingerprint = $m.fingerprint
WITH ep
UNWIND $m.mentions AS m
MERGE (e:Entity {key: m.key}) ON CREATE SET e.name = m.name
MERGE (ep)-[:MENTIONS]->(e);

UNWIND $m.facts AS f
MATCH (ep:Episode {id: $m.episode.id})
MERGE (x:Fact {id: f.id})
  ON CREATE SET x:CurrentFact, x.text = f.text, x.slot = f.slot,
                x.validFrom = datetime(coalesce(f.validFrom, $m.episode.at)),
                x.recordedAt = datetime()
MERGE (x)-[:FROM]->(ep)
WITH x, f
UNWIND f.about AS key
MERGE (e:Entity {key: key}) ON CREATE SET e.name = key
MERGE (x)-[:ABOUT]->(e);

// Supersession: a new current fact closes every other current fact in its
// slot. A replayed episode finds its facts already closed, or current with no
// other current fact beside them, so it changes nothing.
UNWIND $m.facts AS f
MATCH (new:Fact {id: f.id}) WHERE new.closedAt IS NULL
MATCH (old:Fact {slot: new.slot})
WHERE old <> new AND old.closedAt IS NULL
// A correction can say it became true before the old fact did. Then the old
// fact held for no time at all, so its range ends where it starts.
SET old.validTo = CASE WHEN new.validFrom < old.validFrom THEN old.validFrom ELSE new.validFrom END,
    old.closedAt = new.recordedAt
REMOVE old:CurrentFact
MERGE (new)-[:SUPERSEDES]->(old)
RETURN new.slot AS slot, new.text AS current, old.text AS replaced;
.commit
