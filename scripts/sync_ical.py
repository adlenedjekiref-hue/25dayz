"""Récupère le calendrier iCal de chaque logement et écrit les nuits réservées
dans availability/<id>.json. Seules les dates sont conservées, jamais les noms."""
import json, os, re, sys, urllib.request
from datetime import date, datetime, timedelta, timezone

# id du logement -> nom du secret GitHub qui contient son lien iCal
LISTINGS = {
    "vue": "ICAL_VUE",
}

def parse_date(value):
    value = value.strip()[:8]
    return date(int(value[:4]), int(value[4:6]), int(value[6:8]))

def ranges_from_ics(text):
    text = re.sub(r"\r?\n[ \t]", "", text)  # dépliage des lignes iCal
    ranges, start, end = [], None, None
    for line in text.splitlines():
        if line.startswith("BEGIN:VEVENT"):
            start = end = None
        elif line.startswith("DTSTART"):
            start = parse_date(line.split(":", 1)[1])
        elif line.startswith("DTEND"):
            end = parse_date(line.split(":", 1)[1])
        elif line.startswith("END:VEVENT") and start:
            ranges.append((start, end or start + timedelta(days=1)))
    today = date.today()
    ranges = sorted((s, e) for s, e in ranges if e > today)
    merged = []
    for s, e in ranges:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [[s.isoformat(), e.isoformat()] for s, e in merged]

failed = False
os.makedirs("availability", exist_ok=True)
for listing_id, secret in LISTINGS.items():
    url = os.environ.get(secret, "").strip()
    if not url:
        print(f"{listing_id}: secret {secret} absent, ignoré")
        continue
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "25Dayz-calendar-sync"})
        text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        if "BEGIN:VCALENDAR" not in text:
            raise ValueError("réponse qui n'est pas un calendrier iCal")
        ranges = ranges_from_ics(text)
    except Exception as exc:  # on garde l'ancien fichier en cas d'erreur
        print(f"{listing_id}: échec ({exc})")
        failed = True
        continue
    path = f"availability/{listing_id}.json"
    old = {}
    if os.path.exists(path):
        with open(path) as fh:
            old = json.load(fh)
    if old.get("booked") == ranges and old.get("updated"):
        print(f"{listing_id}: inchangé")
        continue
    with open(path, "w") as fh:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                   "booked": ranges}, fh, indent=1)
    print(f"{listing_id}: {len(ranges)} période(s) réservée(s)")

sys.exit(1 if failed else 0)
