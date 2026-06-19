# Chunking Module

Split large documents into smaller, meaningful chunks for RAG pipelines.

---

## Quick Start

```python
from chunking import Chunking

# Prepare data
pages_and_text = [
    {"text": "Your document text here...", "page_number": 1},
    {"text": "More document text...", "page_number": 2},
]

# Create chunker
chunker = Chunking(strategy="recursive", pages_and_text=pages_and_text)

# Get chunks
chunks = chunker.chunk()

# Use chunks
for chunk in chunks:
    print(chunk.content)
```

---

## Input

**Type**: `list[dict]`

Each dict must have:
- `"text"` (str): The document text to chunk.
- `"page_number"` (int): Page identifier.

**Example**:
```python
[
    {"text": "Document content here...", "page_number": 1},
    {"text": "More content...", "page_number": 2},
]
```

---

## Output

**Type**: `list[ChunkResult]`

Each `ChunkResult` has:
- `chunk_id` (int): Unique ID.
- `content` (str): The chunk text.
- `page` (int): Original page number.
- `strategy` (str): Strategy used.
- `token_count` (int): Tokens in chunk.

**Example**:
```python
ChunkResult(
    chunk_id=0,
    content="Document content here...",
    page=1,
    strategy="recursive",
    token_count=5
)
```

---

## Available Strategies

- `"fixed"` — Split by word count.
- `"sentence-chunking"` — Group sentences.
- `"semantic"` — Group by embedding similarity.
- `"recursive"` — Hierarchical split on structure.
- `"hybrid-semantic"` — Semantic + recursive.

---

## Configuration

Set in `.env`:

```bash
CHUNK_SIZE=200                    # Target tokens per chunk
MIN_CHUNK_SIZE=50                 # Minimum tokens
SIMILARITY_THRESHOLD=0.7          # For semantic strategies
MAX_TOKENS=500                    # Max tokens per chunk
CHUNKING_STRATEGY=recursive       # Default strategy
```

See `.env.example` for all options.

---

## Installation

```bash
pip install -r ../requirements.txt
```

---



