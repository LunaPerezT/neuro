"""HTTP access to OpenNeuro: the GraphQL API plus the GitHub mirror as a fallback.

OpenNeuro mirrors every public dataset as a git repository in the
``OpenNeuroDatasets`` GitHub organisation. Small text files (dataset_description.json,
README, participants.tsv/json, sidecar JSON, events.tsv) live in git and can be read
from raw.githubusercontent.com even when openneuro.org itself is unreachable.
Large binary files are git-annexed and only available from OpenNeuro's S3 bucket.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from . import __version__

GRAPHQL_URL = os.environ.get("OPENNEURO_GRAPHQL_URL", "https://openneuro.org/crn/graphql")
GITHUB_RAW_BASE = os.environ.get(
    "OPENNEURO_GITHUB_RAW_BASE", "https://raw.githubusercontent.com/OpenNeuroDatasets"
)
S3_HTTP_BASE = "https://s3.amazonaws.com/openneuro.org"
BACKEND = os.environ.get("OPENNEURO_BACKEND", "auto").lower()  # auto | graphql | github
TIMEOUT = float(os.environ.get("OPENNEURO_TIMEOUT", "60"))
MAX_CONCURRENCY = int(os.environ.get("OPENNEURO_MAX_CONCURRENCY", "4"))
USER_AGENT = f"openneuro-mcp/{__version__} (+https://github.com/OpenNeuroDatasets)"



class OpenNeuroError(Exception):
    """An error with a message written for the calling agent."""


class BackendUnavailable(OpenNeuroError):
    """openneuro.org could not be reached (network/DNS/proxy), as opposed to a bad query."""


def normalize_dataset_id(dataset_id: str) -> str:
    """Accept 'ds2778', 'DS002778' or 'ds002778' and return 'ds002778'."""
    raw = dataset_id.strip().lower()
    match = re.fullmatch(r"ds0*(\d{1,6})", raw)
    if not match:
        raise OpenNeuroError(
            f"'{dataset_id}' is not an OpenNeuro dataset id. Ids look like 'ds002778' "
            "(the letters 'ds' followed by six digits). Use openneuro_search_datasets to find ids."
        )
    return f"ds{int(match.group(1)):06d}"


def safe_relative_path(path: str) -> str:
    """Normalise a path inside a dataset and refuse traversal."""
    clean = path.strip().lstrip("/")
    parts = [p for p in clean.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise OpenNeuroError("Paths must stay inside the dataset; '..' is not allowed.")
    return "/".join(parts)


@dataclass
class _CacheEntry:
    value: Any
    expires: float


@dataclass
class OpenNeuroClient:
    graphql_url: str = GRAPHQL_URL
    github_raw_base: str = GITHUB_RAW_BASE
    backend: str = BACKEND
    timeout: float = TIMEOUT
    _http: httpx.AsyncClient | None = None
    _cache: dict[str, _CacheEntry] = field(default_factory=dict)
    _sem: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(MAX_CONCURRENCY))

    # ------------------------------------------------------------------ lifecycle
    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    # ------------------------------------------------------------------ cache
    def cache_get(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry and entry.expires > time.monotonic():
            return entry.value
        self._cache.pop(key, None)
        return None

    def cache_set(self, key: str, value: Any, ttl: float) -> None:
        self._cache[key] = _CacheEntry(value, time.monotonic() + ttl)

    # ------------------------------------------------------------------ GraphQL
    @property
    def graphql_enabled(self) -> bool:
        return self.backend in ("auto", "graphql")

    @property
    def github_enabled(self) -> bool:
        return self.backend in ("auto", "github")

    async def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """POST a GraphQL document. Raises BackendUnavailable on network failure."""
        if not self.graphql_enabled:
            raise BackendUnavailable("The GraphQL backend is disabled (OPENNEURO_BACKEND=github).")
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        async with self._sem:
            try:
                resp = await self.http.post(
                    self.graphql_url,
                    json=payload,
                    # Apollo's CSRF protection needs a JSON content type (httpx sets it).
                    headers={"Accept": "application/json"},
                )
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ProxyError, httpx.ReadTimeout) as exc:
                raise BackendUnavailable(
                    f"Could not reach {self.graphql_url} ({type(exc).__name__}). "
                    "Check the network connection, or set OPENNEURO_BACKEND=github to read "
                    "metadata from the OpenNeuroDatasets GitHub mirror instead."
                ) from exc
        if resp.status_code == 429:
            raise OpenNeuroError("OpenNeuro rate limit reached (HTTP 429). Wait a minute and retry with fewer requests.")
        if resp.status_code >= 500:
            raise BackendUnavailable(f"OpenNeuro returned HTTP {resp.status_code}; the service may be down. Retry later.")
        try:
            body = resp.json()
        except ValueError as exc:
            raise OpenNeuroError(
                f"OpenNeuro returned HTTP {resp.status_code} with a non-JSON body; "
                "the endpoint may have changed or a proxy is intercepting the request."
            ) from exc
        errors = body.get("errors") or []
        if errors and not body.get("data"):
            messages = "; ".join(str(e.get("message", e)) for e in errors[:3])
            raise OpenNeuroError(f"OpenNeuro GraphQL error: {messages}")
        if resp.status_code >= 400:
            raise OpenNeuroError(f"OpenNeuro returned HTTP {resp.status_code}: {str(body)[:300]}")
        return body.get("data") or {}

    # ------------------------------------------------------------------ GitHub mirror
    async def github_text(self, dataset_id: str, path: str, ref: str = "HEAD") -> str | None:
        """Read a git-tracked text file from the GitHub mirror. Returns None on 404."""
        if not self.github_enabled:
            raise BackendUnavailable("The GitHub fallback is disabled (OPENNEURO_BACKEND=graphql).")
        url = f"{self.github_raw_base}/{dataset_id}/{ref}/{path}"
        async with self._sem:
            try:
                resp = await self.http.get(url)
            except httpx.HTTPError as exc:
                raise BackendUnavailable(f"Could not reach the GitHub mirror ({type(exc).__name__}).") from exc
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise OpenNeuroError(f"GitHub mirror returned HTTP {resp.status_code} for {path}.")
        return resp.text

    # ------------------------------------------------------------------ plain URLs
    async def fetch_text(self, url: str, max_bytes: int) -> tuple[str, bool]:
        """Download up to max_bytes of a text file. Returns (text, truncated)."""
        async with self._sem:
            try:
                async with self.http.stream("GET", url) as resp:
                    if resp.status_code >= 400:
                        raise OpenNeuroError(f"HTTP {resp.status_code} while downloading {url}.")
                    chunks: list[bytes] = []
                    total = 0
                    truncated = False
                    async for chunk in resp.aiter_bytes():
                        chunks.append(chunk)
                        total += len(chunk)
                        if total > max_bytes:
                            truncated = True
                            break
            except httpx.HTTPError as exc:
                raise BackendUnavailable(f"Could not download {url} ({type(exc).__name__}).") from exc
        data = b"".join(chunks)[:max_bytes]
        if b"\x00" in data[:4096]:
            raise OpenNeuroError(
                "This file is binary (e.g. NIfTI, EDF, FIF). Read only text files such as .json, "
                ".tsv, .md or README; use openneuro_get_download_info to fetch imaging data."
            )
        return data.decode("utf-8", errors="replace"), truncated
