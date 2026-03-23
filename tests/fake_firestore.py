"""
Minimal in-memory Firestore for API integration tests.
Supports paths, where (==, array_contains), order_by, limit, stream/get,
set/update/delete, and ArrayRemove transforms.
"""
from __future__ import annotations

from dataclasses import dataclass, field
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
        return FakeDocumentReference(self._store, self._path)

    def to_dict(self) -> Optional[dict]:
        if not self.exists:
            return None
        data = self._store._docs.get(self._path)
        return dict(data) if data is not None else None


class FakeDocumentReference:
    def __init__(self, store: "InMemoryFirestore", path: str) -> None:
        self._store = store
        self._path = path
        self.id = path.rsplit("/", 1)[-1]

    def collection(self, name: str) -> "FakeCollectionReference":
        return FakeCollectionReference(self._store, f"{self._path}/{name}")

    def get(self) -> FakeSnapshot:
        data = self._store._docs.get(self._path)
        exists = data is not None
        return FakeSnapshot(self.id, self._path, self._store, exists=exists)

    def set(self, data: dict, merge: bool = False) -> None:
        if merge and self._path in self._store._docs:
            merged = {**self._store._docs[self._path], **data}
            self._store._docs[self._path] = merged
        else:
            self._store._docs[self._path] = dict(data)

    def update(self, data: dict) -> None:
        if self._path not in self._store._docs:
            raise KeyError(f"No document at {self._path}")
        doc = dict(self._store._docs[self._path])
        for k, v in data.items():
            if isinstance(v, ArrayRemove):
                arr = list(doc.get(k, []))
                for x in v.values:
                    arr = [y for y in arr if y != x]
                doc[k] = arr
            else:
                doc[k] = v
        self._store._docs[self._path] = doc

    def delete(self) -> None:
        self._store._docs.pop(self._path, None)


class FakeCollectionReference:
    def __init__(self, store: "InMemoryFirestore", collection_path: str) -> None:
        self._store = store
        self._collection_path = collection_path

    def document(self, doc_id: str) -> FakeDocumentReference:
        path = f"{self._collection_path}/{doc_id}"
        return FakeDocumentReference(self._store, path)

    def _iter_direct_snapshots(self) -> List[FakeSnapshot]:
        prefix = self._collection_path + "/"
        out: List[FakeSnapshot] = []
        for key in sorted(self._store._docs.keys()):
            if not key.startswith(prefix):
                continue
            rest = key[len(prefix) :]
            if "/" in rest:
                continue
            out.append(FakeSnapshot(rest, key, self._store, exists=True))
        return out

    def stream(self) -> Iterator[FakeSnapshot]:
        yield from self._iter_direct_snapshots()

    def where(self, field: str, op: str, value: Any) -> "FakeQuery":
        return FakeQuery(self._store, self._collection_path, [(field, op, value)])

    def order_by(self, field: str, direction: Optional[str] = None) -> "FakeQuery":
        return FakeQuery(
            self._store,
            self._collection_path,
            [],
            order_field=field,
            order_direction=direction,
        )


@dataclass
class FakeQuery:
    _store: "InMemoryFirestore"
    _collection_path: str
    filters: List[Filter] = field(default_factory=list)
    order_field: Optional[str] = None
    order_direction: Optional[str] = None
    limit_n: Optional[int] = None

    def where(self, field: str, op: str, value: Any) -> "FakeQuery":
        return FakeQuery(
            self._store,
            self._collection_path,
            self.filters + [(field, op, value)],
            self.order_field,
            self.order_direction,
            self.limit_n,
        )

    def order_by(self, field: str, direction: Optional[str] = None) -> "FakeQuery":
        return FakeQuery(
            self._store,
            self._collection_path,
            self.filters,
            order_field=field,
            order_direction=direction,
        )

    def limit(self, n: int) -> "FakeQuery":
        return FakeQuery(
            self._store,
            self._collection_path,
            self.filters,
            self.order_field,
            self.order_direction,
            n,
        )

    def stream(self) -> Iterator[FakeSnapshot]:
        coll = FakeCollectionReference(self._store, self._collection_path)
        snaps = [s for s in coll._iter_direct_snapshots() if _doc_matches_filters(s.to_dict() or {}, self.filters)]
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
        return list(self.stream())


class InMemoryFirestore:
    """Drop-in-ish client() return value for tests."""

    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}

    def collection(self, name: str) -> FakeCollectionReference:
        return FakeCollectionReference(self, name)

    def clear(self) -> None:
        self._docs.clear()
