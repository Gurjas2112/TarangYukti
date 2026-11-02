"""One push sender, two transports: Expo (Android) and pywebpush (web). Implemented in Milestone 6."""

from __future__ import annotations

from typing import Literal

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
Kind = Literal["web", "expo"]
