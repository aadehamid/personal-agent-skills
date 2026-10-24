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
