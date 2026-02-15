import json
import os
from datetime import datetime, timezone, date

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

def bucket_for(days: int | None, never_in_shop: bool) -> str:
    if never_in_shop:
        return "never-in-shop"
    if days is None:
        return "unknown"
    for name, threshold in BUCKETS:
        if days >= threshold:
            return name
    return "0-6"

def to_iso_date(dt) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        parsed = isoparse(dt)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.date().isoformat()
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date().isoformat()
    except Exception:
        return None

def days_since(iso_yyyy_mm_dd: str | None) -> int | None:
    if not iso_yyyy_mm_dd:
        return None
    last = date.fromisoformat(iso_yyyy_mm_dd)
    today = datetime.now(timezone.utc).date()
    return (today - last).days

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

            icon = None
            images = getattr(item, "images", None)
            if images:
                icon = getattr(images, "icon", None) or getattr(images, "small_icon", None)

            ctype = None
            t = getattr(item, "type", None)
            if t:
                ctype = getattr(t, "value", None) or getattr(t, "display_value", None) or str(t)

            rarity = None
            r = getattr(item, "rarity", None)
            if r:
                rarity = getattr(r, "value", None) or getattr(r, "display_value", None) or str(r)

            enriched.append({
                "id": getattr(item, "id", None),
                "name": getattr(item, "name", None),
                "type": ctype,
                "rarity": rarity,
                "icon": icon,
                "last_seen": last_seen_iso,
                "days_since_last_seen": d_since,
                "bucket": bkt,
                "never_in_shop": never_in_shop,
            })

    # Sort: rarest first by days_since; push never/unknown to bottom
    def sort_key(x):
        if x["never_in_shop"]:
            return (2, 0)
        if x["days_since_last_seen"] is None:
            return (1, 0)
        return (0, -x["days_since_last_seen"])

    enriched.sort(key=sort_key)

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
