// Project memory schema. Every statement is idempotent.
// Only current facts carry the CurrentFact label, so full-text recall never
// spends its result limit on superseded facts.
CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.key IS UNIQUE;
CREATE CONSTRAINT episode_id IF NOT EXISTS FOR (ep:Episode) REQUIRE ep.id IS UNIQUE;
CREATE CONSTRAINT fact_id IF NOT EXISTS FOR (f:Fact) REQUIRE f.id IS UNIQUE;
CREATE INDEX fact_slot IF NOT EXISTS FOR (f:Fact) ON (f.slot);
CREATE FULLTEXT INDEX current_fact_text IF NOT EXISTS FOR (f:CurrentFact) ON EACH [f.text];
