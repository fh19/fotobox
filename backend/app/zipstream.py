"""Streaming ZIP generator.

Builds a ZIP on the fly and yields it in chunks so the whole archive is never
held in memory (docs/api-contract.md, docs/meilensteine.md M4). Memory stays
roughly constant — one read buffer plus zip bookkeeping — no matter how many
photos are included. Stored (uncompressed): the JPEGs are already compressed.
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path

_CHUNK = 64 * 1024


class _DrainBuffer:
    """A minimal writable sink the ZipFile writes into; drained between yields."""

    def __init__(self) -> None:
        self._data = bytearray()

    def write(self, data: bytes) -> int:
        self._data.extend(data)
        return len(data)

    def flush(self) -> None:  # ZipFile calls flush()
        pass

    def drain(self) -> bytes:
        chunk = bytes(self._data)
        self._data.clear()
        return chunk


def stream_zip(entries: Iterable[tuple[str, Path]]) -> Iterator[bytes]:
    """Yield ZIP bytes for ``(arcname, path)`` entries, one small chunk at a time."""
    buffer = _DrainBuffer()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for arcname, path in entries:
            if not path.exists():
                continue
            # ZipInfo.from_file carries the file's mtime and mode into the archive.
            # Writing a bare arcname instead left every extracted photo dated
            # 1980-01-01 (zipfile's default) and readable only by its owner — the
            # timestamps looked like a broken clock on the box, but the box was fine.
            info = zipfile.ZipInfo.from_file(path, arcname)
            info.compress_type = zipfile.ZIP_STORED
            with archive.open(info, "w") as target, open(path, "rb") as source:
                while True:
                    block = source.read(_CHUNK)
                    if not block:
                        break
                    target.write(block)
                    drained = buffer.drain()
                    if drained:
                        yield drained
            drained = buffer.drain()
            if drained:
                yield drained
    # Central directory written on close.
    tail = buffer.drain()
    if tail:
        yield tail
