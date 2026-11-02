"""Re-export of the one shared cache. Never write a second cache implementation (prompt §7a)."""

from ty_common.cache import cached, fingerprint, invalidate, to_cell

__all__ = ["cached", "fingerprint", "invalidate", "to_cell"]
