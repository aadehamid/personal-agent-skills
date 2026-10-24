"""Write data-flow.excalidraw: one release through triple stores, Neo4j and Aura (references/multi-store.md)."""
import json, random, sys

random.seed(7)
els = []
B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
def rid():
    return "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(16))

def base(kind, x, y, w, h, **kw):
    e = dict(id=rid(), type=kind, x=x, y=y, width=w, height=h, angle=0,
             strokeColor=kw.pop("stroke", "#1e1e1e"), backgroundColor=kw.pop("bg", "transparent"),
             fillStyle="solid", strokeWidth=kw.pop("sw", 2), strokeStyle=kw.pop("style", "solid"),
             roughness=1, opacity=100, groupIds=[], frameId=None, roundness=kw.pop("roundness", {"type": 3}),
             seed=random.randint(1, 2**31), version=1, versionNonce=random.randint(1, 2**31),
             isDeleted=False, boundElements=[], updated=1, link=None, locked=False)
    e.update(kw)
    e["index"] = ("a" + B62[len(els)]) if len(els) < 62 else ("b" + B62[(len(els) - 62) // 62] + B62[(len(els) - 62) % 62])
    els.append(e)
    return e

def text(x, y, w, h, s, size=16, container=None, align="center", valign="middle", color="#1e1e1e"):
    t = base("text", x, y, w, h, stroke=color, roundness=None, text=s, fontSize=size, fontFamily=5,
             textAlign=align, verticalAlign=valign, containerId=container["id"] if container else None,
             originalText=s, autoResize=True, lineHeight=1.25)
    if container:
        container["boundElements"].append({"type": "text", "id": t["id"]})
    return t

def box(x, y, w, h, label, bg, size=16, style="solid"):
    r = base("rectangle", x, y, w, h, bg=bg, style=style)
    text(x + 8, y + 8, w - 16, h - 16, label, size, container=r)
    return r

def group(x, y, w, h, title, color):
    base("rectangle", x, y, w, h, stroke=color, sw=1, style="dashed", roundness={"type": 3})
    text(x + 12, y + 8, w - 24, 26, title, 20, align="left", valign="top", color=color)

def arrow(a, b, label=None, side=("r", "l"), dashed=False):
    def pt(e, s):
        cx, cy = e["x"] + e["width"] / 2, e["y"] + e["height"] / 2
        return {"r": (e["x"] + e["width"], cy), "l": (e["x"], cy), "t": (cx, e["y"]), "b": (cx, e["y"] + e["height"])}[s]
    (x1, y1), (x2, y2) = pt(a, side[0]), pt(b, side[1])
    ar = base("arrow", x1, y1, abs(x2 - x1), abs(y2 - y1), roundness={"type": 2}, style="dashed" if dashed else "solid",
              points=[[0, 0], [x2 - x1, y2 - y1]], lastCommittedPoint=None,
              startBinding={"elementId": a["id"], "focus": 0, "gap": 6},
              endBinding={"elementId": b["id"], "focus": 0, "gap": 6},
              startArrowhead=None, endArrowhead="arrow", elbowed=False)
    a["boundElements"].append({"type": "arrow", "id": ar["id"]})
    b["boundElements"].append({"type": "arrow", "id": ar["id"]})
    if label:
        text(0, 0, 200, 40, label, 14, container=ar)
    return ar

BLUE, PURPLE, ORANGE, GREEN, GRAY = "#a5d8ff", "#d0bfff", "#ffd8a8", "#b2f2bb", "#e9ecef"

text(0, -90, 1900, 40, "Ontology to stores: end-to-end data flow", 32, align="left", valign="top")
text(0, -48, 1900, 26, "Every hop is checked against the released files, so a loss shows where it happened.", 18, align="left", valign="top", color="#495057")

group(-20, -10, 300, 470, "Sources", "#495057")
ev1 = box(0, 40, 260, 70, "Source documents", GRAY)
ev2 = box(0, 140, 260, 70, "Industry and peer sources", GRAY)
ev3 = box(0, 240, 260, 70, "Reference process model", GRAY)

group(320, -10, 340, 470, "Ontology build (ontology skill, Steps 1-11)", "#1971c2")
b1 = box(340, 40, 300, 90, "W3C stack: RDF, OWL, SKOS,\nSHACL, PROV-O, DCAT", BLUE)
b2 = box(340, 170, 300, 90, "check.sh, pySHACL,\ncompetency questions (SPARQL)", BLUE)
b3 = box(340, 300, 300, 100, "Released packages\n+ DCAT catalog (git tags)", BLUE, 18)
for e in (ev1, ev2, ev3):
    arrow(e, b1)
arrow(b1, b2, side=("b", "t"))
arrow(b2, b3, side=("b", "t"))

sk = box(720, 310, 230, 80, "Skolemize blank nodes\n(stable IRIs)", "#fff3bf")
arrow(b3, sk)

group(1010, -330, 420, 400, "Triple stores", "#6741d9")
jena = box(1030, -280, 380, 90, "Apache Jena Fuseki\nGraph Store Protocol, one named graph per package", PURPLE, 15)
dbx = box(1030, -160, 380, 80, "Databricks: Delta triple table\nin Unity Catalog (planned)", PURPLE)
dfree = box(1030, -60, 180, 100, "Free Edition:\ntransfers run\nfrom your machine", "#eebefa", 14)
dent = box(1230, -60, 180, 100, "Enterprise: your\nmachine, or a job\nin the workspace", "#eebefa", 14)
arrow(sk, jena, "load, export back,\ncompare", side=("t", "l"))
arrow(sk, dbx, "triple for triple", side=("t", "l"))
arrow(dfree, dbx, side=("t", "b"))
arrow(dent, dbx, side=("t", "b"))

group(1010, 130, 420, 400, "ontology-to-lpg skill", "#e8590c")
s1 = box(1030, 180, 380, 70, "Check: design rules, data shapes, refusals", ORANGE, 15)
s2 = box(1030, 290, 380, 70, "Reason: ROBOT + ELK, once, upstream", ORANGE, 15)
s3 = box(1030, 400, 380, 90, "Serialise: loadable.nt + inferred.nt\n(check-serialised)", ORANGE, 15)
arrow(sk, s1, side=("r", "l"))
arrow(s1, s2, side=("b", "t"))
arrow(s2, s3, side=("b", "t"))

group(1490, 130, 420, 400, "Neo4j, local (Docker + n10s)", "#2f9e44")
n1 = box(1510, 180, 380, 80, "n10s load (SHORTEN, fixed order)", GREEN, 15)
n2 = box(1510, 310, 380, 170, "Gate: n10s listShapes() readback,\none fail case per compiled\nconstraint, round trip,\ndeterminism hash", GREEN, 15)
arrow(s3, n1, side=("r", "l"))
arrow(n1, n2, side=("b", "t"))
arrow(jena, n2, "three-way counts\n(--projection-report):\nfiles, store, Neo4j", side=("r", "t"), dashed=True)

group(1490, 590, 420, 260, "Neo4j Aura", "#2f9e44")
a1 = box(1510, 640, 380, 80, "Copy over the driver;\nhash must match the local graph", GREEN, 15)
a2 = box(1510, 750, 380, 80, "GRAPH TYPE: schema enforced\nby the database", GREEN, 15)
arrow(n2, a1, "validated graph", side=("b", "t"))
arrow(a1, a2, side=("b", "t"))

group(1010, 590, 420, 260, "Rebuild test", "#c92a2a")
r1 = box(1030, 640, 380, 180, "Empty local Neo4j and Aura,\nrebuild both from the\nDatabricks export, compare\nwith the released files:\nno loss end to end", "#ffc9c9", 15)
arrow(dbx, r1, side=("l", "l"), dashed=True)
arrow(r1, s1, side=("t", "b"), dashed=True)

group(320, 590, 630, 260, "Later: Unity Catalog", "#495057")
ob = box(340, 640, 590, 180, "OntoBricks (Databricks Labs):\nlink Unity Catalog tables and metric views\n(the KPIs) to the business processes\nin the ontology", GRAY, 16)
arrow(b3, ob, side=("b", "t"), dashed=True)

json.dump({"type": "excalidraw", "version": 2, "source": "https://excalidraw.com", "elements": els,
           "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None}, "files": {}},
          open(sys.argv[1], "w"), indent=1)
print(len(els), "elements")
