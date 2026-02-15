import json
import os
from datetime import datetime, timezone, date
from typing import Any, Optional

import fortnite_api
from dateutil.parser import isoparse


OUT_DIR = "docs/data"
TOP_JSON = os.path.join(OUT_DIR, "top.json")

TOP_LIMIT = 60  # how many items to show on homepage


# -----------------------
# Safety helpers
# -----------------------

def json_safe(x: Any) -> Any:
    """Convert ANY object into JSON-safe data."""
    if x is None:
        return None
    if isinstance(x, (str, int, float, bool)):
        return x
    if isinstance(x, (date, datetime)):
        try:
            if isinstance(x, datetime) and x.tzinfo is None:
                x = x.replace(tzinfo=timezone.utc)
            return x.isoformat()
        except Exception:
            return str(x)

    if isinstance(x, dict):
        return {str(k): json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [json_safe(v) for v in x]

    # Fortnite Asset objects often have .url
    url = getattr(x, "url", None)
    if isinstance(url, str):
        return url

    # Enums often have these
    for attr in ("display_value", "value", "name"):
        v = getattr(x, attr, None)
        if isinstance(v, str):
            return v

    try:
        return str(x)
    except Exception:
        return None


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


def days_since(iso_date: Optional[str]) -> Optional[int]:
    if not iso_date:
        return None
    last = date.fromisoformat(iso_date)
    today = datetime.now(timezone.utc).date()
    return (today - last).days


def pick_icon(item) -> Optional[str]:
    images = getattr(item, "images", None)
    if images is None:
        return None
    icon = getattr(images, "icon", None) or getattr(images, "small_icon", None)
    return json_safe(icon)


# -----------------------
# Main script
# -----------------------

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    api_key = os.environ.get("FORTNITE_API_KEY")
    flags = fortnite_api.ResponseFlags.INCLUDE_SHOP_HISTORY

    results = []

    with fortnite_api.SyncClient(api_key=api_key, response_flags=flags) as client:

        # 1) Get ALL cosmetics (with history)
        print("Fetching cosmetics...")
        all_cosmetics = client.fetch_cosmetics_all()
        br_items = all_cosmetics.br

        # 2) Get CURRENT SHOP
        print("Fetching current shop...")
        shop = client.fetch_shop()

        shop_ids = set()
        for entry in shop.entries:
            for item in entry.items:
                shop_ids.add(item.id)

        print(f"Current shop items: {len(shop_ids)}")

        # 3) Process only items currently in shop
        for item in br_items:

            item_id = getattr(item, "id", None)
            if item_id not in shop_ids:
                continue  # skip if not currently in shop

            history = getattr(item, "shop_history", None) or []
            if not history:
                continue  # skip items with no shop history

            iso_dates = [to_iso_date(h) for h in history]
            iso_dates = [d for d in iso_dates if d]
            if not iso_dates:
                continue

            last_seen = max(iso_dates)
            d_since = days_since(last_seen)

            results.append({
                "id": item_id,
                "name": getattr(item, "name", None),
                "type": getattr(item, "type", None),
                "rarity": getattr(item, "rarity", None),
                "icon": pick_icon(item),
                "last_seen": last_seen,
                "days_since": d_since
            })

    # 4) Sort by rarity (longest ago first)
    results.sort(key=lambda x: -(x["days_since"] or 0))

    # 5) Keep top N
    top = results[:TOP_LIMIT]

    payload = {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "count": len(top),
        "items": json_safe(top)
    }

    with open(TOP_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print(f"Wrote {TOP_JSON} with {len(top)} items")


if __name__ == "__main__":
    main()
