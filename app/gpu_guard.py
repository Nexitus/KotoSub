"""Process-wide single-slot GPU admission guard.

One local GPU serves both batch translation and live sessions, so at most one
job of either kind may run at a time. Kind is "batch" or "live"; holding a slot
is not re-entrant (a second acquire of the same kind fails while it is held).
"""
import threading

_KINDS = ("batch", "live")
_held = None
_lock = threading.Lock()


def try_acquire(kind: str) -> bool:
    """Takes the GPU slot. True if acquired, False if another job holds it."""
    if kind not in _KINDS:
        raise ValueError(f"Unknown GPU job kind: {kind}")
    global _held
    with _lock:
        if _held is not None:
            return False
        _held = kind
        return True


def release(kind: str) -> None:
    """Frees the GPU slot. Raises if `kind` is not the current holder."""
    if kind not in _KINDS:
        raise ValueError(f"Unknown GPU job kind: {kind}")
    global _held
    with _lock:
        if _held != kind:
            raise RuntimeError(f"Cannot release {kind!r} GPU slot; held by {_held!r}")
        _held = None


def held_kind() -> str:
    """Which kind currently holds the slot, or None."""
    with _lock:
        return _held
