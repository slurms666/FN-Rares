import json
import os
from datetime import datetime, timezone, date
from typing import Any, Optional

import fortnite_api
from dateutil.parser import isoparse


OUT_DIR = "docs/data"
RARES_JSON = os.path.join(OUT_DIR, "rares.json")
TOP_JSON = os.path.join(OUT_DIR, "rares_top.json")

BUCKETS = [
    ("365+", 365),
    ("180+", 180),
    ("90+", 90),
    ("30+", 30),
    ("7+", 7),
]


def safe_str(x: Any) -> Optional[str]:
    """Convert enums/objects into a JSON-safe string (or None)."""
    if x is None:
        return None
    for attr in ("display_value", "value", "name"):
        v = getattr(x, attr, None)
        if isinstance(v, str) and v.strip():
            return v.strip()
    try:
        s = str(x).strip()
        return s if s else None
    except Exception:
        return None


def safe_url(x: Any) -> Optional[str]:
    """
    Convert fortnite_api Asset / image objects into a URL string if possible.
    - If x is already a string URL, return it
    - If x has a 'url' attribute (common for Asset), return that
    - Else try to stringify
    """
    if x is None:
        return None

    if isinstance(x, str):
        return x

    # Common pattern: Asset(url="https://...")
    u = getattr(x, "url", None)
    if isinstance(u, str) and u.strip():
        return u.strip()

    # Sometimes nested in 'value'
    v = getattr(x, "value", None)
    if isinstance(v, str) and v.strip():
        return v.strip()

    return safe_str(x)


def to_iso_date(dt: Any) -> Optional[str]:
    """Normalize shop history entries to ISO YYYY-MM-DD."""
    if dt is None:
        return None

    if isinstance(dt, str):
        parsed = isoparse(dt)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.date().isoformat()

    try:
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date().isoformat()
    except Exception:
        return None


def days_since(iso_yyyy_mm_dd: Optional[str]) -> Optional[int]:
    if not iso_yyyy_mm_dd:
        return None
    last = date.fromisoformat(iso_yyyy_mm_dd)
    today = datetime.now(timezone.utc).date()
    return (today - last).days


def bucket_for(days: Optional[int], never_in_shop: bool) -> str:
    if never_in_shop:
        return "never-in-shop"
    if days is None:
        return "unknown"
    for name, threshold in BUCKETS:
        if days >= threshold:
            return name
    return "0-6"


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    api_key = os.environ.get("FORTNITE_API_KEY")
    response_flags = fortnite_api.ResponseFlags.INCLUDE_SHOP_HISTORY

    items_out = []

    with fortnite_api.SyncClient(api_key=api_key, response_flags=response_flags) as client:
        all_cosmetics = client.fetch_cosmetics_all()
        br_items = all_cosmetics.br

        for item in br_items:
            history = getattr(item, "shop_history", None) or []
            never_in_shop = (len(history) == 0)

            last_seen_iso = None
            if history:
                iso_dates = [to_iso_date(x) for x in history]
                iso_dates = [d for d in iso_dates if d]
                last_seen_iso = max(iso_dates) if iso_dates else None

            d_since = days_since(last_seen_iso)
            bkt = bucket_for(d_since, never_in_shop)

            # Extract image URL safely (Asset -> url)
            icon = None
            images = getattr(item, "images", None)
            if images is not None:
                icon = safe_url(getattr(images, "icon", None)) or safe_url(getattr(images, "small_icon", None))

            # JSON-safe strings for type/rarity/id/name
            items_out.append({
                "id": safe_str(getattr(item, "id", None)),
                "name": safe_str(getattr(item, "name", None)),
                "type": safe_str(getattr(item, "type", None)),
                "rarity": safe_str(getattr(item, "rarity", None)),
                "icon": icon,
                "last_seen": last_seen_iso,
                "days_since_last_seen": d_since,
                "bucket": bkt,
                "never_in_shop": bool(never_in_shop),
            })

    # Sort: rarest first; push never/unknown to bottom
    def sort_key(x: dict) -> tuple:
        if x["never_in_shop"]:
            return (2, 0)
        if x["days_since_last_seen"] is None:
            return (1, 0)
        return (0, -int(x["days_since_last_seen"]))

    items_out.sort(key=sort_key)

    top = [x for x in items_out if (not x["never_in_shop"]) and (x["days_since_last_seen"] is not None)][:60]

    payload_all = {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "count": len(items_out),
        "items": items_out
    }
    payload_top = {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "count": len(top),
        "items": top
    }

    with open(RARES_JSON, "w", encoding="utf-8") as f:
        json.dump(payload_all, f, ensure_ascii=False)

    with open(TOP_JSON, "w", encoding="utf-8") as f:
        json.dump(payload_top, f, ensure_ascii=False)

    print("Wrote:", RARES_JSON, "and", TOP_JSON)


if __name__ == "__main__":
    main()
