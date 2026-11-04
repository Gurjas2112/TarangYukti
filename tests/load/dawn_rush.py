"""Dawn rush (spec §15.2.5, Gate L1): around 04:00 IST many fishers ask the same few things at once.

Run in Azure Load Testing (Locust) or locally: `locust -f tests/load/dawn_rush.py --host https://<channels host>`.
Pass: 200 users for 15 minutes, p95 < 2 s for the card, errors < 1 %, no replica restarts, Gemini within the cap
(these paths never call the LLM), and the WAF blocks one IP above 300 requests a minute.
"""

from __future__ import annotations

import random

from locust import HttpUser, between, task

HARBOURS = ["rameswaram", "pamban", "mandapam", "keelakarai", "thondi"]
BOATS = ["small_frp", "non_motorised", "mechanised_trawler"]
LANGS = ["ta-IN", "en-IN", "ml-IN", "te-IN"]


class Fisher(HttpUser):
    wait_time = between(5, 20)

    @task(5)
    def todays_sea(self) -> None:
        q = f"harbour={random.choice(HARBOURS)}&boat_type={random.choice(BOATS)}&lang={random.choice(LANGS)}"
        self.client.get(f"/brief?{q}", name="brief")

    @task(1)
    def why(self) -> None:
        self.client.get("/sources/chunk/1", name="sources")

    @task(1)
    def languages(self) -> None:
        self.client.get("/languages", name="languages")
