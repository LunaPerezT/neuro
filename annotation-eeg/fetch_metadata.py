"""Download participant-level metadata for every dataset in census_eeg.json from the
OpenNeuroDatasets GitHub mirror (git-tracked text files only)."""

import asyncio
import json
import sys
from pathlib import Path

import httpx

BASE = "https://raw.githubusercontent.com/OpenNeuroDatasets"
FILES = ["participants.tsv", "participants.json", "dataset_description.json", "README", "README.md", "README.txt"]
OUT = Path("raw")


async def fetch(client: httpx.AsyncClient, sem: asyncio.Semaphore, ds: str, name: str) -> tuple[str, str, int]:
    dest = OUT / ds / name
    if dest.exists():
        return ds, name, 200
    async with sem:
        for attempt in range(3):
            try:
                r = await client.get(f"{BASE}/{ds}/HEAD/{name}")
                break
            except httpx.HTTPError:
                await asyncio.sleep(2 * (attempt + 1))
        else:
            return ds, name, -1
    if r.status_code == 200:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
    return ds, name, r.status_code


async def main() -> None:
    ids = [r["id"] for r in json.load(open(sys.argv[1]))]
    sem = asyncio.Semaphore(12)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        results = await asyncio.gather(*(fetch(client, sem, ds, f) for ds in ids for f in FILES))
    status: dict[str, dict[str, int]] = {}
    for ds, name, code in results:
        status.setdefault(ds, {})[name] = code
    json.dump(status, open("fetch_status.json", "w"), indent=1)
    have = lambda f: sum(1 for s in status.values() if s.get(f) == 200)
    print(f"datasets: {len(status)}")
    for f in FILES:
        print(f"  {f}: {have(f)}")
    print("errors:", sum(1 for s in status.values() for c in s.values() if c not in (200, 404)))
    print("not on mirror (no description):", [d for d, s in status.items() if s.get("dataset_description.json") != 200][:20])


asyncio.run(main())
