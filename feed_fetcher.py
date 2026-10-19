#!/usr/bin/env python3
"""Poland Power Pulse — live feed updater (runs every 30 min in GitHub Actions).

Reads the RSS/Atom feeds in config/sources.json, keeps Polish power-sector news,
translates Polish headlines to English (DeepL or Azure Translator, key from a
repository secret) and writes data/signals.json, which the dashboard merges with
its built-in, hand-checked items.

Rules applied:
  * the headline is kept exactly as the publisher wrote it — never rephrased;
  * Polish items keep the original headline and add an English translation;
    if no translation key is set, Polish items are skipped (not shown untranslated);
  * the link is the publisher's own article link from the feed;
  * items already built into index.html (same URL) are not duplicated;
  * only items published on or after 1 Jan 2024 are kept.
Uses only the Python standard library.
"""
import datetime as dt, email.utils, hashlib, html, json, os, re, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "signals.json")
STATUS = os.path.join(ROOT, "data", "feed_status.json")
MIN_DATE = "2024-01-01"
MAX_ITEMS = 2000
UA = "Mozilla/5.0 (compatible; PolandPowerPulseBot/1.0; +https://github.com)"

POWER = re.compile(r"energ|electric|power|grid|offshore|onshore|wind|solar|\bpv\b|photovolt|batter|\bbess\b|storage|ccgt|ocgt|"
                   r"gas-fired|gas plant|gas turbine|cogenerat|\bchp\b|district heat|coal|lignite|nuclear|\bsmr|reactor|"
                   r"capacity market|\bppa\b|hydrogen|biomethane|\bure\b|\bpse\b|tariff|"
                   r"prąd|elektrown|elektrociepł|ciepłown|\boze\b|wiatr|fotowolt|magazyn|gazow|kogener|węgl|atom|jądrow|"
                   r"sieci|rynek mocy|rynku mocy|taryf|wodór|biometan|energetyk", re.I)
POLAND = re.compile(r"poland|polish|polsk|warsaw|warszaw|baltic|bałtyk|pomerania|silesia|"
                    r"\bpge\b|enea|energa|orlen|tauron|ze pak|polenergia|\bpse\b|\bure\b|lubiatowo|kozienice|"
                    r"bełchatów|belchatow|ostrołęka|grudziądz|baltica|bc-wind", re.I)
COMPANIES = [
    ("PGE", r"\bpge\b"), ("ENEA", r"\benea\b"), ("ENERGA", r"\benerg(a|i|ę|ą)\b"), ("ORLEN", r"\borlen"),
    ("TAURON", r"\btauron"), ("ZEPAK", r"ze pak|zepak"), ("PEJ", r"\bpej\b|polskie elektrownie jądrowe"),
    ("OSGE", r"orlen synthos|\bosge\b"), ("POLENERGIA", r"polenergi"), ("FORTUM", r"fortum"), ("AXPO", r"\baxpo"),
    ("ENGIE", r"\bengie"), ("EQUINOR", r"equinor"), ("ORSTED", r"ørsted|orsted"), ("RWE", r"\brwe\b"),
    ("TOTAL", r"totalenergies"), ("EDPR", r"\bedpr?\b|edp renewables"), ("OCEANWINDS", r"ocean winds"),
    ("EDF", r"\bedf\b"), ("SHELL", r"\bshell\b"), ("ENI", r"\beni\b|plenitude"), ("BP", r"\bbp\b"),
    ("REPSOL", r"repsol"), ("IBERDROLA", r"iberdrola"), ("ENBW", r"\benbw\b"), ("UNIPER", r"uniper"),
    ("STATKRAFT", r"statkraft"), ("SSE", r"\bsse\b"),
]
COMPANIES = [(c, re.compile(p, re.I)) for c, p in COMPANIES]


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def text(el):
    return html.unescape(re.sub(r"<[^>]+>", " ", el or "")).replace("\xa0", " ").strip()


def clean(t):
    return re.sub(r"\s+", " ", text(t)).strip()


def parse_date(s):
    if not s:
        return None
    try:
        return email.utils.parsedate_to_datetime(s).date().isoformat()
    except Exception:
        pass
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s.strip())
    return m.group(1) if m else None


def parse_feed(raw):
    """Return [(title, link, date, description)] from RSS 2.0 or Atom."""
    root = ET.fromstring(raw)
    out = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        f = {c.tag.split("}")[-1]: c for c in it}
        title = clean(f["title"].text if "title" in f else "")
        link = ""
        if "link" in f:
            link = (f["link"].text or "").strip() or f["link"].attrib.get("href", "")
        for c in it:  # Atom: prefer rel="alternate"
            if c.tag.split("}")[-1] == "link" and c.attrib.get("rel", "alternate") == "alternate" and c.attrib.get("href"):
                link = c.attrib["href"]
                break
        date = None
        for k in ("pubDate", "published", "updated", "date"):
            if k in f and f[k].text:
                date = parse_date(f[k].text)
                if date:
                    break
        desc = ""
        for k in ("description", "summary", "content"):
            if k in f and f[k].text:
                desc = clean(f[k].text)
                break
        if title and link and date:
            out.append((title, link.strip(), date, desc))
    return out


def translate(texts):
    """Polish → English. DeepL first, then Azure Translator. Returns None if no key is configured."""
    texts = [t or "" for t in texts]
    key = os.environ.get("DEEPL_API_KEY", "").strip()
    if key:
        host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
        body = urllib.parse.urlencode([("source_lang", "PL"), ("target_lang", "EN-GB")] + [("text", t) for t in texts]).encode()
        req = urllib.request.Request(f"https://{host}/v2/translate", data=body,
                                     headers={"Authorization": f"DeepL-Auth-Key {key}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return [x["text"] for x in json.load(r)["translations"]]
    key = os.environ.get("AZURE_TRANSLATOR_KEY", "").strip()
    if key:
        req = urllib.request.Request(
            "https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&from=pl&to=en",
            data=json.dumps([{"Text": t} for t in texts]).encode(),
            headers={"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/json",
                     "Ocp-Apim-Subscription-Region": os.environ.get("AZURE_TRANSLATOR_REGION", "westeurope")})
        with urllib.request.urlopen(req, timeout=30) as r:
            return [x["translations"][0]["text"] for x in json.load(r)]
    return None


def curated_urls():
    """URLs already built into index.html — skip these so the feed does not duplicate them."""
    try:
        s = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    except OSError:
        return set()
    return {u.rstrip("/").replace("\\_", "_") for u in re.findall(r"https?://[^\s\"'<>`\\)]+", s)}


def norm_url(u):
    p = urllib.parse.urlsplit(u)
    q = urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith("utm_")])
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, q, "")).rstrip("/")


def main():
    cfg = json.load(open(os.path.join(ROOT, "config", "sources.json"), encoding="utf-8"))
    try:
        prev = json.load(open(OUT, encoding="utf-8")).get("signals", [])
    except Exception:
        prev = []
    known = {s["id"]: s for s in prev if s.get("id")}
    skip = curated_urls()
    status, fresh, pending_pl = [], [], []

    for f in cfg["feeds"]:
        if not f.get("enabled", True):
            continue
        st = {"name": f["name"], "url": f["url"], "ok": False, "items": 0, "kept": 0}
        try:
            entries = parse_feed(fetch(f["url"]))
            st.update(ok=True, items=len(entries))
        except Exception as e:
            st["error"] = f"{type(e).__name__}: {str(e)[:120]}"
            status.append(st)
            continue
        for title, link, date, desc in entries:
            url = norm_url(link)
            hay = f"{title} {desc}"
            if date < MIN_DATE or url in skip or not POWER.search(hay):
                continue
            if f.get("poland_only") and not POLAND.search(hay):
                continue
            iid = "live-" + hashlib.sha1(url.encode()).hexdigest()[:12]
            if iid in known:
                continue
            cos = [c for c, rx in COMPANIES if rx.search(hay)] or ["ALL"]
            item = {"id": iid, "date": date, "lang": f["lang"], "publisher": f["name"], "cos": cos, "region": "National",
                    "links": [{"label": f"{f['name']} — article", "url": link, "type": "press"}],
                    "title": title, "summary": desc[:320].rsplit(" ", 1)[0] + "…" if len(desc) > 320 else desc}
            st["kept"] += 1
            if f["lang"] == "pl":
                item.update(title_pl=title, translated=False)
                pending_pl.append(item)
            else:
                fresh.append(item)
        status.append(st)

    tr_note = "no translation key set — Polish items skipped"
    if pending_pl:
        try:
            for i in range(0, len(pending_pl), 25):
                batch = pending_pl[i:i + 25]
                res = translate([b["title_pl"] for b in batch] + [b["summary"] for b in batch])
                if res is None:
                    break
                n = len(batch)
                for b, t, sm in zip(batch, res[:n], res[n:]):
                    b.update(title=t, summary=sm, translated=True)   # title = English translation; title_pl = exact original
                    fresh.append(b)
            else:
                tr_note = "ok"
        except Exception as e:
            tr_note = f"translation failed: {type(e).__name__}: {str(e)[:120]}"

    allitems = list(known.values()) + fresh
    allitems = [s for s in allitems if s.get("date", "") >= MIN_DATE and (s.get("lang") != "pl" or s.get("translated"))]
    allitems.sort(key=lambda s: s["date"], reverse=True)
    allitems = allitems[:MAX_ITEMS]
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"generated": now, "count": len(allitems), "signals": allitems}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"generated": now, "new_items": len(fresh), "translation": tr_note, "feeds": status},
              open(STATUS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(fresh)} new · {len(allitems)} total · translation: {tr_note}")
    for st in status:
        print(("OK  " if st["ok"] else "FAIL"), st["name"], st.get("kept", 0), st.get("error", ""))


if __name__ == "__main__":
    sys.exit(main())
