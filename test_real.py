import json
from vector_store import NITCVectorStore

store = NITCVectorStore()

# load Rahan's actual file
with open("pdf_to_json/cse_2023_syllabus.json", encoding="utf-8") as f:
    doc = json.load(f)


USE_CHUNKER = False

if USE_CHUNKER:
    from chunking.chunking import Chunking
    
    # Use intelligent recursive chunking
    pages_and_text = [
        {"text": doc["content_markdown"], "page_number": 1}
    ]
    chunker = Chunking(strategy="recursive")
    chunk_results = chunker.chunk(pages_and_text=pages_and_text, overlap_size=20)
    chunks = [chunk.content for chunk in chunk_results]
    print(f"Total chunks: {len(chunks)} (using recursive chunker)")
else:

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