#!/usr/bin/env bash
# Shared project memory for every agent, stored in a Relate graph.
# Model and rules: .agents/skills/project-memory/SKILL.md.
# Installed by the relate-project-memory skill, which replaces this file on
# every update. Change the skill's template, not this copy.
#
# Usage:
#   scripts/memory.sh remember FILE|-   write one episode (JSON) and its facts
#   scripts/memory.sh recall WORDS...   the 10 current facts that best match the words
#   scripts/memory.sh about KEY         current facts about one entity (first 100)
#   scripts/memory.sh history SLOT      facts a slot has held, newest first (first 100)
#   scripts/memory.sh slots             slots that hold a current fact (first 500)
#   scripts/memory.sh asof WHEN         what agents believed at WHEN (first 100); WHEN is a
#                                       date (the end of that UTC day) or a datetime with a zone
#   scripts/memory.sh brief [N]         the N most recent current facts (default 20)
#   scripts/memory.sh check             fail unless every slot holds exactly one current fact
#   scripts/memory.sh init              create the store and its schema
#   scripts/memory.sh path              print the store path
#
# The store is a Relate directory store in the git-ignored .relate-memory/
# folder at the root of the main checkout, so every worktree and every agent
# shares one memory and Git never tracks it. A sandboxed agent that cannot
# write inside .git can still save there when the main checkout is in its
# workspace. A repository whose git directory is not named .git keeps the
# store at <git dir>/relate-memory. PROJECT_MEMORY_DB overrides the path.
# Output is JSON lines.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cypher_dir="$here/memory"
tmp=""
build_dir=""
cleanup() {
  [ -z "$tmp" ] || rm -f "$tmp"
  [ -z "$build_dir" ] || rm -rf "$build_dir"
}
# Clean up on a normal exit and on the signals that usually stop a script.
# SIGKILL and a power loss skip the cleanup, and other ways a script ends may
# skip it too. init removes a build left that way once it is an hour old.
trap cleanup EXIT
trap 'cleanup; trap - EXIT; exit 130' INT
trap 'cleanup; trap - EXIT; exit 143' TERM
trap 'cleanup; trap - EXIT; exit 129' HUP

store() {
  if [ -n "${PROJECT_MEMORY_DB:-}" ]; then
    local db="$PROJECT_MEMORY_DB"
    while [ "${#db}" -gt 1 ] && [ "${db%/}" != "$db" ]; do db="${db%/}"; done
    printf '%s\n' "$db"
    return
  fi
  # Git exports GIT_DIR and friends inside hooks and rebases. Clear them so the
  # path always comes from this script's own repository.
  local common
  common="$(env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR -u GIT_INDEX_FILE \
    -u GIT_OBJECT_DIRECTORY -u GIT_ALTERNATE_OBJECT_DIRECTORIES \
    git -C "$here" rev-parse --path-format=absolute --git-common-dir)"
  if [ "$(basename "$common")" = ".git" ]; then
    printf '%s/.relate-memory\n' "$(dirname "$common")"
  else
    printf '%s/relate-memory\n' "$common"
  fi
}

# Dropbox syncs the store between machines, but Relate's writer lock holds
# only on one machine. Two machines saving at once make Dropbox write
# "conflicted copy" files. Stop on them: a person must decide which copy wins.
dropbox_conflicts() {
  local db
  db="$(store)"
  [ -d "$db" ] || return 0
  # -H follows a store path that is itself a symlink.
  find -H "$db" -name '*conflicted copy*' -print
}

refuse_on_conflicts() {
  local found
  found="$(dropbox_conflicts)"
  [ -z "$found" ] && return 0
  echo "memory: Dropbox conflicted copies in the store; another machine saved at the same time." >&2
  echo "memory: ask the owner to resolve them before anyone saves again:" >&2
  sed -n '1,20p' <<< "$found" >&2
  exit 4
}

need_relate() {
  command -v relate >/dev/null 2>&1 && return 0
  echo "memory: relate is not installed. Install it with: curl -sSfL https://relatedb.ai/install.sh | bash" >&2
  exit 3
}

# --param parses its value as JSON, so a bare `true` or `42` would bind as a
# boolean or a number. Encode every string parameter as a JSON string.
json_string() {
  python3 -c 'import json, sys; print(json.dumps(sys.argv[1]))' "$1"
}

# Writes take the store's writer lock. Another agent may hold it for a moment,
# so retry a locked store (exit 5) for up to 10 seconds. The script file is
# reopened on every attempt.
write() {
  local script="$1" db attempt=1 status
  shift
  db="$(store)"
  while :; do
    set +e
    relate query --database "$db" --mode jsonl --max-rows 0 "$@" < "$script"
    status=$?
    set -e
    if [ "$status" -ne 5 ] || [ "$attempt" -ge 20 ]; then
      return "$status"
    fi
    attempt=$((attempt + 1))
    sleep 0.5
  done
}

read_query() {
  local db
  db="$(store)"
  if [ ! -d "$db" ]; then
    echo "memory: no memory yet at $db. Run: scripts/memory.sh init" >&2
    exit 0
  fi
  if [ -n "$(dropbox_conflicts)" ]; then
    echo "memory: warning: Dropbox conflicted copies in the store; results may be stale. Run: scripts/memory.sh check" >&2
  fi
  # --max-rows 0: relate caps rows at 100 under an agent harness and adds a
  # rowCap line; this script sets its own caps and says when it reaches one.
  relate query --database "$db" --read-only --mode jsonl --max-rows 0 "$@"
}

# Run a read with a row cap. Fetch one row more than the cap, so a result that
# was cut can say so instead of passing for the whole set.
capped() {
  local cap="$1" out count
  shift
  out="$(read_query --param "cap=$((cap + 1))" "$@")"
  count="$(grep -c '^{' <<< "$out" || true)"
  if [ "$count" -gt "$cap" ]; then
    sed -n "1,${cap}p" <<< "$out"
    echo "memory: showing the first $cap rows; more exist" >&2
  elif [ -n "$out" ]; then
    printf '%s\n' "$out"
  fi
}

# The schema is idempotent, so every write runs it first. Its notes are noise
# on success, so show them only when it fails.
# Two relate processes creating one store at once leave it broken. So each
# first writer builds a private store and renames it into place. A rename onto
# a folder that already holds a store fails atomically, and the loser drops
# its copy and uses the winner's. No lock is held, so none can go stale.
# A SIGKILL, an untrapped signal or a crash can leave a private build beside
# the store. It is never used. Remove builds older than an hour on every init.
sweep_builds() {
  local db="$1" parent pattern
  parent="$(dirname "$db")"
  [ -d "$parent" ] || return 0
  # Escape glob characters in the store name so find matches it literally.
  pattern="$(basename "$db" | sed 's/[][*?\\]/\\&/g').init.*"
  find -H "$parent" -mindepth 1 -maxdepth 1 -type d -name "$pattern" -mmin +60 \
    -exec rm -rf {} + 2>/dev/null || true
}

create_store() {
  local db="$1" parent
  parent="$(dirname "$db")"
  mkdir -p "$parent"
  if [ ! -w "$parent" ]; then
    echo "memory: cannot create the store; $parent is not writable" >&2
    return 1
  fi
  build_dir="$db.init.$$.$RANDOM"
  if ! relate query --database "$build_dir" --mode jsonl < "$cypher_dir/schema.cypher" > /dev/null 2>&1; then
    echo "memory: could not create the store at $db" >&2
    return 1
  fi
  python3 -c 'import os, sys
try:
    os.rename(sys.argv[1], sys.argv[2])
except OSError:
    pass' "$build_dir" "$db"
  rm -rf "$build_dir"
  build_dir=""
  if [ ! -d "$db" ]; then
    echo "memory: could not create the store at $db" >&2
    return 1
  fi
}

init() {
  need_relate
  refuse_on_conflicts
  local out db
  db="$(store)"
  sweep_builds "$db"
  [ -d "$db" ] || create_store "$db"
  if ! out="$(write "$cypher_dir/schema.cypher" 2>&1)"; then
    printf '%s\n' "$out" >&2
    return 1
  fi
  echo "memory: store ready at $db"
}

validate() {
  python3 - "$1" <<'PY'
import hashlib, json, re, sys
from datetime import datetime, timedelta, timezone
if sys.version_info < (3, 11):
    sys.exit("memory: needs python3 3.11 or later; this one is " + sys.version.split()[0])
path = sys.argv[1]
def reject_constant(c):
    raise ValueError(f"{c} is not valid JSON")
def finite_float(text):
    value = float(text)
    if value in (float("inf"), float("-inf")):
        raise ValueError(f"{text} is too large for a JSON number")
    return value
try:
    with open(path, encoding="utf-8") as fh:
        m = json.load(fh, parse_constant=reject_constant, parse_float=finite_float)
    json.dumps(m, ensure_ascii=False).encode("utf-8")
except (OSError, ValueError) as exc:
    sys.exit(f"memory: {path} is not readable JSON: {exc}")
KINDS = {"decision", "preference", "correction", "finding", "handoff", "tool_call"}
TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,9})?)?(Z|[+-]\d{2}:\d{2})", re.ASCII)
errors = []
SLOT = re.compile(r"[a-z0-9][a-z0-9._:-]*(/[a-z0-9][a-z0-9._:-]*)+", re.ASCII)
KEY = re.compile(r"[a-z0-9][a-z0-9._:/-]*", re.ASCII)

def entity_key(value, where):
    if not isinstance(value, str) or not KEY.fullmatch(value):
        errors.append(f"{where}: lowercase entity key such as owner or file:scripts/check.sh")

def text(obj, key, where):
    value = obj.get(key) if isinstance(obj, dict) else None
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where}.{key}: missing string")
        return None
    return value

def time(obj, key, where, required=True):
    if not required and obj.get(key) is None:
        return
    value = text(obj, key, where)
    if value is None:
        return
    try:
        parsed = datetime.fromisoformat(value) if TIME.fullmatch(value) else None
        # Relate accepts zone offsets up to 18 hours either way.
        valid = (parsed is not None and parsed.utcoffset() is not None
                 and abs(parsed.utcoffset()) <= timedelta(hours=18))
    except ValueError:
        valid = False
    if not valid:
        errors.append(f"{where}.{key}: not a UTC or offset datetime such as 2026-11-27T10:00:00Z")
        return None
    return parsed

if not isinstance(m, dict):
    sys.exit("memory: invalid episode:\n  top level: not an object")
ep = m.get("episode")
learned = None
if not isinstance(ep, dict):
    errors.append("episode: missing object")
else:
    for key in ("id", "session", "agent", "text"):
        text(ep, key, "episode")
    learned = time(ep, "at", "episode")
    # Memory records what agents have learned, so at is not in the future,
    # beyond five minutes allowed for clock skew between machines, and nothing
    # becomes true after it was learned. Save a plan as a current fact ("The
    # move is planned for 1 March").
    if learned and learned > datetime.now(timezone.utc) + timedelta(minutes=5):
        errors.append("episode.at: in the future; use the time you learned it")
    if not (isinstance(ep.get("kind"), str) and ep["kind"] in KINDS):
        errors.append(f"episode.kind: one of {', '.join(sorted(KINDS))}")
mentions = m.setdefault("mentions", [])
if not isinstance(mentions, list):
    errors.append("mentions: not a list")
    mentions = []
for i, e in enumerate(mentions):
    if not isinstance(e, dict):
        errors.append(f"mentions[{i}]: not an object")
        continue
    entity_key(e.get("key"), f"mentions[{i}].key")
    text(e, "name", f"mentions[{i}]")
facts = m.get("facts")
if not isinstance(facts, list) or not facts:
    errors.append("facts: needs at least one fact")
    facts = []
ids, slots = set(), set()
for i, f in enumerate(facts):
    where = f"facts[{i}]"
    if not isinstance(f, dict):
        errors.append(f"{where}: not an object")
        continue
    fid = text(f, "id", where)
    text(f, "text", where)
    slot = text(f, "slot", where)
    if slot is not None and not SLOT.fullmatch(slot):
        errors.append(f"{where}.slot: lowercase <entity>/<aspect>, such as memory/setup")
    starts = time(f, "validFrom", where, required=False)
    if starts and learned and starts > learned:
        errors.append(f"{where}.validFrom: after episode.at; save a plan as a current fact instead")
    about = f.get("about")
    if not (isinstance(about, list) and about):
        errors.append(f"{where}.about: needs a non-empty list of entity keys")
    else:
        for j, k in enumerate(about):
            entity_key(k, f"{where}.about[{j}]")
    if fid in ids:
        errors.append(f"{where}.id: repeats an earlier fact id")
    if slot in slots:
        errors.append(f"{where}.slot: repeats an earlier slot; one episode holds one fact per slot")
    ids.add(fid)
    slots.add(slot)
if errors:
    sys.exit("memory: invalid episode:\n  " + "\n  ".join(errors))
m.pop("fingerprint", None)
canonical = json.dumps(m, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
m["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
with open(path, "w", encoding="utf-8") as fh:
    json.dump(m, fh, allow_nan=False)
PY
}

# An episode id names one episode, and a fact id belongs to one episode.
# This read gives a clear message; remember.cypher repeats both checks under
# the writer lock, where no other writer can race them.
check_ids() {
  local db clash
  db="$(store)"
  [ -d "$db" ] || return 0
  clash="$(read_query --fetch-params "m=$1" \
    'OPTIONAL MATCH (old:Episode {id: $m.episode.id})
     WITH old WHERE old IS NOT NULL AND (old.fingerprint IS NULL OR old.fingerprint <> $m.fingerprint)
     RETURN "episode id already used for different content" AS problem, old.id AS id
     UNION ALL
     UNWIND $m.facts AS f
     MATCH (x:Fact {id: f.id})
     WHERE NOT EXISTS { (x)-[:FROM]->(:Episode {id: $m.episode.id}) }
     OPTIONAL MATCH (x)-[:FROM]->(other:Episode)
     RETURN "fact id belongs to episode " + coalesce(other.id, "(none)") AS problem, x.id AS id')"
  if [ -n "$clash" ]; then
    echo "memory: invalid episode: ids already in use:" >&2
    printf '%s\n' "$clash" >&2
    exit 1
  fi
}

remember() {
  local src="${1:-}"
  [ -n "$src" ] || { echo "usage: scripts/memory.sh remember FILE|-" >&2; exit 2; }
  tmp="$(mktemp "${TMPDIR:-/tmp}/project-memory.XXXXXX")"
  if [ "$src" = "-" ]; then cat > "$tmp"; else cat -- "$src" > "$tmp"; fi
  validate "$tmp"
  need_relate
  refuse_on_conflicts
  init > /dev/null
  check_ids "$tmp"
  write "$cypher_dir/remember.cypher" --fetch-params "m=$tmp"
  python3 -c 'import json, sys; m = json.load(open(sys.argv[1])); print("memory: saved episode %s with %d fact(s)" % (m["episode"]["id"], len(m["facts"])))' "$tmp"
}

no_args() {
  [ "$#" -eq 0 ] || { echo "usage: scripts/memory.sh $cmd takes no arguments" >&2; exit 2; }
}

cmd="${1:-}"
[ $# -gt 0 ] && shift
case "$cmd" in
  init) no_args "$@"; init ;;
  path) no_args "$@"; store ;;
  remember)
    [ "$#" -le 1 ] || { echo "usage: scripts/memory.sh remember FILE|-" >&2; exit 2; }
    remember "$@" ;;
  recall)
    need_relate
    [[ "${*:-}" =~ [^[:space:]] ]] || { echo "usage: scripts/memory.sh recall WORDS..." >&2; exit 2; }
    q="$(json_string "$*")"
    read_query --param "q=$q" \
      'MATCH (f:CurrentFact) SEARCH f IN (FULLTEXT INDEX current_fact_text FOR $q LIMIT 10) SCORE AS score
       MATCH (f)-[:FROM]->(ep:Episode)
       RETURN f.slot AS slot, f.text AS memory, round(score, 3) AS score,
              ep.agent AS agent, ep.id AS episode, toString(ep.at) AS learned, ep.text AS evidence
       ORDER BY score DESC' ;;
  about)
    need_relate
    [ "$#" -eq 1 ] && [ -n "$1" ] || { echo "usage: scripts/memory.sh about KEY" >&2; exit 2; }
    key="$(json_string "$1")"
    capped 100 --param "key=$key" \
      'MATCH (e:Entity {key: $key})<-[:ABOUT]-(f:CurrentFact)-[:FROM]->(ep:Episode)
       RETURN f.slot AS slot, f.text AS memory, ep.agent AS agent, ep.id AS episode,
              toString(ep.at) AS learned, ep.text AS evidence
       ORDER BY slot LIMIT $cap' ;;
  history)
    need_relate
    [ "$#" -eq 1 ] && [ -n "$1" ] || { echo "usage: scripts/memory.sh history SLOT" >&2; exit 2; }
    slot="$(json_string "$1")"
    capped 100 --param "slot=$slot" \
      'MATCH (f:Fact {slot: $slot})-[:FROM]->(ep:Episode)
       RETURN f.text AS memory, toString(f.validFrom) AS validFrom, toString(f.validTo) AS validTo,
              toString(f.recordedAt) AS recorded, toString(f.closedAt) AS closed,
              ep.agent AS agent, ep.id AS episode, ep.text AS evidence
       ORDER BY f.recordedAt DESC LIMIT $cap' ;;
  asof)
    need_relate
    usage="usage: scripts/memory.sh asof WHEN, a date such as 2026-11-27 (the end of that UTC day) or a datetime such as 2026-11-27T10:00:00Z"
    [ "$#" -eq 1 ] || { echo "$usage" >&2; exit 2; }
    when="$1"
    if [[ "$when" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
      kind=date
    elif [[ "$when" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]{1,9})?)?(Z|[+-][0-9]{2}:[0-9]{2})$ ]]; then
      kind=datetime
    else
      echo "$usage" >&2; exit 2
    fi
    # The shape check above allows only digits, T, Z, +, -, colons and a dot,
    # so plain quotes make a valid JSON string without the Python helper.
    w="\"$when\""
    # Relate parses it, so its own rules decide: real calendar dates, offsets
    # within 18 hours.
    relate query --database :memory: --mode jsonl --param "w=$w" "RETURN $kind(\$w) AS w" > /dev/null 2>&1 \
      || { echo "$usage" >&2; exit 2; }
    # A date means the last moment of that UTC day, compared as a moment, so a
    # fact stamped in another zone falls on the right side of midnight.
    [ "$kind" = date ] && w="\"${when}T23:59:59.999999999Z\""
    # "Believed on t", as the relate cookbook's bitemporal-decisions recipe
    # defines it: recorded by t, valid on t, and an end of validity counts
    # only once it was known (closedAt), so a fact closed after t still looked
    # open on t, and a change recorded ahead of its validFrom is not yet in
    # force. A slot holds one value at a time, so when the rule leaves two
    # candidates, the one recorded later is what agents believed.
    capped 100 --param "w=$w" \
      'MATCH (f:Fact)-[:FROM]->(ep:Episode)
       WHERE f.recordedAt <= datetime($w) AND f.validFrom <= datetime($w)
         AND (f.validTo IS NULL OR f.validTo > datetime($w) OR f.closedAt > datetime($w))
       WITH f, ep ORDER BY f.recordedAt DESC
       WITH f.slot AS slot, collect({f: f, ep: ep})[0] AS top
       WITH top.f AS f, top.ep AS ep
       RETURN f.slot AS slot, f.text AS memory, ep.agent AS agent, ep.id AS episode,
              toString(f.recordedAt) AS recorded, ep.text AS evidence
       ORDER BY slot LIMIT $cap' ;;
  slots)
    no_args "$@"
    need_relate
    capped 500 'MATCH (f:CurrentFact) RETURN DISTINCT f.slot AS slot ORDER BY slot LIMIT $cap' ;;
  brief)
    need_relate
    [ "$#" -le 1 ] || { echo "usage: scripts/memory.sh brief [N], N from 1 to 9999" >&2; exit 2; }
    n="${1-20}"
    [[ "$n" =~ ^[1-9][0-9]{0,3}$ ]] || { echo "usage: scripts/memory.sh brief [N], N from 1 to 9999" >&2; exit 2; }
    read_query --param "n=$n" \
      'MATCH (f:CurrentFact)-[:FROM]->(ep:Episode)
       RETURN f.slot AS slot, f.text AS memory, ep.agent AS agent, ep.id AS episode,
              toString(ep.at) AS learned, ep.text AS evidence
       ORDER BY f.recordedAt DESC LIMIT $n' ;;
  check)
    no_args "$@"
    need_relate
    refuse_on_conflicts
    db="$(store)"
    if [ ! -d "$db" ]; then
      echo "memory: no memory yet at $db. Run: scripts/memory.sh init" >&2
      exit 0
    fi
    out="$(read_query \
      'MATCH (f) WHERE f:Fact OR f:CurrentFact
       WITH f, COUNT { (f)-[:FROM]->(:Episode) } AS sources
       WITH coalesce(f.slot, "(no slot)") AS slot,
            sum(CASE WHEN f:Fact AND f.closedAt IS NULL THEN 1 ELSE 0 END) AS current,
            sum(CASE WHEN NOT f:Fact OR f.slot IS NULL
                       OR (f.closedAt IS NULL) <> (f:CurrentFact) THEN 1 ELSE 0 END) AS mislabelled,
            sum(CASE WHEN sources <> 1 THEN 1 ELSE 0 END) AS badSources
       WHERE current <> 1 OR mislabelled > 0 OR badSources > 0
       RETURN slot, current, mislabelled, badSources')"
    if [ -n "$out" ]; then
      echo "memory: slots without exactly one current fact, or with a fact that is mislabelled or not from exactly one episode:" >&2
      printf '%s\n' "$out" >&2
      exit 1
    fi
    echo "memory: every slot holds exactly one current fact, each from one episode" ;;
  *)
    awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "${BASH_SOURCE[0]}"
    [ -z "$cmd" ] || [ "$cmd" = "help" ] || [ "$cmd" = "-h" ] || [ "$cmd" = "--help" ] || exit 2 ;;
esac
