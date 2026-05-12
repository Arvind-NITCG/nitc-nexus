import json
from vector_store import NITCVectorStore

store = NITCVectorStore()

# load Rahan's actual file
with open("pdf_to_json/cse_2023_syllabus.json", encoding="utf-8") as f:
    doc = json.load(f)

# split content_markdown into chunks by paragraph
chunks = [c.strip() for c in doc["content_markdown"].split("\n\n") if c.strip()]

print(f"Total chunks: {len(chunks)}")

store.upsert_document(doc, chunks)

# test 5 real questions
questions = [
    "What are the core subjects in CSE?",
    "What electives are available?",
    "What is the credit structure?",
    "Who are the faculty?",
    "What labs are there?",
]

for q in questions:
    print(f"\nQ: {q}")
    results = store.query(q, n_results=2)
    for r in results:
        print(f"  Score {r['score']:.3f} | {r['text'][:80]}")