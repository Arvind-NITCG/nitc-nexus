from __future__ import annotations

import re
from .models import ChunkResult, Strategy
from typing import TYPE_CHECKING

import nltk
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer
from .config import settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer
    from spacy.lang.en import English as SpacyEnglish


_MODEL_CACHE: dict[str, object] = {}



class Chunking:
    def __init__(self, strategy: str) -> None:

        try:
            self.strategy = Strategy(strategy.lower())
        except ValueError:
            valid = ", ".join(s.value for s in Strategy)
            raise ValueError(
                f"Unknown strategy {strategy!r}. Valid options: {valid}"
            )
 
        _tok_key = f"tokenizer:{settings.semantic_model}"
        if _tok_key not in _MODEL_CACHE:
            _MODEL_CACHE[_tok_key] = AutoTokenizer.from_pretrained(settings.semantic_model)
        self.tokenizer: AutoTokenizer = _MODEL_CACHE[_tok_key]

        if self.strategy in (Strategy.SEMANTIC, Strategy.HYBRID_SEMANTIC, Strategy.RECURSIVE):
            self._ensure_nltk()
 
    
 
    def _ensure_nltk(self) -> None:
        for resource in ("tokenizers/punkt", "tokenizers/punkt_tab"):
            try:
                nltk.data.find(resource)
            except LookupError:
                nltk.download(resource.split("/")[-1])
 
    @property
    def semantic_model(self) -> "SentenceTransformer":
        key = f"sentence_transformer:{settings.semantic_model}"
        if key not in _MODEL_CACHE:
            from sentence_transformers import SentenceTransformer
            _MODEL_CACHE[key] = SentenceTransformer(settings.semantic_model)
        return _MODEL_CACHE[key]  # type: ignore[return-value]
 
    @property
    def nlp(self) -> "SpacyEnglish":
        if "spacy_sentencizer" not in _MODEL_CACHE:
            from spacy.lang.en import English
            nlp = English()
            nlp.add_pipe("sentencizer")
            _MODEL_CACHE["spacy_sentencizer"] = nlp
        return _MODEL_CACHE["spacy_sentencizer"]  # type: ignore[return-value]
 

    def _token_count(self, text: str) -> int:
        """Tokenizer-accurate token count (no special tokens)."""
        return len(self.tokenizer.encode(text, add_special_tokens=False))
 
    def _clean_text(self, text: str) -> str:

        text = re.sub(
            r"\b(?:[a-zA-Z] ){1,}[a-zA-Z]\b",
            lambda m: m.group(0).replace(" ", ""),
            text,
        )
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)
        return text.strip()
 
    @staticmethod
    def _split_list(lst: list, size: int) -> list[list]:
        return [lst[i : i + size] for i in range(0, len(lst), size)]
 
    def _apply_overlap(self, chunks: list[str], overlap_size: int) -> list[str]:
        """Prepend the last ``overlap_size`` words of chunk N onto chunk N+1."""
        if overlap_size <= 0 or len(chunks) <= 1:
            return chunks
        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_words = chunks[i - 1].split()
            tail = prev_words[-overlap_size:] if len(prev_words) >= overlap_size else prev_words
            result.append(" ".join(tail + chunks[i].split()))
        return result
 

 
    def _fixed_chunking(self, text: str) -> list[str]:
        """Split by word count; chunk_size = max words per chunk."""
        words = text.split()
        if not words:
            return []
        size = settings.chunk_size
        return [" ".join(words[i : i + size]) for i in range(0, len(words), size)]
 
    def _sentence_wise_chunking(self, text: str) -> list[str]:

        if not text.strip():
            return []
        doc = self.nlp(text)
        sentences = [s.text.strip() for s in doc.sents if s.text.strip()]
 
        chunks: list[str] = []
        current: list[str] = []
        current_tokens = 0
 
        for sentence in sentences:
            t = self._token_count(sentence)
            sentence_limit_hit = len(current) >= settings.max_num_sentences
            token_limit_hit = current_tokens + t > settings.chunk_size
 
            if current and (sentence_limit_hit or token_limit_hit):
                chunks.append(" ".join(current))
                current = []
                current_tokens = 0
 
            current.append(sentence)
            current_tokens += t
 
        if current:
            chunks.append(" ".join(current))
        return chunks
 
    def _semantic_chunk_text(self, text: str) -> list[str]:
        sentences = nltk.sent_tokenize(text)
        if not sentences:
            return []
 
        embeddings = self.semantic_model.encode(sentences)
        chunks: list[str] = []
        current: list[str] = [sentences[0]]
        current_emb = embeddings[0]
        current_tokens = self._token_count(sentences[0])
 
        for i in range(1, len(sentences)):
            sim = cosine_similarity([current_emb], [embeddings[i]])[0][0]
            next_tokens = self._token_count(sentences[i])
 
            if sim >= settings.similarity_threshold and (current_tokens + next_tokens) <= settings.max_tokens:
                current.append(sentences[i])
                current_emb = (current_emb * (len(current) - 1) + embeddings[i]) / len(current)
                current_tokens += next_tokens
            else:
                chunks.append(" ".join(current))
                current = [sentences[i]]
                current_emb = embeddings[i]
                current_tokens = next_tokens
 
        if current:
            chunks.append(" ".join(current))
 
        
        merged: list[str] = []
        for chunk in chunks:
            if merged and self._token_count(chunk) < settings.min_chunk_size:
                merged[-1] += " " + chunk
            else:
                merged.append(chunk)
        return merged
 
    def _recursive_chunk_text(self, text: str) -> list[str]:
        """Recursively split on paragraph → line → sentence until within max_chunk_size tokens."""
 
        def _split(chunk: str, depth: int = 0) -> list[str]:
            if self._token_count(chunk) <= settings.chunk_size or depth >= settings.max_depth:
                return [chunk]
            for sep in ("\n\n", "\n"):
                parts = [p.strip() for p in chunk.split(sep) if p.strip()]
                if len(parts) > 1:
                    result: list[str] = []
                    for part in parts:
                        result.extend(_split(part, depth + 1))
                    return result
            # Sentence-level fallback
            sentences = nltk.sent_tokenize(chunk)
            groups: list[str] = []
            current_sents: list[str] = []
            current_tokens = 0
            for sentence in sentences:
                t = self._token_count(sentence)
                if current_tokens + t > settings.chunk_size and current_sents:
                    groups.append(" ".join(current_sents))
                    current_sents = [sentence]
                    current_tokens = t
                else:
                    current_sents.append(sentence)
                    current_tokens += t
            if current_sents:
                groups.append(" ".join(current_sents))
            return groups
 
        raw = _split(text)
        # Merge tiny trailing fragments into their predecessor
        merged: list[str] = []
        for chunk in raw:
            if merged and self._token_count(chunk) < settings.min_chunk_size:
                merged[-1] += " " + chunk
            else:
                merged.append(chunk)
        return merged
 
    def _hybrid_semantic_chunk_text(self, text: str) -> list[str]:
        """Semantic grouping first; recursive refinement for oversized chunks."""
        result: list[str] = []
        for chunk in self._semantic_chunk_text(text):
            if self._token_count(chunk) > settings.chunk_size:
                result.extend(self._recursive_chunk_text(chunk))
            else:
                result.append(chunk)
        return result
 

    def chunk(
        self,
        pages_and_text: list[dict],
        overlap_size: int = 0,
    ) -> list[ChunkResult]:
        
        _dispatch = {
            Strategy.FIXED:           self._fixed_chunking,
            Strategy.SENTENCE:        self._sentence_wise_chunking,
            Strategy.SEMANTIC:        self._semantic_chunk_text,
            Strategy.RECURSIVE:       self._recursive_chunk_text,
            Strategy.HYBRID_SEMANTIC: self._hybrid_semantic_chunk_text,
        }
 
        all_chunks: list[ChunkResult] = []
        chunk_counter = 0
 
        for page_idx, page in enumerate(pages_and_text):
            raw_text: str = page.get("text", "")
            if not raw_text.strip():
                continue
 
            text = self._clean_text(raw_text)
            page_number: int = page.get("page_number", page_idx)
            raw_chunks = _dispatch[self.strategy](text)
 
            if overlap_size > 0:
                raw_chunks = self._apply_overlap(raw_chunks, overlap_size)
 
            for chunk_text in raw_chunks:
                if not chunk_text.strip():
                    continue
                all_chunks.append(
                    ChunkResult(
                        chunk_id=chunk_counter,
                        content=chunk_text,
                        page=page_number,
                        strategy=self.strategy.value,
                        token_count=self._token_count(chunk_text),
                    )
                )
                chunk_counter += 1
 
        return all_chunks
 
