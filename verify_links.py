#!/usr/bin/env python3
"""Poland Power Pulse — daily link check (GitHub Actions).

Opens every article link built into index.html plus the live-feed links in
data/signals.json and writes:
  data/headlines.json   — {"bad_links": [...]} read by the dashboard, which then
                          skips any secondary source link that is definitely dead;
  data/link_report.json — status of every link, for you to review.

A link is marked bad ONLY on 404/410 or when the site cannot be reached at all.
403/429 and similar "bot blocked" answers are reported as 'blocked' but NOT marked
bad, because many publishers block automated checks while the page works in a browser.
Headlines are never changed by this script — they stay exactly as curated.
Uses only the Python standard library.
"""
import concurrent.futures as cf, datetime as dt, json, os, re, socket, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
SKIP = re.compile(r"fonts\.g|googleapis|w3\.org|schemas-microsoft|github\.com|\$\{")


def urls():
    s = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    found = {u.replace("\\_", "_").rstrip(".,;") for u in re.findall(r"https?://[^\s\"'<>`\\)]+", s)}
    try:
        for it in json.load(open(os.path.join(ROOT, "data", "signals.json"), encoding="utf-8")).get("signals", []):
            for l in it.get("links", []):
                found.add(l["url"])
    except Exception:
        pass
    return sorted(u for u in found if not SKIP.search(u))


def check(u):
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(u, method=method, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return u, r.status, "ok"
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 400, 501):
                continue
            return u, e.code, "bad" if e.code in (404, 410) else "blocked"
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            reason = str(getattr(e, "reason", e))
            if method == "HEAD":
                continue
            dns = "Name or service not known" in reason or "getaddrinfo" in reason or "nodename" in reason
            return u, None, "bad" if dns else "unreachable"
        except Exception as e:
            return u, None, f"error: {type(e).__name__}"
    return u, None, "unreachable"


def main():
    links = urls()
    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(check, links))
    bad = sorted(u for u, _, v in res if v == "bad")
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    json.dump({"generated": now, "items": {}, "bad_links": bad},
              open(os.path.join(ROOT, "data", "headlines.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"generated": now, "checked": len(res),
               "summary": {k: sum(1 for *_, v in res if v == k) for k in sorted({v for *_, v in res})},
               "links": [{"url": u, "status": c, "result": v} for u, c, v in res]},
              open(os.path.join(ROOT, "data", "link_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"checked {len(res)} links · bad {len(bad)}")
    for u in bad:
        print("BAD", u)


if __name__ == "__main__":
    main()
