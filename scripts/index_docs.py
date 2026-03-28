#!/usr/bin/env python3
"""
Document indexing pipeline.

Usage:
    python scripts/index_docs.py --source ./docs --glob "**/*.md"
    python scripts/index_docs.py --source ./docs --glob "**/*.txt" --chunk-size 512

Recursively reads files, splits them into overlapping chunks,
embeds them with OpenAI, and upserts into pgvector.
"""

import asyncio
import argparse
import sys
import os
import re
from pathlib import Path
from typing import List, Iterator

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_openai import OpenAIEmbeddings
from app.config import settings
from app.db.pgvector import get_pool, ensure_schema


# ---------------------------------------------------------------------------
# Text splitter (no external dep — simple overlap chunker)
# ---------------------------------------------------------------------------

def chunk_text(text: str, size: int = 512, overlap: int = 64) -> List[str]:
    """Split text into overlapping chunks by word boundary."""
    words = text.split()
    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        chunks.append(" ".join(words[start:end]))
        start += size - overlap
    return [c for c in chunks if len(c.strip()) > 20]


def iter_files(source: str, glob: str) -> Iterator[Path]:
    root = Path(source)
    if not root.exists():
        raise FileNotFoundError(f"Source directory not found: {source}")
    yield from root.glob(glob)


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

async def index_file(path: Path, embedder: OpenAIEmbeddings, pool, chunk_size: int, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8", errors="ignore")
    # Strip markdown syntax for cleaner embeddings
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"[#*`>\[\]]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return 0

    chunks = chunk_text(text, size=chunk_size)
    source = str(path)

    if dry_run:
        print(f"  [dry-run] {source}: {len(chunks)} chunks (not written)")
        return len(chunks)

    embeddings = await embedder.aembed_documents(chunks)

    async with pool.acquire() as conn:
        # Deduplicate by source: remove old chunks for this file first
        await conn.execute("DELETE FROM doc_chunks WHERE source = $1;", source)

        for chunk_text_val, embedding in zip(chunks, embeddings):
            vector_literal = "[" + ",".join(str(v) for v in embedding) + "]"
            await conn.execute(
                "INSERT INTO doc_chunks (source, chunk_text, embedding) VALUES ($1, $2, $3::vector);",
                source,
                chunk_text_val,
                vector_literal,
            )

    return len(chunks)


async def main(args: argparse.Namespace) -> None:
    print(f"Indexing: source={args.source!r} glob={args.glob!r} chunk-size={args.chunk_size}")

    await ensure_schema()
    pool = await get_pool()

    embedder = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )

    files = list(iter_files(args.source, args.glob))
    if not files:
        print("No files matched. Done.")
        return

    total_chunks = 0
    for i, path in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {path} ...", end=" ", flush=True)
        try:
            n = await index_file(path, embedder, pool, args.chunk_size, args.dry_run)
            print(f"{n} chunks")
            total_chunks += n
        except Exception as exc:
            print(f"ERROR: {exc}")

    print(f"\nDone. Indexed {total_chunks} chunks from {len(files)} files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index documents into pgvector")
    parser.add_argument("--source", default="./docs", help="Root directory of documents")
    parser.add_argument("--glob", default="**/*.md", help="Glob pattern relative to source")
    parser.add_argument("--chunk-size", type=int, default=512, help="Words per chunk")
    parser.add_argument("--dry-run", action="store_true", help="Parse but do not write to DB")
    asyncio.run(main(parser.parse_args()))
