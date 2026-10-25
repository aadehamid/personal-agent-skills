"""The one helper for every value a script in scripts/ prints.

A person or an agent pastes what these scripts print into a shell, so every printed value that
comes from input, a path, a hash, a name or a shape term goes through q() (shlex.quote of its text:
a newline, $(...), a backtick or < > stays one shell word), and every Cypher comment through
comment(). test_engine_gate.PrintedValues reads every script's syntax tree and fails on a print
that interpolates anything else.
"""
import json
import shlex


def q(value):
    return shlex.quote(str(value))


def comment(text):
    """A Cypher comment line holding text as one quoted, escaped word."""
    return "// " + q(json.dumps(text, ensure_ascii=False)[1:-1])


# Query keys whose values are credentials in a URL (a signed URL, a token in the query string).
SECRET_QUERY_KEYS = ("token", "password", "passwd", "pwd", "secret", "key", "sig", "signature", "auth",
                     "credential", "code")


def redact(uri):
    """uri as it may be printed or stored: the password in user:password@ and the value of every
    credential-like query key become ***, and the fragment is dropped. A value that is not a URL
    comes back unchanged."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    text = str(uri)
    try:
        parts = urlsplit(text)
    except ValueError:
        return "***"
    if not parts.scheme or not parts.netloc:
        return text
    netloc = parts.netloc
    if "@" in netloc:
        user, _, host = netloc.rpartition("@")
        netloc = (user.split(":", 1)[0] + ":***" if ":" in user else user) + "@" + host
    query = urlencode([(k, "***" if any(s in k.lower() for s in SECRET_QUERY_KEYS) else v)
                       for k, v in parse_qsl(parts.query, keep_blank_values=True)], safe="*")
    return urlunsplit((parts.scheme, netloc, parts.path, query, ""))


def scrub(text, secrets):
    """text with every non-empty secret replaced by ***, for a message the script wrote itself."""
    text = str(text)
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "***")
    return text
