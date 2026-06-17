import hashlib #unique id
import json
from datetime import datetime #check old docs
from typing import Optional #None

import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

# ── CONFIG ────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "nitc_nexus",
    "user":     "postgres",
    "password": "postgres123",
}
EMBEDDING_MODEL = "all-MiniLM-L6-v2" 

# How many days before a document is considered stale
STALE_POLICY = {
    "syllabus":           365,  # taken to be 1 year
    "circular":            90,  # taken to be 3 months
    "academic_calendar":  365,
    "hostel_rules":       365,
    "general":            180,  # fallback
}

class NITCVectorStore:
   
    def __init__(self):
        
        # Connect to PostgreSQL
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.conn.autocommit = True
        register_vector(self.conn)

        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks;")
            count = cur.fetchone()[0]
        print(f"Connected to PostgreSQL — {count} chunks stored")

        # Load the embedding model
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)
        print(f"Embedding model loaded")

    def upsert_document(self, doc: dict, chunks: list) -> int:

        if not chunks:
            print(f"WARNING: no chunks — skipped")
            return 0

        doc_id   = doc["document_id"]
        category = doc.get("category", "general")
        audience = doc.get("target_audience", "ALL")
        date_str = doc.get("date_issued", datetime.today().strftime("%Y-%m-%d"))
        title    = doc.get("title", "Untitled")

        # delete old version of this document
        self._delete_by_document_id(doc_id)

        # extract text + page number from whatever chunk format comes in
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

        # convert chunks to embeddings
        print(f"Embedding {len(texts)} chunks for '{title}'...")
        embeddings = self.embedder.encode(texts, show_progress_bar=False)

        # insert each chunk as a row in the chunks table
        with self.conn.cursor() as cur:
            for i, (text, page, emb) in enumerate(zip(texts, pages, embeddings)):
                chunk_id = self._make_chunk_id(doc_id, i)
                cur.execute(
                    """
                    INSERT INTO chunks
                        (chunk_id, document_id, title, category,
                         target_audience, date_issued, page_number,
                         chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding;
                    """,
                    (
                        chunk_id, doc_id, title, category,
                        audience, date_str, page,
                        i, text, emb.tolist(),
                    ),
                )

        print(f"✓ Stored {len(texts)} chunks for '{title}'")
        return len(texts)
    
    def query(
        self,
        question: str,
        n_results:       int           = 5,
        category:        Optional[str] = None,
        target_audience: Optional[str] = None,
    ) -> list[dict]:
        """
        Search for chunks relevant to a question.
        
        question        = the student's question
        n_results       = how many chunks to return (default 5)
        category        = optional filter e.g. "syllabus"
        target_audience = optional filter e.g. "S4"
        """

        # Convert the question to an embedding
        query_embedding = self.embedder.encode([question])[0]

        # Build the WHERE clause as plain SQL
        conditions = []
        params = []

        if category:
            conditions.append("category = %s")
            params.append(category)

        if target_audience and target_audience != "ALL":
            conditions.append("(target_audience = %s OR target_audience = 'ALL')")
            params.append(target_audience)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # pgvector's <=> operator computes cosine DISTANCE
        # (lower = more similar)
        sql = f"""
            SELECT content, document_id, title, category,
                   target_audience, date_issued, page_number, chunk_index,
                   embedding <=> %s AS distance
            FROM chunks
            {where_clause}
            ORDER BY distance ASC
            LIMIT %s;
        """

        with self.conn.cursor() as cur:
            cur.execute(sql, [query_embedding] + params + [n_results])
            rows = cur.fetchall()

        # Reformat results into clean dicts
        formatted = []
        for row in rows:
            (content, doc_id, title, category, audience,
             date_issued, page_number, chunk_index, distance) = row
            formatted.append({
                "text":     content,
                "score":    round(1 - distance, 4),
                "metadata": {
                    "document_id":     doc_id,
                    "title":           title,
                    "category":        category,
                    "target_audience": audience,
                    "date_issued":     str(date_issued),
                    "page_number":     page_number,
                    "chunk_index":     chunk_index,
                },
            })

        return formatted
    def evict_stale_documents(self, dry_run: bool = False) -> list[str]:
        """
        Delete documents that are older than their category's threshold.
        
        dry_run=True  → just print what would be deleted, don't actually delete
        dry_run=False → actually delete
        
        Run this once a week to keep the DB clean.
        """

        print(f"Running stale-data check (dry_run={dry_run})...")

        # Get one row per document (not per chunk)
        with self.conn.cursor() as cur:
            cur.execute("SELECT DISTINCT document_id, category, date_issued FROM chunks;")
            rows = cur.fetchall()

        if not rows:
            print("Collection is empty.")
            return []

        today = datetime.today().date()
        stale_doc_ids = []

        # Check each document's date against its category's threshold
        for doc_id, category, date_issued in rows:
            threshold = STALE_POLICY.get(category, 180)  # days

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

        # Only actually delete if dry_run is False
        if not dry_run:
            for doc_id in stale_doc_ids:
                self._delete_by_document_id(doc_id)
            print(f"✓ Deleted {len(stale_doc_ids)} stale documents.")
        else:
            print("Dry run — nothing deleted.")

        return stale_doc_ids
    
    def _delete_by_document_id(self, document_id: str):
        """Delete ALL chunks that belong to a document_id."""
        
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE document_id = %s;", (document_id,))
            if cur.rowcount > 0:
                print(f"  Removed {cur.rowcount} old chunks for '{document_id}'")

    @staticmethod
    def _make_chunk_id(document_id: str, chunk_index: int) -> str:
        """
        Generate a stable unique ID for a chunk.
        Same document_id + same position always = same ID.
        """
        raw = f"{document_id}__chunk_{chunk_index}"
        return hashlib.md5(raw.encode()).hexdigest()
    def stats(self) -> dict:
        """Show what's in the database — useful for debugging."""
        
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks;")
            total = cur.fetchone()[0]

            cur.execute("SELECT COUNT(DISTINCT document_id) FROM chunks;")
            unique_docs = cur.fetchone()[0]

            cur.execute("SELECT category, COUNT(*) FROM chunks GROUP BY category;")
            categories = dict(cur.fetchall())

            cur.execute("SELECT target_audience, COUNT(*) FROM chunks GROUP BY target_audience;")
            audiences = dict(cur.fetchall())

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