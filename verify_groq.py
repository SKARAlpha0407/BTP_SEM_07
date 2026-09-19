
import os
from dotenv import load_dotenv
from backend.app.llm_service import extract_insights_batch

load_dotenv()
key = os.getenv("GROQ_API_KEY")
if not key:
    print("BLOCKED: waiting for API key")
    exit(1)

test_papers = [
    {"title": "Paper A", "abstract": "About RAG and vectors."},
    {"title": "Paper B", "abstract": "About LLM quantization."}
]
try:
    res = extract_insights_batch(test_papers)
    print(f"SUCCESS: Extracted {len(res)} results")
    print(res)
except Exception as e:
    print(f"FAILURE: {e}")
    exit(1)
