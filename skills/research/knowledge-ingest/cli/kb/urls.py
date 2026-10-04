"""URL identity: when two URLs are the same resource.

Moved here from scripts/url_identity.py so it ships inside the kb package;
that script now imports it. Matching is deliberate, not naive: stripping query
strings collapses every YouTube link to "youtube.com/watch". Video ids are
preserved; tracking parameters are dropped. The alias tables were verified case
by case against the corpus, not guessed.
"""
import re
import urllib.parse

# Parameters that identify the resource and must be kept.
MEANINGFUL_QS = {"v", "id", "p", "list", "paper_id", "arxiv"}
# Common tracking parameters, always dropped.
TRACKING = re.compile(r"^(utm_|ref|si|s|feature|fbclid|gclid|mc_|source|usp)")


# Known aliases: the same resource reachable under a different host, path or
# owner. Verified case by case against both corpora — not guessed. Without
# these the diff reports dozens of false "only external" hits.
REPO_RENAMES = {
    "openaccess-ai-collective/axolotl": "axolotl-ai-cloud/axolotl",
    "facebookresearch/llama-recipes": "meta-llama/llama-cookbook",
    "mozilla-ocho/llamafile": "mozilla-ai/llamafile",
    "neuralmagic/guidellm": "vllm-project/guidellm",
}


# Unsloth doc pages that were renamed, not just moved. Verified by comparing
# the slug lists on both sides.
UNSLOTH_SLUGS = {
    "reinforcement-learning-guide": "reinforcement-learning-rl-guide",
    "how-to-finetune-llama-3-and-export-to-ollama":
        "tutorial-how-to-finetune-llama-3-and-use-in-ollama",
    "qwen3-vl-run-and-fine-tune": "qwen3-vl-how-to-run-and-fine-tune",
    "tutorials-how-to-fine-tune-and-run-llms": "tutorials",
}


# Sites that moved domain. Each pair was confirmed present on both sides with
# the same article slug before being added here.
HOST_MOVES = {
    "mlops.systems": "alexstrick.com",          # same author, same post slugs
    "e2eml.school": "brandonrohrer.com",
    "buttondown.email": "buttondown.com",
    "camdavidsonpilon.github.io": "dataorigami.net",
    "eigenfoo.xyz": "georgeho.org",
    "v0.dev": "v0.app",
}


def apply_aliases(host: str, path: str) -> tuple[str, str]:
    host = HOST_MOVES.get(host, host)
    # apeatling moved dated permalinks to /articles/.
    if host == "apeatling.com":
        path = re.sub(r"^/\d{4}/\d{2}/\d{2}/", "/articles/", path).removesuffix(".html")
    # The OpenAI cookbook moved to developers.openai.com/cookbook/.
    if host == "cookbook.openai.com":
        host, path = "developers.openai.com", "/cookbook" + path
    # x.ai renamed /blog/ to /news/; jordivillar /data/ to /blog/.
    if host == "x.ai":
        path = path.replace("/blog/", "/news/")
    if host == "jordivillar.com":
        path = path.replace("/data/", "/blog/")
    # MIT OCW dropped the department segment from course paths.
    if host == "ocw.mit.edu":
        path = re.sub(r"^/courses/[a-z-]+/(\d)", r"/courses/\1", path)
    # Renamed repos / model orgs.
    path = re.sub(r"/videlalvaro/leet-llm", "/videlalvaro/inference-school", path, flags=re.I)
    path = re.sub(r"/ds4sd/smoldocling", "/docling-project/SmolDocling", path, flags=re.I)
    # The "Inside vLLM" article is published on both the author's site and vllm.ai.
    if (host, path) == ("vllm.ai", "/blog/2025-09-05-anatomy-of-vllm"):
        host, path = "aleksagordic.com", "/blog/vllm"
    # Unsloth moved docs.unsloth.ai/X to unsloth.ai/docs/X AND restructured the
    # tree underneath. Page slugs stayed unique, so key on the final slug.
    if host in ("docs.unsloth.ai", "unsloth.ai") and (host == "docs.unsloth.ai"
                                                      or path.startswith("/docs")):
        slug = path.rstrip("/").split("/")[-1]
        slug = UNSLOTH_SLUGS.get(slug, slug)
        return "unsloth.ai", "/docs/" + slug

    # Blog subdomain vs /blog/ path — same article, two URL shapes.
    for sub, base in (("blog.lancedb.com", "lancedb.com"),
                      ("blog.llamaindex.ai", "llamaindex.ai"),
                      ("blog.vllm.ai", "vllm.ai")):
        if host == sub:
            host, path = base, "/blog" + path
    if host == "vllm.ai" and path.startswith("/blog/"):
        # blog.vllm.ai/2025/11/19/slug.html vs vllm.ai/blog/2025-11-19-slug
        path = re.sub(r"^/blog/(\d{4})/(\d{2})/(\d{2})/([^/]+?)(\.html)?$",
                      r"/blog/\1-\2-\3-\4", path)
    # Stability renamed /news/ to /news-updates/.
    if host == "stability.ai":
        path = path.replace("/news-updates/", "/news/")
    # Slack engineering dropped the Medium hash suffix from its slugs.
    if host == "slack.engineering":
        path = re.sub(r"-[0-9a-f]{12}$", "", path)
    # O'Reilly moved the reader to learning.oreilly.com.
    if host == "learning.oreilly.com":
        host = "oreilly.com"

    # Lightning renamed /studios/ to /templates/ and /pages/courses/ to /courses/.
    if host == "lightning.ai":
        path = path.replace("/studios/", "/templates/").replace("/pages/courses/", "/courses/")
    # DeepLearning.AI renamed /short-courses/ to /courses/, and learn.* is the
    # course player for the same course as the www landing page.
    if host in ("deeplearning.ai", "learn.deeplearning.ai"):
        path = path.replace("/short-courses/", "/courses/")
        path = re.sub(r"(/courses/[^/]+)/lesson/.*$", r"\1", path)
        return "deeplearning.ai", path
    # GitHub repo renames.
    if host == "github.com":
        m = re.match(r"^/([^/]+/[^/]+)(/.*)?$", path)
        if m and m.group(1).lower() in REPO_RENAMES:
            path = "/" + REPO_RENAMES[m.group(1).lower()] + (m.group(2) or "")
    return host, path


def norm(url: str) -> str:
    """Canonical key for one URL. Two URLs sharing a key are the same resource."""
    url = (url or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    p = urllib.parse.urlparse(url)
    host = p.netloc.lower().split("@")[-1].split(":")[0]
    for prefix in ("www.", "m.", "mobile."):
        host = host.removeprefix(prefix)
    path = p.path.rstrip("/")

    # YouTube: the video id IS the identity; the path never is.
    if host in ("youtube.com", "youtu.be", "youtube-nocookie.com"):
        q = urllib.parse.parse_qs(p.query)
        vid = q.get("v", [None])[0]
        if not vid and host == "youtu.be":
            vid = path.lstrip("/")
        for seg in ("/embed/", "/live/", "/shorts/", "/v/"):
            if not vid and seg in path:
                vid = path.split(seg)[-1].split("/")[0]
        if not vid and (lst := q.get("list", [None])[0]):
            return f"youtube:playlist:{lst}"
        return f"youtube:{vid}" if vid else "youtube:" + path

    # arXiv: /abs/ID and /pdf/ID are the same paper.
    if host == "arxiv.org":
        m = re.search(r"/(?:abs|pdf)/([0-9v.]+)", path)
        if m:
            return f"arxiv:{m.group(1).rstrip('.')}"

    # GitHub: strip the trailing view fragments that do not change the resource.
    if host == "github.com":
        path = re.sub(r"/(tree|blob)/(main|master)/?$", "", path)

    host, path = apply_aliases(host, path)

    keep = {k: v for k, v in urllib.parse.parse_qs(p.query).items()
            if k in MEANINGFUL_QS and not TRACKING.match(k)}
    qs = "?" + urllib.parse.urlencode(sorted(keep.items()), doseq=True) if keep else ""
    return f"{host}{path}{qs}".lower()
