"""Step 0: public OpenNeuro census and the list of human datasets.

Writes census_all.json (one row per public dataset), meta/census_human.json and ids_human.txt
(not synthetic, species human or unreported, minus excluded_nonhuman_extra.json).
Usage: python census.py
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "openneuro-mcp" / "src"))
from openneuro_mcp import service  # noqa: E402
from openneuro_mcp.client import OpenNeuroClient  # noqa: E402

NON_HUMAN = {"mouse", "rat", "macaque", "monkey", "rhesus monkey", "canine", "sheep", "pig", "zebrafish", "marmoset"}


async def main():
    client = OpenNeuroClient()
    try:
        rows = await service.census(client, modality=None, include_groups=False, refresh=True, max_datasets=100_000)
    finally:
        await client.aclose()
    extra = set(json.loads((ROOT / "excluded_nonhuman_extra.json").read_text()))
    human = [r for r in rows if not r.get("synthetic") and (r.get("species") or "human").lower() not in NON_HUMAN
             and r["id"] not in extra]
    (ROOT / "census_all.json").write_text(json.dumps(rows))
    (ROOT / "meta").mkdir(exist_ok=True)
    (ROOT / "meta" / "census_human.json").write_text(json.dumps(human))
    (ROOT / "ids_human.txt").write_text("\n".join(r["id"] for r in human) + "\n")
    print(f"{len(rows)} public datasets, {len(human)} human")


if __name__ == "__main__":
    asyncio.run(main())
