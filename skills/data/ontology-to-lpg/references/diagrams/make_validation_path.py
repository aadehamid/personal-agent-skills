"""Write validation-path.excalidraw: the validation path V1 to V14 and GRAPH TYPE G1 to G4 (references/multi-store.md)."""
import json, random, sys

random.seed(11)
els = []
B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

def rid():
    return "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(16))

def base(kind, x, y, w, h, **kw):
    n = len(els)
    e = dict(id=rid(), type=kind, x=x, y=y, width=w, height=h, angle=0,
             strokeColor=kw.pop("stroke", "#1e1e1e"), backgroundColor=kw.pop("bg", "transparent"),
             fillStyle="solid", strokeWidth=kw.pop("sw", 2), strokeStyle=kw.pop("style", "solid"),
             roughness=1, opacity=100, groupIds=[], frameId=None, roundness=kw.pop("roundness", {"type": 3}),
             seed=random.randint(1, 2**31), version=1, versionNonce=random.randint(1, 2**31),
             isDeleted=False, boundElements=[], updated=1, link=None, locked=False,
             index=("a" + B62[n]) if n < 62 else ("b" + B62[(n - 62) // 62] + B62[(n - 62) % 62]))
    e.update(kw)
    els.append(e)
    return e

def text(x, y, w, h, s, size=16, container=None, align="center", valign="middle", color="#1e1e1e"):
    t = base("text", x, y, w, h, stroke=color, roundness=None, text=s, fontSize=size, fontFamily=5,
             textAlign=align, verticalAlign=valign, containerId=container["id"] if container else None,
             originalText=s, autoResize=True, lineHeight=1.25)
    if container:
        container["boundElements"].append({"type": "text", "id": t["id"]})
    return t

def box(x, y, w, h, label, bg, size=15):
    r = base("rectangle", x, y, w, h, bg=bg)
    text(x + 8, y + 8, w - 16, h - 16, label, size, container=r)
    return r

def group(x, y, w, h, title, color):
    base("rectangle", x, y, w, h, stroke=color, sw=1, style="dashed")
    text(x + 12, y + 8, w - 24, 26, title, 20, align="left", valign="top", color=color)

SIDES = {"r": (1, 0.5), "l": (0, 0.5), "t": (0.5, 0), "b": (0.5, 1)}
def arrow(a, b, label=None, side=("r", "l"), dashed=False, color="#1e1e1e"):
    fa, fb = SIDES[side[0]], SIDES[side[1]]
    x1, y1 = a["x"] + a["width"] * fa[0], a["y"] + a["height"] * fa[1]
    x2, y2 = b["x"] + b["width"] * fb[0], b["y"] + b["height"] * fb[1]
    ar = base("arrow", x1, y1, abs(x2 - x1), abs(y2 - y1), roundness={"type": 2}, stroke=color,
              style="dashed" if dashed else "solid", points=[[0, 0], [x2 - x1, y2 - y1]], lastCommittedPoint=None,
              startBinding={"elementId": a["id"], "fixedPoint": list(fa), "mode": "orbit"},
              endBinding={"elementId": b["id"], "fixedPoint": list(fb), "mode": "orbit"},
              startArrowhead=None, endArrowhead="arrow", elbowed=False)
    a["boundElements"].append({"type": "arrow", "id": ar["id"]})
    b["boundElements"].append({"type": "arrow", "id": ar["id"]})
    if label:
        text(0, 0, 220, 40, label, 13, container=ar)
    return ar

ORANGE, GREEN, PURPLE, RED, BLUE = "#ffd8a8", "#b2f2bb", "#d0bfff", "#ffc9c9", "#a5d8ff"
W, H, GAP = 250, 150, 30

def row(x0, y, labels, bg):
    out = []
    for i, s in enumerate(labels):
        out.append(box(x0 + i * (W + GAP), y, W, H, s, bg))
    for a, b in zip(out, out[1:]):
        arrow(a, b)
    return out

text(0, -110, 2200, 40, "Ontology to stores: validation path and GRAPH TYPE", 32, align="left", valign="top")
text(0, -66, 2200, 26, "Each check must pass before the next runs. Any failure stops the run, and no report is written.", 18, align="left", valign="top", color="#495057")

rel = box(-300, 40, 230, 110, "Released packages\n+ data", BLUE, 18)

group(-20, -10, 5 * (W + GAP) + 10, 230, "Before the load (on the files)", "#e8590c")
pre = row(0, 40, [
    "V1 Design rules:\none kind + one range per\npredicate (Rule 1);\ncardinality shape (Rule 2)",
    "V2 Full SHACL\n(pySHACL + SHACL-AF)\nover asserted + inferred:\n0 violations",
    "V3 Reason once\n(ROBOT + ELK);\nkeep only real\ninferences",
    "V4 check-serialised:\none triple per line, sorted,\nno repeats, nothing\nasserted in inferred.nt",
    "V5 Manifest:\nSHA-256 of every\ninput and shape file"], ORANGE)
arrow(rel, pre[0])

group(-20, 270, 7 * (W + GAP) + 10, 230, "In the local Neo4j (Docker + n10s)", "#2f9e44")
neo = row(0, 320, [
    "V6 Load in a fixed\norder; every import\nreturns OK",
    "V7 Engine readback:\nlistShapes() vs the shapes\nfile; every constraint n10s\ndid not compile is listed",
    "V8 n10s SHACL\nvalidate():\n0 violations",
    "V9 One fail case per\ncompiled constraint: right\nnode, path, component;\na mutant is caught",
    "V10 Round trip:\nexport back to RDF,\n0 lost, 0 added",
    "V11 Determinism:\nsorted and shuffled\nloads give one hash",
    "V12 Report written only\nwhen all pass;\ncheck-report: passed,\nfingerprints current"], GREEN)
arrow(pre[-1], neo[0], side=("b", "t"))

group(-20, 550, 2 * (W + GAP) + 10, 230, "Delivery", "#6741d9")
dl = [box(W + GAP, 600, W, H, "V13 Aura copy:\nAura hash = local hash\n= report hash", PURPLE),
      box(0, 600, W, H, "V14 Triple store:\ncounts per graph, per\npredicate, three-way\n(files, store, Neo4j)", PURPLE)]
arrow(neo[-1], dl[0], side=("b", "t"))
arrow(neo[-1], dl[1], side=("b", "t"))

gx = 2 * (W + GAP) + 40
group(gx - 20, 550, 4 * (W + GAP) + 10, 380, "GRAPH TYPE on Aura (Enterprise or Aura; Community refuses it)", "#c92a2a")
gt = row(gx, 600, [
    "G1 build.py graph-type:\none statement from the\nsh:targetClass shapes;\nleft-out list as comments",
    "G2 Apply after V13:\nALTER CURRENT GRAPH\nTYPE SET; confirm with\nSHOW CURRENT GRAPH TYPE",
    "G3 Probe: a write that\nbreaks the type must\nfail (ConstraintValidation\nFailed)",
    "G4 From then on Aura\nrejects bad writes from\napps; n10s cannot run\nthere"], RED)
arrow(dl[0], gt[0])
box(gx, 780, 4 * (W + GAP) - GAP, 120,
    "Covers: labels, property types, NOT NULL (minCount 1 + maxCount 1), lists, relationship endpoints.\n"
    "Leaves out: counts on relationships, sh:in, sh:pattern, ranges, lengths (no GRAPH TYPE form).\n"
    "Coverage depends on sh:targetClass shapes: shapes targeted by node or SPARQL give no element type.\n"
    "It adds a guard for later writes; the n10s gate (V6-V12) stays the proof.", "#fff5f5", 15)

json.dump({"type": "excalidraw", "version": 2, "source": "https://excalidraw.com", "elements": els,
           "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None}, "files": {}},
          open(sys.argv[1], "w"), indent=1)
print(len(els), "elements")
