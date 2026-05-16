import hashlib #unique id
import json
from datetime import datetime #check old docs
from typing import Optional #None

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# ── CONFIG ────────────────────────────────────────────────────────
CHROMA_PATH     = "./nitc_chroma_db"  
COLLECTION_NAME = "nitc_documents"    # like a table name in normal DB
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
   
    def __init__(self, chroma_path: str = CHROMA_PATH):
        
        # Connect to ChromaDB — creates the folder if it doesn't exist
        self.client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(anonymized_telemetry=False),
            # anonymized_telemetry=False means don't send usage data to ChromaDB servers
        )
        
        # Get the collection if it exists, create it if it doesn't
        # metadata={"hnsw:space": "cosine"} means use cosine similarity
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        print(f"Connected — {self.collection.count()} chunks stored")

        # Load the embedding model
        # First time: downloads ~80MB from internet and caches it
        # After that: loads from cache instantly
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

        # handle both list[str] and list[Document] from LangChain
        # Extracts the text from Document objects if needed
        chunks = [
            c.content if hasattr(c, 'content')
            else c.page_content if hasattr(c, 'page_content')
            else c
            for c in chunks]
   

        # convert chunks to embeddings
        print(f"Embedding {len(chunks)} chunks for '{title}'...")
        embeddings = self.embedder.encode(chunks, show_progress_bar=False).tolist()

        # build unique IDs and metadata for each chunk
        chunk_ids = []
        metadatas = []
        for i, chunk in enumerate(chunks):
            
            # unique ID for this chunk — based on doc_id + position
            chunk_id = self._make_chunk_id(doc_id, i)
            chunk_ids.append(chunk_id)
            
            # metadata stored alongside each chunk
            # used for filtering in query()
            metadatas.append({
                "document_id":     doc_id,
                "title":           title,
                "category":        category,
                "target_audience": audience,
                "date_issued":     date_str,
                "chunk_index":     i,
                "ingested_at":     datetime.utcnow().isoformat(),
            })

        # store everything in ChromaDB
        # upsert = insert if new, replace if exists
        self.collection.upsert(
            ids        = chunk_ids,   # unique ID per chunk
            embeddings = embeddings,  # 384 numbers per chunk
            documents  = chunks,      # original text (stored alongside)
            metadatas  = metadatas,   # category, audience, date etc.
        )

        print(f"✓ Stored {len(chunks)} chunks for '{title}'")
        return len(chunks)
    
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
        query_embedding = self.embedder.encode([question]).tolist()

        # Build the WHERE filter clause
        # None means no filter — search everything
        where = self._build_where(category, target_audience)

        # Set up query arguments
        kwargs = {
            "query_embeddings": query_embedding,
            "n_results":        n_results,
            "include":          ["documents", "metadatas", "distances"],
        }
        
        # Only add WHERE clause if we have filters
        if where:
            kwargs["where"] = where

        # Run the search — ChromaDB's HNSW finds closest embeddings
        results = self.collection.query(**kwargs)

        # Reformat results into clean dicts
        formatted = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            formatted.append({
                "text":     doc,
                "score":    round(1 - dist, 4),  # convert distance to similarity
                # distance 0 = identical → similarity 1.0
                # distance 1 = opposite  → similarity 0.0
                "metadata": meta,
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

        # Get all stored metadata
        all_results = self.collection.get(include=["metadatas"])
        
        if not all_results["ids"]:
            print("Collection is empty.")
            return []

        today = datetime.today()
        stale_doc_ids = set()  # use set to avoid duplicates

        # Check each chunk's date against its category's threshold
        for chunk_id, meta in zip(all_results["ids"], all_results["metadatas"]):
            category  = meta.get("category", "general")
            date_str  = meta.get("date_issued", "")
            threshold = STALE_POLICY.get(category, 180)  # days

            if not date_str:
                continue
            
            try:
                issued   = datetime.strptime(date_str, "%Y-%m-%d")
                age_days = (today - issued).days
                
                if age_days > threshold:
                    # this document is too old — mark for deletion
                    stale_doc_ids.add(meta["document_id"])
            except ValueError:
                pass  # skip if date format is wrong

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

        return list(stale_doc_ids)
    
    # ── HELPER FUNCTIONS ──────────────────────────────────────────

    def _delete_by_document_id(self, document_id: str):
        """Delete ALL chunks that belong to a document_id."""
        
        # Find all chunk IDs for this document
        existing = self.collection.get(
            where={"document_id": {"$eq": document_id}},
            include=[],  # we only need IDs, not content
        )
        
        if existing["ids"]:
            self.collection.delete(ids=existing["ids"])
            print(f"  Removed {len(existing['ids'])} old chunks for '{document_id}'")

    @staticmethod
    def _make_chunk_id(document_id: str, chunk_index: int) -> str:
        """
        Generate a stable unique ID for a chunk.
        Same document_id + same position always = same ID.
        This is important for upsert to work correctly.
        """
        raw = f"{document_id}__chunk_{chunk_index}"
        return hashlib.md5(raw.encode()).hexdigest()

    @staticmethod
    def _build_where(
        category:        Optional[str],
        target_audience: Optional[str],
    ) -> Optional[dict]:
        """
        Build a ChromaDB WHERE filter from optional arguments.
        
        If category="syllabus" AND target_audience="S4":
        Returns chunks that are syllabus AND (S4 OR ALL)
        
        The $or for audience means S4 students also get
        documents meant for everyone, not just S4-specific ones.
        """
        conditions = []
        
        if category:
            conditions.append({"category": {"$eq": category}})
        
        if target_audience and target_audience != "ALL":
            conditions.append({
                "$or": [
                    {"target_audience": {"$eq": target_audience}},
                    {"target_audience": {"$eq": "ALL"}},
                ]
            })
        
        if not conditions:
            return None          # no filter
        if len(conditions) == 1:
            return conditions[0] # single filter
        return {"$and": conditions}  # both filters

    def stats(self) -> dict:
        """Show what's in the database — useful for debugging."""
        
        total    = self.collection.count()
        all_meta = self.collection.get(include=["metadatas"])["metadatas"]

        categories = {}
        audiences  = {}
        doc_ids    = set()

        for m in all_meta:
            cat = m.get("category", "?")
            aud = m.get("target_audience", "?")
            categories[cat] = categories.get(cat, 0) + 1
            audiences[aud]  = audiences.get(aud, 0) + 1
            doc_ids.add(m.get("document_id", "?"))

        return {
            "total_chunks":     total,
            "unique_documents": len(doc_ids),
            "by_category":      categories,
            "by_audience":      audiences,
        }
    
    