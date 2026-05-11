"""Tests for the Zotero read-only importer.

We fabricate a minimal Zotero SQLite schema and a storage layout so the
importer can run without a real Zotero install.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.models import ImportSourceType
from app.zotero import ZoteroError, ZoteroReader


_ITEMS_SCHEMA = """
create table itemTypes (itemTypeID integer primary key, typeName text);
create table items (
    itemID integer primary key,
    key text not null,
    itemTypeID integer not null
);
create table deletedItems (itemID integer primary key);
create table fields (fieldID integer primary key, fieldName text);
create table itemDataValues (valueID integer primary key, value text);
create table itemData (itemID integer, fieldID integer, valueID integer);
create table creators (creatorID integer primary key, firstName text, lastName text);
create table creatorTypes (creatorTypeID integer primary key, creatorType text);
create table itemCreators (
    itemID integer, creatorID integer, creatorTypeID integer, orderIndex integer
);
create table itemAttachments (
    itemID integer,
    parentItemID integer,
    contentType text,
    path text
);
"""


def _build_zotero_dir(root: Path) -> Path:
    storage = root / "storage"
    storage.mkdir(parents=True)
    db_path = root / "zotero.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(_ITEMS_SCHEMA)

    # Item types.
    conn.execute("insert into itemTypes (itemTypeID, typeName) values (1, 'journalArticle')")
    conn.execute("insert into itemTypes (itemTypeID, typeName) values (2, 'attachment')")
    conn.execute("insert into itemTypes (itemTypeID, typeName) values (3, 'note')")

    # Fields.
    fields = ["title", "publicationTitle", "date", "DOI", "url", "abstractNote", "extra"]
    for fid, name in enumerate(fields, start=1):
        conn.execute("insert into fields (fieldID, fieldName) values (?, ?)", (fid, name))

    # Creator types.
    conn.execute("insert into creatorTypes (creatorTypeID, creatorType) values (1, 'author')")

    # Parent paper item.
    conn.execute("insert into items (itemID, key, itemTypeID) values (10, 'PAPERKEY', 1)")

    def _add_field(item_id: int, field_name: str, value: str) -> None:
        fid = fields.index(field_name) + 1
        cursor = conn.execute(
            "select valueID from itemDataValues where value = ?", (value,)
        ).fetchone()
        if cursor is None:
            conn.execute("insert into itemDataValues (value) values (?)", (value,))
            vid = conn.execute("select last_insert_rowid()").fetchone()[0]
        else:
            vid = cursor[0]
        conn.execute(
            "insert into itemData (itemID, fieldID, valueID) values (?, ?, ?)",
            (item_id, fid, vid),
        )

    _add_field(10, "title", "Zotero Paper Title")
    _add_field(10, "publicationTitle", "Journal of Local-First Reading")
    _add_field(10, "date", "2024-06-15")
    _add_field(10, "DOI", "10.5555/zotero.paper.1")
    _add_field(10, "url", "https://arxiv.org/abs/2401.99999")
    _add_field(10, "abstractNote", "A test paper for the Zotero importer.")
    _add_field(10, "extra", "")

    # Authors.
    conn.execute("insert into creators (firstName, lastName) values ('Alice', 'Liu')")
    conn.execute("insert into creators (firstName, lastName) values ('Bob', 'Chen')")
    alice = conn.execute("select last_insert_rowid()").fetchone()[0] - 0  # Bob
    bob = alice
    # Recompute properly.
    alice = conn.execute(
        "select creatorID from creators where lastName = 'Liu'"
    ).fetchone()[0]
    bob = conn.execute(
        "select creatorID from creators where lastName = 'Chen'"
    ).fetchone()[0]
    conn.execute(
        "insert into itemCreators (itemID, creatorID, creatorTypeID, orderIndex) values (10, ?, 1, 0)",
        (alice,),
    )
    conn.execute(
        "insert into itemCreators (itemID, creatorID, creatorTypeID, orderIndex) values (10, ?, 1, 1)",
        (bob,),
    )

    # Attachment item.
    conn.execute("insert into items (itemID, key, itemTypeID) values (11, 'ATTACHKEY', 2)")
    pdf_dir = storage / "ATTACHKEY"
    pdf_dir.mkdir(parents=True)
    pdf_path = pdf_dir / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nhello")
    conn.execute(
        """
        insert into itemAttachments (itemID, parentItemID, contentType, path)
        values (11, 10, 'application/pdf', 'storage:paper.pdf')
        """
    )

    # Add a deleted item to make sure we ignore it.
    conn.execute("insert into items (itemID, key, itemTypeID) values (20, 'GONE', 1)")
    conn.execute("insert into deletedItems (itemID) values (20)")

    conn.commit()
    conn.close()
    return root


def test_zotero_reader_returns_paper_items_with_pdf_attachment(tmp_path: Path) -> None:
    zdir = _build_zotero_dir(tmp_path / "Zotero")
    reader = ZoteroReader(zotero_dir=zdir)
    assert reader.is_available()

    items = reader.list_items()
    assert len(items) == 1
    only = items[0]
    assert only.title == "Zotero Paper Title"
    assert only.authors == ["Alice Liu", "Bob Chen"]
    assert only.year == 2024
    assert only.venue == "Journal of Local-First Reading"
    assert only.doi == "10.5555/zotero.paper.1"
    assert only.arxiv_id == "2401.99999"
    assert only.pdf_path is not None and only.pdf_path.is_file()

    meta = only.to_metadata()
    assert meta.source_type is ImportSourceType.ZOTERO
    assert meta.title == "Zotero Paper Title"


def test_zotero_reader_handles_missing_db(tmp_path: Path) -> None:
    reader = ZoteroReader(zotero_dir=tmp_path / "no-zotero")
    assert not reader.is_available()
    with pytest.raises(ZoteroError):
        reader.list_items()
