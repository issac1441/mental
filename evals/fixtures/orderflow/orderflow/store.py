"""In-memory versioned store with optimistic concurrency.

Every record carries a version. Writers must present the version they read;
a mismatch raises VersionConflict, which is retryable by design — callers
re-read and re-apply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import VersionConflict


@dataclass
class Record:
    value: Any
    version: int = 1


@dataclass
class VersionedStore:
    _records: dict[str, Record] = field(default_factory=dict)

    def get(self, key: str) -> Record | None:
        return self._records.get(key)

    def put(self, key: str, value: Any, expected_version: int | None) -> Record:
        """Write ``value`` under ``key``.

        ``expected_version`` must match the stored version (or be ``None``
        for a brand-new key), otherwise VersionConflict is raised.
        """
        current = self._records.get(key)
        if current is None:
            if expected_version is not None:
                raise VersionConflict(f"{key}: record vanished")
            record = Record(value=value, version=1)
        else:
            if expected_version != current.version:
                raise VersionConflict(
                    f"{key}: expected v{expected_version}, found v{current.version}"
                )
            record = Record(value=value, version=current.version + 1)
        self._records[key] = record
        return record

    def delete(self, key: str) -> None:
        self._records.pop(key, None)
