"""
CLI batch ingestion tool for PageIndex Knowledge Base.
Usage:
    python scripts/ingest.py --file path/to/document.pdf
    python scripts/ingest.py --dir path/to/documents/
"""
import argparse
import asyncio
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from core.database import SessionLocal
from core.config import settings
from models.document import Document, DocumentStatus
from services.ingestion import run_ingestion_task


ALLOWED_EXT = set(settings.ALLOWED_EXTENSIONS)


async def ingest_file(filepath: str, category: str = None):
    filename = os.path.basename(filepath)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ALLOWED_EXT:
        print(f"  Skip (unsupported type): {filename}")
        return

    with open(filepath, "rb") as f:
        file_data = f.read()

    checksum = hashlib.sha256(file_data).hexdigest()

    db = SessionLocal()
    try:
        existing = db.query(Document).filter(Document.checksum == checksum).first()
        if existing:
            print(f"  Skip (duplicate): {filename}")
            return

        doc = Document(
            title=filename,
            file_type=ext,
            file_size=len(file_data),
            category=category,
            status=DocumentStatus.UPLOADING,
            checksum=checksum,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        print(f"  Processing: {filename} (id={doc.id})")
        await run_ingestion_task(doc.id, file_data, filename, ext)
        print(f"  Done: {filename}")
    finally:
        db.close()


async def main():
    parser = argparse.ArgumentParser(description="PageIndex Knowledge Base Ingestion Tool")
    parser.add_argument("--file", help="Single file to ingest")
    parser.add_argument("--dir", help="Directory to ingest recursively")
    parser.add_argument("--category", default=None, help="Category label")
    args = parser.parse_args()

    if not args.file and not args.dir:
        parser.print_help()
        sys.exit(1)

    if args.file:
        await ingest_file(args.file, args.category)

    if args.dir:
        for root, dirs, files in os.walk(args.dir):
            for fname in sorted(files):
                fpath = os.path.join(root, fname)
                await ingest_file(fpath, args.category)

    print("\nIngestion complete.")


if __name__ == "__main__":
    asyncio.run(main())
