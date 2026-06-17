from dataclasses import dataclass
from enum import Enum

class Strategy(str, Enum):
    FIXED           = "fixed"
    SENTENCE        = "sentence-chunking"
    SEMANTIC        = "semantic"
    RECURSIVE       = "recursive"
    HYBRID_SEMANTIC = "hybrid-semantic"


@dataclass
class ChunkResult:
    chunk_id:    int
    content:     str
    page:        int
    strategy:    str
    token_count: int


