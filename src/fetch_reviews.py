"""
Fetch Huckberry product reviews from the public Yotpo widget API.

Huckberry serves reviews through Yotpo. The widget API is public (no auth) and
returns clean JSON, including each reviewer's structured fit/height/weight fields
when the product's review form collects them.

Access pattern
--------------
- App key lives in the Yotpo loader script on any product page
  (cdn-widgetsrepository.yotpo.com/v1/loader/<APP_KEY>).
- Yotpo's product id is "P" + the numeric id in the Huckberry product URL,
  e.g. /store/flint-and-tinder/category/p/99266-... -> "P99266".
- Reviews: GET https://api.yotpo.com/v1/widget/<APP_KEY>/products/<PID>/reviews.json
           ?per_page=150&page=<n>&sort=date&direction=desc

Sort by date (not the default) so the sample is representative across star
ratings instead of front-loading 5-star reviews.

Usage
-----
    python src/fetch_reviews.py P99266 --pages 10 --out data/flagship_raw.json
"""
import argparse, json, time, sys
import urllib.request

APP_KEY = "yBhQs4CegPg4ZbbyeVNLkrF0S5mE6zOvQsDzb8IP"  # Huckberry, read from the page loader
BASE = "https://api.yotpo.com/v1/widget/{key}/products/{pid}/reviews.json"


def fetch_page(pid, page, per_page=150):
    url = (BASE.format(key=APP_KEY, pid=pid)
           + f"?per_page={per_page}&page={page}&sort=date&direction=desc")
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def custom_fields_by_title(cf):
    """Flatten Yotpo custom_fields ({'--34050': {'title':'Fit','value':1}, ...})."""
    out = {}
    for f in (cf or {}).values():
        if isinstance(f, dict) and f.get("title"):
            out[f["title"]] = f.get("value")
    return out


def fetch_reviews(pid, pages=10, keep_text=False):
    rows = []
    for p in range(1, pages + 1):
        data = fetch_page(pid, p)
        revs = (data.get("response") or {}).get("reviews") or []
        if not revs:
            break
        for rv in revs:
            cf = custom_fields_by_title(rv.get("custom_fields"))
            row = {
                "score": rv.get("score"),
                "fit": cf.get("Fit"),            # 1 runs small, 2 true, 3 runs large
                "height": cf.get("Height"),
                "weight": cf.get("Weight"),
                "body_type": cf.get("Body Type"),
                "size_kept": cf.get("Size Kept"),
                "verified": 1 if rv.get("verified_buyer") else 0,
                "date": (rv.get("created_at") or "")[:10],
            }
            if keep_text:
                row["title"] = rv.get("title") or ""
                row["content"] = rv.get("content") or ""
            rows.append(row)
        time.sleep(0.3)  # be polite
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pid", help="Yotpo product id, e.g. P99266")
    ap.add_argument("--pages", type=int, default=10)
    ap.add_argument("--text", action="store_true", help="keep review title/content")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rows = fetch_reviews(a.pid, a.pages, keep_text=a.text)
    out = a.out or f"data/{a.pid}_reviews.json"
    json.dump(rows, open(out, "w"))
    print(f"{len(rows)} reviews -> {out}", file=sys.stderr)
