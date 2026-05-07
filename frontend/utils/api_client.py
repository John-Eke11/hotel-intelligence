"""HTTP client for the Hotel Intelligence FastAPI backend.

All methods return None on connection failure so the UI can degrade gracefully
without crashing when the backend is not yet running.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Optional

import requests
from requests.exceptions import RequestException


class APIClient:
    """Thin wrapper around the FastAPI backend REST API."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (
            base_url or os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
        ).rstrip("/")
        self._session = requests.Session()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get(self, path: str, params: Optional[dict] = None) -> Optional[dict | list]:
        try:
            resp = self._session.get(
                f"{self.base_url}{path}", params=params, timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except RequestException:
            return None

    def _post(self, path: str, payload: dict) -> Optional[dict]:
        try:
            resp = self._session.post(
                f"{self.base_url}{path}", json=payload, timeout=30
            )
            resp.raise_for_status()
            return resp.json()
        except RequestException:
            return None

    # ── Health ────────────────────────────────────────────────────────────────

    def health(self) -> bool:
        """Return True if the backend is reachable."""
        return self._get("/health") is not None

    # ── KPI metrics ───────────────────────────────────────────────────────────

    def get_kpis(
        self, from_date: date, to_date: date, property_id: int = 1
    ) -> Optional[dict]:
        """Occupancy, ADR, RevPAR, TRevPAR — with period-over-period deltas.

        Expected response shape:
            {
                "occupancy": 0.78,        "occupancy_delta": 0.03,
                "adr": 145.50,            "adr_delta": -2.10,
                "revpar": 113.49,         "revpar_delta": 1.20,
                "trevpar": 134.00,        "trevpar_delta": 5.80,
            }
        """
        return self._get(
            "/metrics/kpis",
            {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "property_id": property_id,
            },
        )

    def get_revenue_by_channel(
        self, from_date: date, to_date: date, property_id: int = 1
    ) -> Optional[list]:
        """Revenue breakdown by booking channel.

        Expected response shape:
            [{"channel": "direct", "total_revenue": 48200.0}, ...]
        """
        return self._get(
            "/metrics/revenue-by-channel",
            {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "property_id": property_id,
            },
        )

    def get_revenue_by_segment(
        self, from_date: date, to_date: date, property_id: int = 1
    ) -> Optional[list]:
        """Revenue breakdown by guest segment.

        Expected response shape:
            [{"segment": "leisure", "total_revenue": 62000.0}, ...]
        """
        return self._get(
            "/metrics/revenue-by-segment",
            {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "property_id": property_id,
            },
        )

    def get_monthly_trend(
        self, from_date: date, to_date: date, property_id: int = 1
    ) -> Optional[list]:
        """Monthly actual vs budget revenue.

        Expected response shape:
            [{"month": "2025-01-01", "actual_revenue": 95000.0, "target_revenue": 100000.0}, ...]
        """
        return self._get(
            "/metrics/monthly-trend",
            {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "property_id": property_id,
            },
        )

    def get_events(self, from_date: date, to_date: date) -> Optional[list]:
        """Events (external demand drivers) within the date range.

        Expected response shape:
            [{"event_name": "Iron Man Cascais", "event_type": "sporting",
              "event_start_date": "2025-06-14", "event_end_date": "2025-06-16",
              "historical_rate_uplift": 0.40, "is_recurring": true}, ...]
        """
        return self._get(
            "/events",
            {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
            },
        )

    # ── Chat / NL-to-SQL ─────────────────────────────────────────────────────

    def chat(self, query: str, property_id: int = 1) -> Optional[dict]:
        """Send a natural language query; return SQL + tabular results.

        Expected response shape:
            {
                "summary": "In March 2025, occupancy was 74.3%.",
                "sql": "SELECT ...",
                "data": {
                    "columns": ["month", "occupancy"],
                    "rows": [["2025-03-01", 0.743]]
                }
            }
        """
        return self._post("/api/query", {"user_prompt": query, "property_id": property_id})
