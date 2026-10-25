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
    """uri as it may be printed or stored: all userinfo (anything before @ in the authority) and the
    value of every credential-like query key become ***, and the fragment is dropped. A value that is not a URL
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
    if "@" in netloc:   # all userinfo goes, with or without a colon: https://TOKEN@host is a credential too
        netloc = "***@" + netloc.rpartition("@")[2]
    query = urlencode([(k, "***" if any(s in k.lower() for s in SECRET_QUERY_KEYS) else v)
                       for k, v in parse_qsl(parts.query, keep_blank_values=True)], safe="*")
    return urlunsplit((parts.scheme, netloc, parts.path, query, ""))


def scrub(text, secrets):
    """text with every non-empty secret replaced by ***, for a message the script wrote itself."""
    text = str(text)
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "***")
    return text


class Refusal(ValueError):
    """A refusal the script words itself: fixed text that names only the script's own flags, keys
    and checks, and counts. It never holds text the user supplied (a path, a value, an unknown
    option, a report's content) or a library's message, so it can be printed as it is."""


def error_line(context, exc):
    """What an error path prints: a Refusal's own text, or else the fixed context and the exception's
    type name. Never a library's message or a path, which can carry a URL or a credential from the
    arguments, the environment or a file."""
    if isinstance(exc, Refusal):
        return str(exc)
    return f"{context} ({type(exc).__name__})"


def unverified_report(fails):
    """The refusal for a projection report that did not earn its pass: a count, never the report's
    content; build.py check-report lists each failed check."""
    return Refusal(f"the projection report is not a verified report ({len(fails)} check(s) failed); "
                   "run build.py check-report on it to see which")
