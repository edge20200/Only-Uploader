"""
Staleness checks for the cached BASE.torrent.

A BASE.torrent left in tmp/<uuid>/ is reused on later runs so the content does not
have to be hashed again. If the content changed after that torrent was created
(a re-encode, a remux, a repair) the cached piece hashes no longer describe it, and
uploading it publishes a torrent that cannot verify a single piece. Clients with an
incomplete directory react to that by moving the real file out of its seeding
location, so a stale cache can cost the user the file they were seeding.

Detecting this does not require re-hashing, which is the whole point of the cache.
Two cheap signals are enough:

  * file sizes - a re-encode almost always changes the total size,
  * modification times - content newer than the torrent changed after it was made.

At creation time `write_cache_sidecar` records the exact files that went into the
torrent next to it. When that sidecar is absent (a cache created before this existed,
or a torrent reused from the client) the expected sizes are read back out of the
.torrent itself instead.

Nothing here reads content bytes, so the check stays cheap on multi-GB releases.
"""

import json
import os
from typing import NamedTuple, Optional

SIDECAR_SUFFIX = ".cache.json"
SIDECAR_VERSION = 1

# Timestamps are coarse on some filesystems (FAT, some SMB shares), so allow a
# small amount of slack before calling content "newer than the torrent".
MTIME_TOLERANCE = 2.0

STALE_ACTIONS = ("rehash", "abort")


class CacheStatus(NamedTuple):
    fresh: bool
    reason: Optional[str]
    # Where the expectations came from: 'sidecar', 'torrent', or 'unknown'.
    source: str


class _ExpectedFile(NamedTuple):
    path: str
    label: str
    size: int
    mtime: Optional[float]


def sidecar_path(torrent_path):
    """Path of the metadata sidecar belonging to a .torrent."""
    return f"{torrent_path}{SIDECAR_SUFFIX}"


def content_base(content_path):
    """Directory that recorded paths are stored relative to."""
    path = os.path.abspath(str(content_path))
    return path if os.path.isdir(path) else os.path.dirname(path)


def write_cache_sidecar(torrent_path, content_path, filepaths):
    """Record the size and mtime of every file that went into `torrent_path`."""
    base = content_base(content_path)
    files, total_size, newest_mtime = [], 0, 0.0

    for filepath in filepaths:
        filepath = os.path.abspath(str(filepath))
        stat = os.stat(filepath)
        files.append({
            "path": os.path.relpath(filepath, base).replace(os.sep, "/"),
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        })
        total_size += stat.st_size
        newest_mtime = max(newest_mtime, stat.st_mtime)

    payload = {
        "version": SIDECAR_VERSION,
        "content_path": os.path.abspath(str(content_path)),
        "total_size": total_size,
        "newest_mtime": newest_mtime,
        "files": files,
    }

    destination = sidecar_path(torrent_path)
    with open(destination, "w") as handle:
        json.dump(payload, handle, indent=2)
    return destination


def clear_cache_sidecar(torrent_path):
    """Drop a sidecar that no longer belongs to the .torrent sitting next to it."""
    try:
        os.remove(sidecar_path(torrent_path))
    except OSError:
        pass


def validate_cached_torrent(torrent_path, content_path, mtime_tolerance=MTIME_TOLERANCE):
    """Check a cached .torrent against the content on disk without re-hashing."""
    if not os.path.exists(torrent_path):
        return CacheStatus(False, "the cached torrent no longer exists", "unknown")

    try:
        torrent_mtime = os.path.getmtime(torrent_path)
        expected, source = _expected_files(torrent_path, content_path)
    except (OSError, ValueError) as error:
        return CacheStatus(False, f"the cached torrent could not be read ({error})", "unknown")

    if not expected:
        return CacheStatus(False, "the cached torrent lists no files", source)

    for entry in expected:
        if not os.path.isfile(entry.path):
            return CacheStatus(False, f"missing content file: {entry.label}", source)

        stat = os.stat(entry.path)
        if stat.st_size != entry.size:
            return CacheStatus(
                False,
                f"size mismatch for {entry.label}: torrent expects {entry.size} bytes, "
                f"disk has {stat.st_size} bytes",
                source,
            )

        changed = stat.st_mtime > torrent_mtime + mtime_tolerance
        if entry.mtime is not None:
            changed = changed or abs(stat.st_mtime - entry.mtime) > mtime_tolerance
        if changed:
            return CacheStatus(False, f"content modified after the torrent was created: {entry.label}", source)

    return CacheStatus(True, None, source)


def resolve_stale_action(configured, can_rehash=True):
    """Decide what to do about a stale cache: 'rehash' (default) or 'abort'."""
    if not can_rehash:
        return "abort"
    action = str(configured or "rehash").strip().lower()
    return action if action in STALE_ACTIONS else "rehash"


def _expected_files(torrent_path, content_path):
    recorded = _read_sidecar(torrent_path)
    if recorded is not None:
        base = content_base(content_path)
        expected = [
            _ExpectedFile(
                path=os.path.join(base, *entry["path"].split("/")),
                label=entry["path"],
                size=int(entry["size"]),
                mtime=entry.get("mtime"),
            )
            for entry in recorded.get("files", [])
        ]
        return expected, "sidecar"
    return _files_from_torrent(torrent_path, content_path), "torrent"


def _read_sidecar(torrent_path):
    try:
        with open(sidecar_path(torrent_path)) as handle:
            recorded = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(recorded, dict) or recorded.get("version") != SIDECAR_VERSION:
        return None
    return recorded


def _files_from_torrent(torrent_path, content_path):
    """Derive the expected files from the .torrent itself, for caches without a sidecar."""
    with open(torrent_path, "rb") as handle:
        metainfo, _ = _bdecode(handle.read(), 0)

    info = metainfo[b"info"]
    name = info[b"name"].decode("utf-8", "replace")
    base = _torrent_base(content_path, name)

    if b"files" not in info:
        return [_ExpectedFile(os.path.join(base, name), name, int(info[b"length"]), None)]

    expected = []
    for entry in info[b"files"]:
        parts = [part.decode("utf-8", "replace") for part in entry[b"path"]]
        expected.append(_ExpectedFile(
            path=os.path.join(base, name, *parts),
            label="/".join(parts),
            size=int(entry[b"length"]),
            mtime=None,
        ))
    return expected


def _torrent_base(content_path, torrent_name):
    """Directory the torrent's top level entry sits in, given the content path."""
    path = os.path.abspath(str(content_path))
    if os.path.basename(path) == torrent_name:
        return os.path.dirname(path)
    return path if os.path.isdir(path) else os.path.dirname(path)


def _bdecode(data, pos):
    """Minimal bencode reader - just enough to pull file names and lengths out."""
    prefix = data[pos:pos + 1]

    if prefix == b"i":
        end = data.index(b"e", pos)
        return int(data[pos + 1:end]), end + 1

    if prefix == b"l":
        items, pos = [], pos + 1
        while data[pos:pos + 1] != b"e":
            item, pos = _bdecode(data, pos)
            items.append(item)
        return items, pos + 1

    if prefix == b"d":
        mapping, pos = {}, pos + 1
        while data[pos:pos + 1] != b"e":
            key, pos = _bdecode(data, pos)
            value, pos = _bdecode(data, pos)
            mapping[key] = value
        return mapping, pos + 1

    if prefix.isdigit():
        separator = data.index(b":", pos)
        start = separator + 1
        end = start + int(data[pos:separator])
        if end > len(data):
            raise ValueError("truncated string")
        return data[start:end], end

    raise ValueError(f"unexpected byte at offset {pos}")
