import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# The API imports need these set; no real service is contacted in tests.
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/none")
os.environ["EMBED_MODEL"] = "hash-ngram:384"  # no model download in tests
