import hashlib
import json
from datetime import datetime
from typing import Optional

from sentence_transformers import SentenceTransformer
from sqlalchemy import func

from db.sessions import SessionLocal
from db.models import DocumentChunk
from config import settings

EMBEDDING_MODEL = getattr(settings, "semantic_model", "all-MiniLM-L6-v2")

# How many days before a document is considered stale
STALE_POLICY = {
    "syllabus":           365,
    "circular":            90,
    "academic_calendar":  365,
    "hostel_rules":       365,
    "general":            180,
}


class NITCVectorStore:

    def __init__(self):
        # No persistent connection held here. Each method opens a
        # short-lived session from the shared pool (SessionLocal),
        # uses it, then closes it — avoids the connection pool leak.
        with SessionLocal() as db:
            count = db.query(DocumentChunk).count()
        print(f"Connected to PostgreSQL — {count} chunks stored")

        self.embedder = SentenceTransformer(EMBEDDING_MODEL)
        print("Embedding model loaded")

    def upsert_document(self, doc: dict, chunks: list) -> int:
        if not chunks:
            print("WARNING: no chunks — skipped")
            return 0

        doc_id   = doc["document_id"]
        category = doc.get("category", "general")
        audience = doc.get("target_audience", "ALL")
        date_str = doc.get("date_issued", datetime.today().strftime("%Y-%m-%d"))
        title    = doc.get("title", "Untitled")

        self._delete_by_document_id(doc_id)

        texts = []
        pages = []
        for c in chunks:
            if hasattr(c, 'content'):
                texts.append(c.content)
                pages.append(getattr(c, 'page', 1))
            elif hasattr(c, 'page_content'):
                texts.append(c.page_content)
                pages.append(1)
            else:
                texts.append(c)
                pages.append(1)

        print(f"Embedding {len(texts)} chunks for '{title}'...")
        embeddings = self.embedder.encode(texts, show_progress_bar=False)

        with SessionLocal() as db:
            for i, (text, page, emb) in enumerate(zip(texts, pages, embeddings)):
                chunk_id = self._make_chunk_id(doc_id, i)
                new_chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    title=title,
                    category=category,
                    target_audience=audience,
                    date_issued=date_str,
                    page_number=page,
                    chunk_index=i,
                    content=text,
                    embedding=emb.tolist(),
                )
                db.merge(new_chunk)
            db.commit()

        print(f"✓ Stored {len(texts)} chunks for '{title}'")
        return len(texts)

    def query(
        self,
        question: str,
        n_results:       int           = 5,
        category:        Optional[str] = None,
        target_audience: Optional[str] = None,
    ) -> list:
        query_embedding = self.embedder.encode([question])[0].tolist()

        with SessionLocal() as db:
            distance_col = DocumentChunk.embedding.cosine_distance(query_embedding)

            q = db.query(DocumentChunk, distance_col.label("distance"))

            if category:
                q = q.filter(DocumentChunk.category == category)

            if target_audience and target_audience != "ALL":
                q = q.filter(
                    (DocumentChunk.target_audience == target_audience)
                    | (DocumentChunk.target_audience == "ALL")
                )

            results = q.order_by(distance_col.asc()).limit(n_results).all()

        formatted = []
        for chunk, distance in results:
            formatted.append({
                "text": chunk.content,
                "score": round(1 - distance, 4),
                "metadata": {
                    "document_id":     chunk.document_id,
                    "title":           chunk.title,
                    "category":        chunk.category,
                    "target_audience": chunk.target_audience,
                    "date_issued":     str(chunk.date_issued),
                    "page_number":     chunk.page_number,
                    "chunk_index":     chunk.chunk_index,
                },
            })

        return formatted

    def evict_stale_documents(self, dry_run: bool = False) -> list:
        print(f"Running stale-data check (dry_run={dry_run})...")

        with SessionLocal() as db:
            rows = (
                db.query(
                    DocumentChunk.document_id,
                    DocumentChunk.category,
                    DocumentChunk.date_issued,
                )
                .distinct()
                .all()
            )

        if not rows:
            print("Collection is empty.")
            return []

        today = datetime.today().date()
        stale_doc_ids = []

        for doc_id, category, date_issued in rows:
            threshold = STALE_POLICY.get(category, 180)
            if date_issued is None:
                continue
            age_days = (today - date_issued).days
            if age_days > threshold:
                stale_doc_ids.append(doc_id)

        if not stale_doc_ids:
            print("No stale documents found.")
            return []

        print(f"Found {len(stale_doc_ids)} stale documents:")
        for doc_id in stale_doc_ids:
            print(f"  - {doc_id}")

        if not dry_run:
            for doc_id in stale_doc_ids:
                self._delete_by_document_id(doc_id)
            print(f"✓ Deleted {len(stale_doc_ids)} stale documents.")
        else:
            print("Dry run — nothing deleted.")

        return stale_doc_ids

    def _delete_by_document_id(self, document_id: str):
        with SessionLocal() as db:
            deleted_count = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == document_id)
                .delete()
            )
            db.commit()
            if deleted_count > 0:
                print(f"  Removed {deleted_count} old chunks for '{document_id}'")

    @staticmethod
    def _make_chunk_id(document_id: str, chunk_index: int) -> str:
        raw = f"{document_id}__chunk_{chunk_index}"
        return hashlib.md5(raw.encode()).hexdigest()

    def stats(self) -> dict:
        with SessionLocal() as db:
            total = db.query(DocumentChunk).count()
            unique_docs = db.query(DocumentChunk.document_id).distinct().count()

            categories = dict(
                db.query(DocumentChunk.category, func.count())
                .group_by(DocumentChunk.category)
                .all()
            )
            audiences = dict(
                db.query(DocumentChunk.target_audience, func.count())
                .group_by(DocumentChunk.target_audience)
                .all()
            )

        return {
            "total_chunks":     total,
            "unique_documents": unique_docs,
            "by_category":      categories,
            "by_audience":      audiences,
        }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from chunking.chunking import Chunking

    store = NITCVectorStore()

    with open("pdf_to_json/cse_2023_syllabus.json", encoding="utf-8") as f:
        doc = json.load(f)

    pages_and_text = [{"text": doc["content_markdown"], "page_number": 1}]

    chunker = Chunking("recursive")
    chunk_results = chunker.chunk(pages_and_text)
    print(f"Total chunks: {len(chunk_results)}")

    store.upsert_document(doc, chunk_results)

    questions = [
        "What are the list of electives for BTech CSE?",
        "How many activity points are required?",
        "What programming courses are taught?",
        "How many credits are needed to graduate?",
    ]

    for q in questions:
        print(f"\nQ: {q}")
        results = store.query(q, n_results=2)
        for r in results:
            print(f"  Score {r['score']:.3f} | {r['text'][:80]}")

    print("\n── Stats ───────────────────────────────")
    print(json.dumps(store.stats(), indent=2))

    print("\n✓ Smoke test passed.")