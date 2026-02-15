import json
import os
from datetime import datetime, timezone, date
from typing import Any, Optional

import fortnite_api
from dateutil.parser import isoparse


OUT_DIR = "docs/data"
RARES_JSON = os.path.join(OUT_DIR, "rares.json")
TOP_JSON = os.path.join(OUT_DIR, "rares_top.json")

# Buckets you wanted (in days)
BUCKETS = [
    ("365+", 365),
    ("180+", 180),
    ("90+", 90),
    ("30+", 30),
    ("7+", 7),
]


def safe_str(x: Any) -> Optional[str]:
    """
    Convert fortnite_api enums/objects (and anything else) into a JSON-safe string.
    Returns None for None.
    """
    if x is None:
        return None

    # Some wrapper objects hold their useful value in one of these attributes.
    for attr in ("display_value", "value", "name"):
        v = getattr(x, attr, None)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # Sometimes the object itself stringifies nicely; if not, this still won't crash JSON.
    try:
        s = str(x).strip()
        return s if s else None
    except Exception:
        return None


def to_iso_date(dt: Any) -> Optional[str]:
    """
    Normalize shop history entries to ISO YYYY-MM-DD strings.
    Wrapper versions can return datetime objects or strings.
    """
    if dt is None:
        return None

    if isinstance(dt, str):
        parsed = isoparse(dt)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.date().isoformat()

    # datetime-like objects
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

    enriched = []

    # IMPORTANT: fortnite_api requires a session. The context manager sets it up.
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

            # Icon image (best-effort)
            icon = None
            images = getattr(item, "images", None)
            if images is not None:
                icon = getattr(images, "icon", None) or getattr(images, "small_icon", None)

            # Make these JSON-safe strings no matter what
            ctype = safe_str(getattr(item, "type", None))
            rarity = safe_str(getattr(item, "rarity", None))

            enriched.append({
                "id": safe_str(getattr(item, "id", None)),
                "name": safe_str(getattr(item, "name", None)),
                "type": ctype,
                "rarity": rarity,
                "icon": icon,  # URL string already
                "last_seen": last_seen_iso,  # YYYY-MM-DD
                "days_since_last_seen": d_since,
                "bucket": bkt,
                "never_in_shop": never_in_shop,
            })

    # Sort: rarest first by days_since; push never/unknown to bottom
    def sort_key(x: dict) -> tuple:
        if x["never_in_shop"]:
            return (2, 0)
        if x["days_since_last_seen"] is None:
            return (1, 0)
        return (0, -int(x["days_since_last_seen"]))

    enriched.sort(key=sort_key)

    # Homepage selection: only items that have actually been in the shop
    top = [x for x in enriched if (not x["never_in_shop"]) and (x["days_since_last_seen"] is not None)][:60]

    payload_all = {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "count": len(enriched),
        "items": enriched
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
