import json
import sys
sys.path.insert(0, ".")

from chunking.chunking import Chunking
from chunking.models import ChunkResult, Strategy
from vector_store import NITCVectorStore

store = NITCVectorStore()

# load Rahan's actual JSON
with open("pdf_to_json/cse_2023_syllabus.json", encoding="utf-8") as f:
    doc = json.load(f)

# convert to Prashant's expected format
pages_and_text = [{"text": doc["content_markdown"], "page_number": 1}]

# run Prashant's chunker
chunker = Chunking("recursive")
chunk_results = chunker.chunk(pages_and_text)

print(f"Total chunks from Prashant's chunker: {len(chunk_results)}")
print(f"First chunk preview: {chunk_results[0].content[:100]}")

# store in your vector store
store.upsert_document(doc, chunk_results)

questions = [
    # Exactly in the document
    "What are the list of electives for BTech CSE?",
    "How many activity points are required for BTech CSE?",
    
    # Somewhat related
    "What programming courses are taught in CSE?",
    "How many credits are needed to graduate?",
    
    # Can be derived
    "Which semester has the most subjects?",
    "What is the workload like in final year CSE?",
    
    # Completely unrelated
    "What is the hostel fee structure?",
    "How do I apply for a scholarship?",
]


for q in questions:
    print(f"\nQ: {q}")
    results = store.query(q, n_results=2)
    for r in results:
        print(f"  Score {r['score']:.3f} | {r['text'][:80]}")