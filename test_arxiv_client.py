
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from backend.app.arxiv_client import search_papers
    print("Import successful")
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

try:
    print("Searching for 'quantum computing'...")
    papers = search_papers("quantum computing", max_results=5)
    print(f"Found {len(papers)} papers.")
    for i, paper in enumerate(papers):
        print(f"[{i+1}] {paper.title}")
        print(f"    ID: {paper.arxiv_id}")
        print(f"    URL: {paper.arxiv_url}")
        print("-" * 20)
except Exception as e:
    print(f"An error occurred during search: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
