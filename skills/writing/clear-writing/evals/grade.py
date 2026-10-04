#!/usr/bin/env python3
"""Programmatic grader for clear-writing evals. Usage: grade.py <iteration-dir>"""
import json, os, re, sys

AI_WORDS = r"\b(delve|leverag\w*|seamless\w*|pivotal|robust|testament|underscor\w*|showcas\w*|foster\w*|tapestry|crucial|additionally|utiliz\w*|cutting-edge|unwavering|landscape|vibrant|game-chang\w*|synerg\w*)\b"
CHATBOT = r"(I hope this helps|Let me know if|Great question|Certainly!|Of course!|Happy to help|Feel free to)"
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2705\u2B50]")

def read(p):
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""

def sentences(t):
    t = re.sub(r"```.*?```", "", t, flags=re.S)
    t = re.sub(r"^\s*([#>|-]|\d+\.).*$", lambda m: m.group(0).lstrip("#>-| 0123456789."), t, flags=re.M)
    return [s for s in re.split(r"(?<=[.!?])\s+", t) if len(s.split()) > 2]

def avg_len(t):
    s = sentences(t)
    return sum(len(x.split()) for x in s) / max(len(s), 1)

def common(main, resp):
    out = []
    n = main.count("\u2014") + len(re.findall(r"\s\u2013\s", main))
    out.append(("No em dashes or spaced en dashes in the deliverable", n == 0, f"{n} dashes"))
    hits = sorted(set(m.lower() for m in re.findall(AI_WORDS, main, re.I)))
    out.append(("No AI-vocabulary words (delve, leverage, seamless, pivotal...)", not hits, f"found: {hits}"))
    cb = re.findall(CHATBOT, resp, re.I)
    out.append(("Chat reply has no chatbot filler phrases", not cb, f"found: {cb}"))
    return out

def g_explainer(o):
    main, resp = read(f"{o}/explanation.md"), read(f"{o}/response.md")
    r = common(main, resp)
    wc = len(main.split())
    r.append(("Explanation is short (<350 words)", 0 < wc < 350, f"{wc} words"))
    first = " ".join(sentences(main)[:2])
    r.append(("Answer first: MQTT named in the first two sentences", "MQTT" in first, first[:200]))
    a = avg_len(main)
    r.append(("Average sentence length <= 20 words", a <= 20, f"avg {a:.1f}"))
    bl = re.findall(r"\*\*[^*\n]+:\*\*", main)
    r.append(("No bold 'Label:' lead-ins", not bl, f"found: {bl}"))
    sm = re.findall(r"^#+\s*(bottom line|summary|in summary|conclusion|tl;dr)", main, re.I | re.M)
    r.append(("No restating summary section (Bottom line / Summary)", not sm, f"found: {sm}"))
    return r

def g_post(o):
    main, resp = read(f"{o}/post.md"), read(f"{o}/response.md")
    r = common(main, resp)
    e = EMOJI.findall(main)
    r.append(("No emoji", not e, f"{len(e)} emoji"))
    bl = re.findall(r"\*\*[^*]+:\*\*", main)
    r.append(("No bold-label inline-header bullets", not bl, f"found: {bl}"))
    h = re.findall(r"#\w+", main)
    r.append(("At most 3 hashtags", len(h) <= 3, f"{len(h)} hashtags"))
    r.append(("Keeps facts: 14 systems and 3 regions", "14" in main and re.search(r"\b(3|three)\b", main) is not None, ""))
    tail = main.strip().splitlines()[-3:] if main.strip() else []
    gen = re.search(r"(future|brighter|exciting times|journey|stay tuned)", " ".join(tail), re.I)
    r.append(("No generic closing line", not gen, f"tail: {tail}"))
    pct = re.findall(r"\d+\s?%", main)
    r.append(("No invented percentages (none in source)", not pct, f"found: {pct}"))
    return r

def g_runbook(o):
    main, resp = read(f"{o}/runbook.md"), read(f"{o}/response.md")
    r = common(main, resp)
    steps = re.findall(r"^\s*\d+\.\s", main, re.M)
    r.append(("Uses numbered steps (>=4)", len(steps) >= 4, f"{len(steps)} numbered lines"))
    low = main.lower()
    w = [m.start() for m in re.finditer(r"(lost permanently|permanently lost|permanently loses|permanently deletes|lost for good|cannot be recovered|can't be recovered|data loss|lose data|lost for good|deletes|is lost|are lost)", low)]
    # The clear step is a numbered line that deletes/clears files in the buffer folder.
    c = [m.start() for m in re.finditer(r"^\s*\d+\.\s[^\n]*(delete|clear|remove)[^\n]*buffer", low, re.M)]
    ok = bool(w and c and min(w) < min(c))
    r.append(("Data-loss warning appears before the buffer-clear step", ok, f"warning@{w[:3]} clear@{c[:3]}"))
    need = ["HIST-COL-02", r"D:\Collector\logs", r"D:\Collector\buffer", "bufutil", "services.msc"]
    miss = [n for n in need if n.lower() not in low]
    r.append(("Preserves hostnames, paths and commands", not miss, f"missing: {miss}"))
    r.append(("Preserves 60-minute RTU window and 5-minute check", ("60" in main or "hour" in low) and "5 min" in low, ""))
    return r

ORIGINAL_REPITCH_WORDS = 125  # word count of the previous message in repitch_context.md

def g_repitch(o):
    main = read(f"{o}/reply.md")
    r = common(main, read(f"{o}/response.md") or main)
    wc = len(main.split())
    # Plain words take more room than jargon, so allow up to 20% over the original.
    r.append(("Reply is at most 20% longer than the original message", 0 < wc <= ORIGINAL_REPITCH_WORDS * 1.2, f"{wc} words vs {ORIGINAL_REPITCH_WORDS}"))
    a = avg_len(main)
    r.append(("Average sentence length <= 20 words", a <= 20, f"avg {a:.1f}"))
    low = main.lower()
    labels = ["target mode", "`target`", "hold gate", "drift-allow", "uns-gen", "re-alias", "w/ "]
    left = [l for l in labels if l in low]
    r.append(("Internal labels from the original are replaced with plain words", not left, f"still present: {left}"))
    arrows = re.findall("[\u2192\u21d2]|->|=>", main)
    r.append(("No arrows or symbol-speak", not arrows, f"found: {arrows}"))
    last = [s for s in sentences(main) if s.strip()][-1:] or [""]
    r.append(("Ends with the decision the user must make (a question)", last[0].strip().endswith("?"), f"last: {last[0][:120]}"))
    return r

GRADERS = {"mqtt-vs-opcua-explainer": g_explainer, "unslop-linkedin-post": g_post, "historian-runbook": g_runbook, "wait-what-repitch": g_repitch}

it = sys.argv[1]
for ev, fn in GRADERS.items():
    for cfg in ("with_skill", "without_skill", "old_skill"):
        import glob as _g; m = _g.glob(f"{it}/eval-*-{ev}"); d = f"{m[0]}/{cfg}/run-1" if m else ""
        if not os.path.isdir(f"{d}/outputs"):
            continue
        res = fn(f"{d}/outputs")
        exp = [{"text": t, "passed": bool(p), "evidence": e} for t, p, e in res]
        passed = sum(x["passed"] for x in exp)
        g = {"expectations": exp, "summary": {"passed": passed, "failed": len(exp) - passed, "total": len(exp), "pass_rate": round(passed / len(exp), 2)}}
        json.dump(g, open(f"{d}/grading.json", "w"), indent=2)
        print(f"{ev:28} {cfg:14} {passed}/{len(exp)}")
