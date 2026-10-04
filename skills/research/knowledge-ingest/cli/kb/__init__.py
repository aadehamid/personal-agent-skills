"""kb — read-only validation for knowledge-ingest bundles.

Every check exists because a real ingest or review hit the failure. None of them
can say whether a sentence is true to its source; that is the independent
reviewer's job (Gate B). `kb` makes Gate A cheaper and harder to get wrong.
"""

__version__ = "0.1.0"
