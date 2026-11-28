"""
Keeps the vector database identical on every PC / server, with no cloud and no commands.

  * After every indexing, export_snapshot() rewrites  backend/data/chroma_snapshot.npz
    (commit and push this file with git like any other file).
  * When the app starts, sync_on_startup() loads that file into local Chroma if the file is
    new or local Chroma has fewer papers. Merge only: nothing local is ever deleted.

Manual use is still possible (run from backend with PYTHONPATH=.):
    python -m app.vectorstore.snapshot_sync export | import | import --replace | info
"""
import hashlib
import json
import os
import sys
import threading
from collections import Counter
from pathlib import Path

import numpy as np

from app.vectorstore.chroma_client import _collection

SNAPSHOT = Path(os.environ.get("CHROMA_SNAPSHOT",
                               Path(__file__).resolve().parents[2] / "data" / "chroma_snapshot.npz"))
_MARKER = SNAPSHOT.with_name(".chroma_snapshot.sha256")   # local only, add to .gitignore
_BATCH = 500
_lock = threading.Lock()


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def export_snapshot(path: Path = SNAPSHOT) -> int:
    """Writes every paper in local Chroma to one file. Returns the paper count."""
    with _lock:
        data = _collection.get(include=["embeddings", "metadatas", "documents"])
        ids = data["ids"]
        if not ids:
            return 0
        metas = data["metadatas"] or [{} for _ in ids]
        docs = data["documents"] or [None for _ in ids]
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "wb") as f:                      # write whole file, then swap: never half-written
            np.savez_compressed(
                f,
                ids=np.array(ids, dtype=str),
                embeddings=np.asarray(data["embeddings"], dtype=np.float32),
                metadatas=np.array([json.dumps(m or {}) for m in metas], dtype=str),
                documents=np.array([json.dumps(d) for d in docs], dtype=str),
            )
        os.replace(tmp, path)
        _MARKER.write_text(_hash(path))                 # this PC already has what the file holds
        return len(ids)


def import_snapshot(path: Path = SNAPSHOT, replace: bool = False) -> int:
    """Loads the file into local Chroma (merge, or replace). Returns the paper count in the file."""
    with _lock:
        z = np.load(path, allow_pickle=False)
        ids = z["ids"].tolist()
        emb = z["embeddings"].astype(np.float32)
        metas = [json.loads(s) for s in z["metadatas"].tolist()]
        docs = [json.loads(s) for s in z["documents"].tolist()]
        if replace:
            old = _collection.get(include=[])["ids"]
            for i in range(0, len(old), _BATCH):
                _collection.delete(ids=old[i:i + _BATCH])
        for i in range(0, len(ids), _BATCH):
            kw = dict(ids=ids[i:i + _BATCH], embeddings=emb[i:i + _BATCH].tolist(),
                      metadatas=metas[i:i + _BATCH])
            d = docs[i:i + _BATCH]
            if any(x is not None for x in d):
                kw["documents"] = ["" if x is None else x for x in d]
            _collection.upsert(**kw)
        _MARKER.write_text(_hash(path))
        return len(ids)


def sync_on_startup() -> str:
    """Call once when the app starts. Never raises: a problem here must not stop the server."""
    try:
        if not SNAPSHOT.exists():
            return "no snapshot file found, nothing to load"
        same_file = _MARKER.exists() and _MARKER.read_text().strip() == _hash(SNAPSHOT)
        with np.load(SNAPSHOT, allow_pickle=False) as z:
            in_file = len(z["ids"])
        if same_file and _collection.count() >= in_file:
            return f"already up to date ({_collection.count()} papers)"
        n = import_snapshot()
        return f"loaded {n} papers from snapshot; local Chroma now has {_collection.count()}"
    except Exception as e:
        return f"snapshot load skipped: {e}"


def safe_export() -> None:
    """Call after indexing. Never raises: indexing already succeeded."""
    try:
        export_snapshot()
    except Exception as e:
        print(f"[snapshot] export failed: {e}")


def _info() -> None:
    def show(title, metas):
        c = Counter((m or {}).get("professor_name", "?") for m in metas)
        print(f"{title}: {len(metas)} papers, {len(c)} professors")
        for n, k in sorted(c.items()):
            print(f"    {n}: {k}")
    if SNAPSHOT.exists():
        z = np.load(SNAPSHOT, allow_pickle=False)
        show(f"FILE {SNAPSHOT}", [json.loads(s) for s in z["metadatas"].tolist()])
    else:
        print(f"FILE {SNAPSHOT}: not found")
    show("LOCAL CHROMA", _collection.get(include=["metadatas"])["metadatas"])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "export":
        print(f"Exported {export_snapshot()} papers to {SNAPSHOT}")
    elif cmd == "import":
        print(f"Imported {import_snapshot(replace='--replace' in sys.argv)} papers")
    elif cmd == "info":
        _info()
    else:
        sys.exit(__doc__)