"""Zotero read-only importer.

Zotero stores its library in ``~/Zotero/zotero.sqlite`` and the attachment
PDFs under ``~/Zotero/storage/<itemKey>/<filename>.pdf`` (or a custom
``dataDir``). We copy the SQLite file to a temp location to avoid the
desktop app's exclusive lock, read the items we care about, and resolve
each attachment to an absolute PDF path.

This module is **read-only**: we never write back into the user's Zotero
library. Paperflow merely imports a snapshot of the metadata + PDF.
"""

from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from shutil import copy2
from typing import Iterable, List, Optional

from app.models import ImportSourceType, PaperMetadata


DEFAULT_ZOTERO_DIR = Path.home() / "Zotero"
DEFAULT_DB_NAME = "zotero.sqlite"
DEFAULT_STORAGE_DIR = "storage"


# Item types that Paperflow treats as papers.
_PAPER_LIKE_TYPES = {
    "journalArticle",
    "conferencePaper",
    "preprint",
    "report",
    "thesis",
    "bookSection",
    "manuscript",
    "document",
}


class ZoteroError(Exception):
    """Raised when the Zotero library cannot be opened or read."""


@dataclass
class ZoteroItem:
    item_id: int
    item_key: str
    title: Optional[str]
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    abstract: Optional[str] = None
    pdf_path: Optional[Path] = None

    def to_metadata(self) -> PaperMetadata:
        return PaperMetadata(
            title=self.title,
            authors=list(self.authors),
            year=self.year,
            venue=self.venue,
            doi=self.doi.lower() if self.doi else None,
            arxiv_id=self.arxiv_id,
            source_type=ImportSourceType.ZOTERO,
            source_url=f"zotero://select/items/{self.item_key}",
            abstract=self.abstract,
        )


class ZoteroReader:
    """Read items + attachments from a local Zotero SQLite snapshot."""

    def __init__(
        self,
        zotero_dir: Optional[Path] = None,
        *,
        db_path: Optional[Path] = None,
        storage_dir: Optional[Path] = None,
    ) -> None:
        self.zotero_dir = Path(zotero_dir or DEFAULT_ZOTERO_DIR).expanduser()
        self.db_path = Path(db_path or (self.zotero_dir / DEFAULT_DB_NAME)).expanduser()
        self.storage_dir = Path(storage_dir or (self.zotero_dir / DEFAULT_STORAGE_DIR)).expanduser()

    # ------------------------------------------------------------------ public

    def is_available(self) -> bool:
        return self.db_path.is_file() and self.storage_dir.is_dir()

    def list_items(self, *, limit: Optional[int] = None) -> List[ZoteroItem]:
        """Return paper-like items with their attached PDF resolved."""

        if not self.db_path.is_file():
            raise ZoteroError(f"Zotero database not found: {self.db_path}")

        with self._open() as conn:
            item_rows = conn.execute(
                """
                select i.itemID, i.key, it.typeName
                from items i
                join itemTypes it on it.itemTypeID = i.itemTypeID
                left join deletedItems d on d.itemID = i.itemID
                where d.itemID is null
                """
            ).fetchall()

            items: List[ZoteroItem] = []
            for row in item_rows:
                if row["typeName"] not in _PAPER_LIKE_TYPES:
                    continue
                item = self._hydrate_item(conn, row["itemID"], row["key"])
                if item is not None and item.pdf_path is not None:
                    items.append(item)
                if limit is not None and len(items) >= limit:
                    break

        items.sort(key=lambda i: (i.year or 0, (i.title or "")), reverse=True)
        return items

    # ------------------------------------------------------------------ private

    def _open(self) -> sqlite3.Connection:
        """Open a read-only copy of the Zotero DB.

        Zotero locks the live ``zotero.sqlite`` while the app is running.
        We copy the file to a tempdir before opening so the user does not have
        to quit Zotero to use the importer.
        """

        tmp = Path(tempfile.gettempdir()) / "paperflow-zotero-snapshot.sqlite"
        try:
            copy2(self.db_path, tmp)
        except OSError as exc:
            raise ZoteroError(f"Could not snapshot Zotero DB: {exc}") from exc

        conn = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _hydrate_item(self, conn: sqlite3.Connection, item_id: int, item_key: str) -> Optional[ZoteroItem]:
        fields = self._item_fields(conn, item_id)
        item = ZoteroItem(
            item_id=item_id,
            item_key=item_key,
            title=fields.get("title"),
        )

        publication = fields.get("publicationTitle") or fields.get("conferenceName")
        item.venue = publication
        item.doi = (fields.get("DOI") or "").lower() or None
        item.abstract = fields.get("abstractNote")

        date_str = fields.get("date") or ""
        for token in date_str.split():
            if len(token) >= 4 and token[:4].isdigit():
                item.year = int(token[:4])
                break

        # arXiv id is sometimes stored in the extra field or the URL.
        extra = fields.get("extra") or ""
        url = fields.get("url") or ""
        item.arxiv_id = _arxiv_id_from_strings(extra, url)

        # Creators / authors.
        author_rows = conn.execute(
            """
            select c.firstName, c.lastName
            from itemCreators ic
            join creators c on c.creatorID = ic.creatorID
            join creatorTypes ct on ct.creatorTypeID = ic.creatorTypeID
            where ic.itemID = ? and ct.creatorType = 'author'
            order by ic.orderIndex
            """,
            (item_id,),
        ).fetchall()
        item.authors = [
            " ".join(part for part in [r["firstName"], r["lastName"]] if part)
            for r in author_rows
            if r["firstName"] or r["lastName"]
        ]

        # Attached PDF: child item of type ``attachment`` whose path resolves.
        pdf_row = conn.execute(
            """
            select ia.path, child.key
            from itemAttachments ia
            join items child on child.itemID = ia.itemID
            left join deletedItems d on d.itemID = child.itemID
            where ia.parentItemID = ?
              and (ia.contentType = 'application/pdf' or ia.path like '%.pdf')
              and d.itemID is null
            order by ia.itemID
            """,
            (item_id,),
        ).fetchone()

        if pdf_row is not None:
            item.pdf_path = self._resolve_attachment_path(pdf_row["path"], pdf_row["key"])

        return item

    def _item_fields(self, conn: sqlite3.Connection, item_id: int) -> dict:
        rows = conn.execute(
            """
            select f.fieldName, idv.value
            from itemData id
            join fields f on f.fieldID = id.fieldID
            join itemDataValues idv on idv.valueID = id.valueID
            where id.itemID = ?
            """,
            (item_id,),
        ).fetchall()
        return {row["fieldName"]: row["value"] for row in rows}

    def _resolve_attachment_path(self, raw_path: Optional[str], child_key: str) -> Optional[Path]:
        if not raw_path:
            return None
        # Linked file paths are absolute (`attachments:` prefix removed).
        if raw_path.startswith("storage:"):
            relative = raw_path[len("storage:") :]
            candidate = self.storage_dir / child_key / relative
        elif raw_path.startswith("attachments:"):
            relative = raw_path[len("attachments:") :]
            candidate = self.storage_dir / child_key / relative
        else:
            candidate = Path(raw_path).expanduser()
        return candidate if candidate.is_file() else None


# ---------------------------------------------------------------- helpers


def _arxiv_id_from_strings(*strings: str) -> Optional[str]:
    import re

    pattern = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?", re.IGNORECASE)
    for s in strings:
        if not s:
            continue
        m = pattern.search(s)
        if m:
            return m.group(0)
    return None


def to_metadata_list(items: Iterable[ZoteroItem]) -> List[PaperMetadata]:
    return [item.to_metadata() for item in items]
