"""
Minimal in-memory Firestore for API integration tests.
Supports paths, where (==, array_contains), order_by, limit, stream/get,
set/update/delete, and ArrayRemove transforms.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Any, Iterator, List, Optional, Tuple

from google.cloud.firestore import ArrayRemove
from google.cloud.firestore import Query as FirestoreQuery


Filter = Tuple[str, str, Any]


def _doc_matches_filters(data: dict, filters: List[Filter]) -> bool:
    for fld, op, val in filters:
        if op == "==":
            if data.get(fld) != val:
                return False
        elif op == "array_contains":
            arr = data.get(fld, [])
            if not isinstance(arr, list) or val not in arr:
                return False
        else:
            raise NotImplementedError(f"Unsupported where op: {op}")
    return True


@dataclass
class FakeSnapshot:
    """Document snapshot compatible with google-cloud-firestore usage in Antify."""

    id: str
    _path: str
    _store: "InMemoryFirestore"
    exists: bool = True

    @property
    def reference(self) -> "FakeDocumentReference":
        """Get the document reference"""
        return FakeDocumentReference(self._store, self._path)

    def to_dict(self) -> Optional[dict]:
        """Convert the snapshot to a dictionary"""
        if not self.exists:
            return None
        data = self._store.get_doc(self._path)
        return dict(data) if data is not None else None


class FakeDocumentReference:
    """Document reference compatible with google-cloud-firestore usage in Antify."""
    def __init__(self, store: "InMemoryFirestore", path: str) -> None:
        self._store = store
        self._path = path
        self.id = path.rsplit("/", 1)[-1]

    def collection(self, name: str) -> "FakeCollectionReference":
        """Get a collection reference"""
        return FakeCollectionReference(self._store, f"{self._path}/{name}")

    def get(self) -> FakeSnapshot:
        """Get the document snapshot"""
        data = self._store.get_doc(self._path)
        exists = data is not None
        return FakeSnapshot(self.id, self._path, self._store, exists=exists)

    def set(self, data: dict, merge: bool = False) -> None:
        """Set the document data"""
        existing = self._store.get_doc(self._path)
        if merge and existing is not None:
            merged = {**existing, **data}
            self._store.set_doc(self._path, merged)
        else:
            self._store.set_doc(self._path, dict(data))

    def update(self, data: dict) -> None:
        """Update the document data"""
        if not self._store.has_doc(self._path):
            raise KeyError(f"No document at {self._path}")
        doc = dict(self._store.get_doc(self._path) or {})
        for k, v in data.items():
            if isinstance(v, ArrayRemove):
                arr = list(doc.get(k, []))
                for x in v.values:
                    arr = [y for y in arr if y != x]
                doc[k] = arr
            else:
                doc[k] = v
        self._store.set_doc(self._path, doc)

    def delete(self) -> None:
        """Delete the document"""
        self._store.delete_doc(self._path)


class FakeCollectionReference:
    """Collection reference compatible with google-cloud-firestore usage in Antify."""
    def __init__(self, store: "InMemoryFirestore", collection_path: str) -> None:
        self._store = store
        self._collection_path = collection_path

    def document(self, doc_id: str) -> FakeDocumentReference:
        """Get a document reference"""
        path = f"{self._collection_path}/{doc_id}"
        return FakeDocumentReference(self._store, path)

    def iter_direct_snapshots(self) -> List[FakeSnapshot]:
        """Iterate over the direct snapshots"""
        prefix = self._collection_path + "/"
        out: List[FakeSnapshot] = []
        for key in sorted(self._store.doc_keys()):
            if not key.startswith(prefix):
                continue
            rest = key[len(prefix) :]
            if "/" in rest:
                continue
            out.append(FakeSnapshot(rest, key, self._store, exists=True))
        return out

    def stream(self) -> Iterator[FakeSnapshot]:
        """Stream the documents"""
        yield from self.iter_direct_snapshots()

    def where(self, field: str, op: str, value: Any) -> "FakeQuery":
        """Where the documents"""
        return FakeQuery(self._store, self._collection_path, [(field, op, value)])

    def order_by(self, field: str, direction: Optional[str] = None) -> "FakeQuery":
        """Order the documents"""
        return FakeQuery(
            self._store,
            self._collection_path,
            [],
            order_field=field,
            order_direction=direction,
        )


@dataclass
class FakeQuery:
    """Query the documents"""
    _store: "InMemoryFirestore"
    _collection_path: str
    filters: List[Filter] = dataclass_field(default_factory=list)
    order_field: Optional[str] = None
    order_direction: Optional[str] = None
    limit_n: Optional[int] = None

    def where(self, field_name: str, op: str, value: Any) -> "FakeQuery":
        """Where the documents"""
        return FakeQuery(
            self._store,
            self._collection_path,
            self.filters + [(field_name, op, value)],
            self.order_field,
            self.order_direction,
            self.limit_n,
        )

    def order_by(self, field_name: str, direction: Optional[str] = None) -> "FakeQuery":
        """Order the documents"""
        return FakeQuery(
            self._store,
            self._collection_path,
            self.filters,
            order_field=field_name,
            order_direction=direction,
        )

    def limit(self, n: int) -> "FakeQuery":
        """Limit the number of documents"""
        return FakeQuery(
            self._store,
            self._collection_path,
            self.filters,
            self.order_field,
            self.order_direction,
            n,
        )

    def stream(self) -> Iterator[FakeSnapshot]:
        """Stream the documents"""
        coll = FakeCollectionReference(self._store, self._collection_path)
        snaps = [s for s in coll.iter_direct_snapshots()
                 if _doc_matches_filters(s.to_dict() or {}, self.filters)]
        if self.order_field:
            reverse = self.order_direction == FirestoreQuery.DESCENDING

            def sort_key(s: FakeSnapshot) -> Any:
                d = s.to_dict() or {}
                v = d.get(self.order_field)
                return v

            snaps.sort(key=sort_key, reverse=reverse)
        if self.limit_n is not None:
            snaps = snaps[: self.limit_n]
        yield from snaps

    def get(self) -> List[FakeSnapshot]:
        """Get the documents"""
        return list(self.stream())


class InMemoryFirestore:
    """Drop-in-ish client() return value for tests."""

    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}

    def get_doc(self, path: str) -> Optional[dict]:
        """Get a document by path."""
        return self._docs.get(path)

    def has_doc(self, path: str) -> bool:
        """Check whether a document exists by path."""
        return path in self._docs

    def set_doc(self, path: str, data: dict) -> None:
        """Set a document by path."""
        self._docs[path] = dict(data)

    def delete_doc(self, path: str) -> None:
        """Delete a document by path."""
        self._docs.pop(path, None)

    def doc_keys(self) -> list[str]:
        """Return all document keys."""
        return list(self._docs.keys())

    def collection(self, name: str) -> FakeCollectionReference:
        """Get a collection reference"""
        return FakeCollectionReference(self, name)

    def clear(self) -> None:
        """Clear the documents"""
        self._docs.clear()
