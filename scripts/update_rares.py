import json
import os
from datetime import datetime, timezone, date, datetime as dt_type
from typing import Any, Optional, Dict, List

import fortnite_api
from dateutil.parser import isoparse


OUT_DIR = "docs/data"

# Output files (small + structured)
META_JSON = os.path.join(OUT_DIR, "meta.json")
TOP_JSON = os.path.join(OUT_DIR, "top.json")
BUCKETS_JSON = os.path.join(OUT_DIR, "buckets.json")

# Threshold buckets
BUCKET_RULES = [
    ("365+", 365),
    ("180+", 180),
    ("90+", 90),
    ("30+", 30),
    ("7+", 7),
]

# cap items per bucket to keep file sizes sensible
PER_BUCKET_LIMIT = 500
TOP_LIMIT = 60


def to_iso_date(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, str):
        try:
            parsed = isoparse(x)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.date().isoformat()
        except Exception:
            return None
    try:
        if getattr(x, "tzinfo", None) is None and hasattr(x, "replace"):
            x = x.replace(tzinfo=timezone.utc)
        if hasattr(x, "date"):
            return x.date().isoformat()
    except Exception:
        pass
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
    for name, threshold in BUCKET_RULES:
        if days >= threshold:
            return name
    return "0-6"


def json_safe(x: Any) -> Any:
    """Recursively convert ANY object into something json.dump can handle."""
    if x is None:
        return None
    if isinstance(x, (str, int, float, bool)):
        return x
    if isinstance(x, (date, dt_type)):
        try:
            if isinstance(x, dt_type):
                if x.tzinfo is None:
                    x = x.replace(tzinfo=timezone.utc)
                return x.isoformat()
            return x.isoformat()
        except Exception:
            return str(x)

    if isinstance(x, dict):
        return {str(k): json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [json_safe(v) for v in x]

    # wrapper asset types often expose .url
    u = getattr(x, "url", None)
    if isinstance(u, str) and u.strip():
        return u.strip()

    # wrapper enums/objects often expose these
    for attr in ("display_value", "value", "name"):
        v = getattr(x, attr, None)
        if isinstance(v, str) and v.strip():
            return v.strip()

    try:
        return str(x)
    except Exception:
        return None


def pick_icon(item: Any) -> Optional[str]:
    images = getattr(item, "images", None)
    if images is None:
        return None
    icon = getattr(images, "icon", None) or getattr(images, "small_icon", None)
    return json_safe(icon)  # converts Asset -> url string if needed


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    api_key = os.environ.get("FORTNITE_API_KEY")
    response_flags = fortnite_api.ResponseFlags.INCLUDE_SHOP_HISTORY

    items: List[Dict[str, Any]] = []

    with fortnite_api.SyncClient(api_key=api_key, response_flags=response_flags) as client:
        all_cosmetics = client.fetch_cosmetics_all()
        br_items = all_cosmetics.br

        for item in br_items:
            history = getattr(item, "shop_history", None) or []
            never_in_shop = (len(history) == 0)

            last_seen_iso = None
            if history:
                iso_dates = [to_iso_date(h) for h in history]
                iso_dates = [d for d in iso_dates if d]
                last_seen_iso = max(iso_dates) if iso_dates else None

            d_since = days_since(last_seen_iso)
            bkt = bucket_for(d_since, never_in_shop)

            items.append({
                # keep only fields the website needs
                "id": getattr(item, "id", None),
                "name": getattr(item, "name", None),
                "type": getattr(item, "type", None),
                "rarity": getattr(item, "rarity", None),
                "icon": pick_icon(item),
                "last_seen": last_seen_iso,
                "days_since": d_since,
                "bucket": bkt,
                "never_in_shop": bool(never_in_shop),
            })

    # sanitize everything once
    items = json_safe(items)

    # sorting: rarest first by days_since; push never/unknown to bottom
    def sort_key(x: dict) -> tuple:
        if x.get("never_in_shop"):
            return (2, 0)
        if x.get("days_since") is None:
            return (1, 0)
        return (0, -int(x["days_since"]))

    items.sort(key=sort_key)

    # Top list (homepage)
    top = [x for x in items if (not x.get("never_in_shop")) and (x.get("days_since") is not None)][:TOP_LIMIT]

    # Buckets (capped)
    buckets: Dict[str, List[dict]] = {
        "365+": [],
        "180+": [],
        "90+": [],
        "30+": [],
        "7+": [],
        "0-6": [],
        "never-in-shop": [],
        "unknown": [],
    }

    for x in items:
        b = x.get("bucket", "unknown")
        if b not in buckets:
            b = "unknown"
        # cap all the big buckets
        if len(buckets[b]) < PER_BUCKET_LIMIT:
            buckets[b].append(x)

    meta = {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "total_items": len(items),
        "top_count": len(top),
        "bucket_counts": {k: len(v) for k, v in buckets.items()},
    }

    # write outputs
    with open(META_JSON, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)

    with open(TOP_JSON, "w", encoding="utf-8") as f:
        json.dump({"updated_utc": meta["updated_utc"], "items": top}, f, ensure_ascii=False)

    with open(BUCKETS_JSON, "w", encoding="utf-8") as f:
        json.dump({"updated_utc": meta["updated_utc"], "buckets": buckets}, f, ensure_ascii=False)

    print("Wrote:", META_JSON, TOP_JSON, BUCKETS_JSON)


if __name__ == "__main__":
    main()
