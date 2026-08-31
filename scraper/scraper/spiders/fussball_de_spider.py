"""
Scrapy-Spider: fussball.de – Ergebnisse aus Torminuten rekonstruieren.

Vorgehen (gemäß Methodik der Bachelorarbeit):
  1. Für jede Spielplan-URL in START_URLS alle Links der Form
     https://www.fussball.de/spiel/... in Seitenreihenfolge einsammeln.
  2. Jede Spielseite parsen: Spieldatum aus dem <title> (dd-mm-yyyy),
     Teamnamen aus <section id="course-quick-view">,
     Tore aus dem Attribut data-match-events (div#rangescontainer, ebenfalls
     innerhalb von <section id="course-quick-view">). Dort steht der komplette
     Spielverlauf als Ereignisliste, z. B.
        {'time':'6','type':'goal','team':'home'}
     Gezählt werden alle Ereignisse mit type == "goal", getrennt nach
     team == "home" / "away". Elfmeter und Eigentore werden auf fussball.de
     nicht gesondert kodiert, tragen also denselben type und werden damit
     automatisch korrekt mitgezählt. Dieser Indikator ist robuster als die
     früher genutzten Torminuten im goals-Div, weil er nicht davon abhängt,
     dass Torschützen eingetragen wurden.
  3. Fehlt <section id="course-quick-view"> bzw. das Attribut
     data-match-events, wird als Ergebnis der Platzhalter "NA" eingetragen.
  4. Liga/Saison werden aus dem Spielplan-Link geparst.
  5. Jedes Item trägt league_index/match_index (Chronologie der
     Spielplanseite), sodass die Reihenfolge unabhängig von Scrapys
     asynchroner Abarbeitung rekonstruierbar bleibt (siehe Hinweis unten).

Start (aus dem Ordner scraper/, Ausgabedatei frei wählbar über -O):
    scrapy crawl fussballde_ergebnisse -O ../data/scraped/passender_dateiname.csv

Für einen neuen Datensatz einfach START_URLS unten anpassen und den Befehl
mit passendem Dateinamen erneut ausführen. Die Spider schreibt KEINE Datei
selbst – die Ausgabe kommt ausschließlich aus Scrapys -O/-o-Feed. Zielort ist
data/scraped/ (gescrapte reale Daten, per .gitignore vom Repo ausgeschlossen).
"""

import re
from urllib.parse import urlparse

import scrapy

# ----------------------------------------------------------------------------
# Konfiguration  — HIER die Spielplan-URL(s) fuer den gewuenschten Datensatz
# eintragen, dann (aus dem Ordner scraper/):
#   scrapy crawl fussballde_ergebnisse -O ../data/scraped/<name>.csv
# ----------------------------------------------------------------------------

# 36 Saisons aus verschiedenen Verbänden (Westfalen, Berlin, Südwest (Bayern), Sachsen-Anhalt) 
START_URLS = [
    "https://www.fussball.de/spielplan/iga-2027-landesliga-staffel-1-westfalen-landesliga-herren-saison2526-westfalen/-/staffel/02SVESAFO8000002VS5489BTVT4MI2QN-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/iga-2027-landesliga-staffel-2-westfalen-landesliga-herren-saison2526-westfalen/-/staffel/02SVESAGGO000007VS5489BTVT4MI2QN-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/iga-2027-landesliga-staffel-3-westfalen-landesliga-herren-saison2526-westfalen/-/staffel/02SVESAHA8000005VS5489BTVT4MI2QN-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/iga-2027-landesliga-staffel-4-westfalen-landesliga-herren-saison2526-westfalen/-/staffel/02SVESAI3C00000GVS5489BTVT4MI2QN-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/iga-2027-landesliga-staffel-1-westfalen-landesliga-herren-saison2425-westfalen/-/staffel/02PMQKH29G000017VS5489B4VT1N8HH9-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/iga-2027-landesliga-staffel-2-westfalen-landesliga-herren-saison2425-westfalen/-/staffel/02PMQKH2OC00000LVS5489B4VT1N8HH9-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/iga-2027-landesliga-staffel-3-westfalen-landesliga-herren-saison2425-westfalen/-/staffel/02PMQKH38O00001IVS5489B4VT1N8HH9-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/iga-2027-landesliga-staffel-4-westfalen-landesliga-herren-saison2425-westfalen/-/staffel/02PMQKH3P4000016VS5489B4VT1N8HH9-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/landesliga-staffel-1-westfalen-landesliga-herren-saison2324-westfalen/-/staffel/02M95J83BO000000VS5489B4VSAUO6GA-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/landesliga-staffel-2-westfalen-landesliga-herren-saison2324-westfalen/-/staffel/02M95J83PS00001HVS5489B4VSAUO6GA-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/landesliga-staffel-3-westfalen-landesliga-herren-saison2324-westfalen/-/staffel/02M95J8450000000VS5489B4VSAUO6GA-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/landesliga-staffel-4-westfalen-landesliga-herren-saison2324-westfalen/-/staffel/02M95J84F8000016VS5489B4VSAUO6GA-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/landesliga-staffel-1-westfalen-landesliga-herren-saison2223-westfalen/-/staffel/02I7BC18FC000017VS5489B4VV6D53L9-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/landesliga-staffel-2-westfalen-landesliga-herren-saison2223-westfalen/-/staffel/02I7BC18QO00001IVS5489B4VV6D53L9-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/landesliga-staffel-3-westfalen-landesliga-herren-saison2223-westfalen/-/staffel/02I7BC197400001HVS5489B4VV6D53L9-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/landesliga-staffel-4-westfalen-landesliga-herren-saison2223-westfalen/-/staffel/02I7BC19HO000018VS5489B4VV6D53L9-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-st1-berlin-landesliga-herren-saison2526-berlin/-/staffel/02TH61PSMK000005VS5489BTVTLPPK10-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-st2-berlin-landesliga-herren-saison2526-berlin/-/staffel/02TH61PSRC000006VS5489BTVTLPPK10-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-st1-berlin-landesliga-herren-saison2425-berlin/-/staffel/02PQ3I3GE0000006VS5489B3VT0HF02K-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-st2-berlin-landesliga-herren-saison2425-berlin/-/staffel/02PQ3I3GK4000006VS5489B3VT0HF02K-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-st1-berlin-landesliga-herren-saison2324-berlin/-/staffel/02M7480S2O000006VS5489B4VSAUO6GA-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-st2-berlin-landesliga-herren-saison2324-berlin/-/staffel/02M7480S6S000006VS5489B4VSAUO6GA-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-st1-berlin-landesliga-herren-saison2223-berlin/-/staffel/02I8UIH034000006VS5489B3VU9O46OC-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-st2-berlin-landesliga-herren-saison2223-berlin/-/staffel/02I8UIH08C000005VS5489B3VU9O46OC-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-ost-suedwest-landesliga-herren-saison2526-suedwest/-/staffel/02TGQ3DK7800000AVS5489BTVTLPPK10-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-west-suedwest-landesliga-herren-saison2526-suedwest/-/staffel/02TH847CAG000005VS5489BUVS7GO5S8-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-ost-suedwest-landesliga-herren-saison2425-suedwest/-/staffel/02PPQS990G000009VS5489B4VSOV4IQ0-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-west-suedwest-landesliga-herren-saison2425-suedwest/-/staffel/02PQOI0NK0000004VS5489B3VSK4BA2V-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-ost-suedwest-landesliga-herren-saison2324-suedwest/-/staffel/02M6HPPVV8000007VS5489B4VSAUO6GA-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-west-suedwest-landesliga-herren-saison2324-suedwest/-/staffel/02M48I9N6G000004VS5489B3VTVUJRS3-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-ost-suedwest-landesliga-herren-saison2223-suedwest/-/staffel/02IJ1KLO3G000004VS5489B3VVETK79U-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/herren-landesliga-west-suedwest-landesliga-herren-saison2223-suedwest/-/staffel/02IH0QF19G000004VS5489B3VS27R2HJ-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/lotto-landesliga-nord-sachsen-anhalt-landesliga-herren-saison2526-sachsen-anhalt/-/staffel/02THS12V78000004VS5489BUVVSMDEIN-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/lotto-landesliga-sued-sachsen-anhalt-landesliga-herren-saison2526-sachsen-anhalt/-/staffel/02THS15PPK000004VS5489BUVVSMDEIN-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/lotto-landesliga-nord-sachsen-anhalt-landesliga-herren-saison2425-sachsen-anhalt/-/staffel/02PR0FHAM8000000VS5489B3VSK4BA2V-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/lotto-landesliga-sued-sachsen-anhalt-landesliga-herren-saison2425-sachsen-anhalt/-/staffel/02PR0FHAUS000005VS5489B3VSK4BA2V-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/bfv-landesliga-mittelbaden-baden-landesliga-herren-saison2526-baden/-/staffel/02TGQ5ND2S00000FVS5489BTVTLPPK10-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/bfv-landesliga-odenwald-baden-landesliga-herren-saison2526-baden/-/staffel/02TGQ5NCFC00000GVS5489BTVTLPPK10-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/bfv-landesliga-rhein-neckar-baden-landesliga-herren-saison2526-baden/-/staffel/02TGQ5NCSC00000BVS5489BTVTLPPK10-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/bfv-landesliga-mittelbaden-baden-landesliga-herren-saison2425-baden/-/staffel/02PPEJOUL400000HVS5489B4VSOV4IQ0-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/bfv-landesliga-odenwald-baden-landesliga-herren-saison2425-baden/-/staffel/02PPEJOU2400000GVS5489B4VSOV4IQ0-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/bfv-landesliga-rhein-neckar-baden-landesliga-herren-saison2425-baden/-/staffel/02PPEJOUCC00000EVS5489B4VSOV4IQ0-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/bfv-landesliga-mittelbaden-baden-landesliga-herren-saison2324-baden/-/staffel/02M5LMHL6G00000HVS5489B4VSAUO6GA-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/bfv-landesliga-odenwald-baden-landesliga-herren-saison2324-baden/-/staffel/02M5LMHKRK00000FVS5489B4VSAUO6GA-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/bfv-landesliga-rhein-neckar-baden-landesliga-herren-saison2324-baden/-/staffel/02M5LMHL1O00000IVS5489B4VSAUO6GA-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/bfv-landesliga-mittelbaden-baden-landesliga-herren-saison2223-baden/-/staffel/02IHMERVPO000004VS5489B4VUIHV7I0-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/bfv-landesliga-odenwald-baden-landesliga-herren-saison2223-baden/-/staffel/02IHLV321G000003VS5489B4VUIHV7I0-G#!/section/matchplan",
    "https://www.fussball.de/spielplan/bfv-landesliga-rhein-neckar-baden-landesliga-herren-saison2223-baden/-/staffel/02IHMCJ1U8000004VS5489B4VUIHV7I0-G#!/section/matchplan",
]

PLACEHOLDER = "NA"  # Ergebnis-Platzhalter, wenn course-quick-view fehlt

# Reihenfolge der Spalten in der Ausgabe-CSV (stabil, unabhaengig von der
# dict-Reihenfolge im Item). Chronologie steckt in league_index/match_index.
FIELDS = [
    "liga",
    "saison",
    "date",
    "home_team",
    "away_team",
    "home_goals",
    "away_goals",
    # Halbzeitstand aus span.half-result – steht als EINZIGE Ergebnisangabe im
    # Klartext auf der Seite (Endstand und Spielplan-Datum sind verschleiert).
    # Dient als unabhaengige Gegenprobe: ein Halbzeitstand groesser als der aus
    # Torereignissen rekonstruierte Endstand ist logisch unmoeglich und
    # entlarvt Partien ohne Torereignisse (z. B. am gruenen Tisch gewertet).
    "home_goals_ht",
    "away_goals_ht",
    "liga_slug",
    "staffel_id",
    "league_index",
    "match_index",
    # match_url bewusst als LETZTE Spalte: steht die URL mittendrin, zieht die
    # Linkerkennung von Editoren den Rest der Zeile (Komma + Folgespalten) mit
    # in den Link, und fussball.de liefert dann mit Status 200 eine
    # Fehlerseite statt der Spielseite.
    "match_url",
]

# ----------------------------------------------------------------------------
# Regex-Bausteine
# ----------------------------------------------------------------------------

# Ein einzelnes Ereignis-Objekt aus data-match-events, z. B.
#   {'time':'6','type':'goal','team':'home'}
# Durch [^{}]* greift der Ausdruck nur die innersten Objekte (die Ereignisse),
# nicht die umschließende Struktur ('first-half', 'second-half', ...).
EVENT_RE = re.compile(r"\{[^{}]*\}")

# Schlüssel/Wert-Paare innerhalb eines Ereignisses (einfache Anführungszeichen).
EVENT_KV_RE = re.compile(r"'([\w-]+)'\s*:\s*'([^']*)'")

# Ereignistyp, der als Tor zählt.
GOAL_TYPE = "goal"

# Saison aus dem URL-Slug: "saison2526" -> 2025/26
SEASON_RE = re.compile(r"saison(\d{2})(\d{2})")

# Staffel-ID aus dem Pfad ".../staffel/<ID>-G"
STAFFEL_RE = re.compile(r"/staffel/([A-Z0-9]+)-G")

# Spieldatum aus dem <title> der Spielseite, z. B.
#   "SC Westfalia Herne - Königsborner SV Ergebnis: Landesliga - Herren - 21.04.2024"
# Der Titel ist die einzige Klartext-Quelle fuer das Datum: in der Spielplan-
# tabelle (td.column-date) und beim Endstand ist es per data-obfuscation
# verschleiert.
TITLE_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")

# Halbzeitstand aus <span class="half-result">[5 : 1]</span>
HALFTIME_RE = re.compile(r"(\d+)\s*:\s*(\d+)")


def parse_halftime(text: str) -> tuple:
    """
    Liest den Halbzeitstand aus dem Text von span.half-result ("[5 : 1]").

    Rueckgabe: (home, away) als int, oder (PLACEHOLDER, PLACEHOLDER), wenn die
    Seite keinen Halbzeitstand ausweist. Anders als der Endstand steht dieser
    Wert im Klartext im HTML und ist deshalb von den Torereignissen unabhaengig.
    """
    m = HALFTIME_RE.search(text or "")
    if not m:
        return PLACEHOLDER, PLACEHOLDER
    return int(m.group(1)), int(m.group(2))


def parse_date(title: str) -> str:
    """
    Zieht das Spieldatum aus dem Seitentitel und gibt es als dd-mm-yyyy zurueck;
    ohne Treffer den Platzhalter.

    Das Datum ist die maßgebliche Groesse fuer die chronologische Reihenfolge
    (match_number im long_df): der
    nominelle Spieltag taugt wegen Nachhol- und Vorverlegungsterminen nicht.

    Hinweis fuer die Aufbereitung: dd-mm-yyyy ist NICHT als Text sortierbar,
    also vor dem Sortieren umwandeln:
        pd.to_datetime(df["date"], format="%d-%m-%Y")
    """
    m = TITLE_DATE_RE.search(title or "")
    if not m:
        return PLACEHOLDER
    tag, monat, jahr = m.groups()
    return f"{tag}-{monat}-{jahr}"


def parse_match_events(attr_text: str) -> list:
    """
    Parst das Attribut data-match-events zu einer Liste von Ereignis-Dicts.

    Das Attribut ist JSON-ähnlich, benutzt aber einfache Anführungszeichen und
    ist daher nicht direkt json-parsebar. Ausgewertet werden deshalb per Regex
    die innersten Objekte, z. B. {'time':'6','type':'goal','team':'home'}.
    """
    events = []
    for raw in EVENT_RE.findall(attr_text or ""):
        event = dict(EVENT_KV_RE.findall(raw))
        if "type" in event and "team" in event:
            events.append(event)
    return events


def count_goals(events: list) -> tuple:
    """
    Zählt Tore je Team aus den Ereignissen (type == "goal").

    Rückgabe: (home_goals, away_goals).
    """
    home = sum(1 for e in events if e["type"] == GOAL_TYPE and e["team"] == "home")
    away = sum(1 for e in events if e["type"] == GOAL_TYPE and e["team"] == "away")
    return home, away


def parse_league_info(spielplan_url: str) -> dict:
    """Extrahiert Liga-Slug, Saison, Verband und Staffel-ID aus dem Link."""
    path = urlparse(spielplan_url).path
    # Pfad: /spielplan/<slug>/-/staffel/<ID>-G
    parts = [p for p in path.split("/") if p]
    slug = parts[1] if len(parts) > 1 and parts[0] == "spielplan" else ""

    season = ""
    m = SEASON_RE.search(slug)
    if m:
        season = f"20{m.group(1)}/{m.group(2)}"

    staffel_id = ""
    m = STAFFEL_RE.search(path)
    if m:
        staffel_id = m.group(1)

    # Liga-Name = Slug ohne "saisonXXYY"-Teil und ohne Verbands-Suffix.
    # Der volle Slug bleibt als eindeutige Referenz erhalten.
    liga = slug
    m = SEASON_RE.search(slug)
    if m:
        liga = slug[: m.start()].rstrip("-")

    return {
        "liga_slug": slug,       # vollständig, eindeutig
        "liga": liga,            # lesbarer Teil vor "saison..."
        "saison": season,        # z. B. "2025/26"
        "staffel_id": staffel_id,
    }


# ----------------------------------------------------------------------------
# Spider
# ----------------------------------------------------------------------------


class FussballDeSpider(scrapy.Spider):
    name = "fussballde_ergebnisse"

    # Feste Spaltenreihenfolge fuer den -O/-o-Feed. KEIN eigener Dateiname
    # hier – die Zieldatei bestimmt der Aufruf via -O <name>.csv.
    custom_settings = {"FEED_EXPORT_FIELDS": FIELDS}

    async def start(self):
        for league_index, url in enumerate(START_URLS):
            yield scrapy.Request(
                url,
                callback=self.parse_spielplan,
                meta={
                    "league_index": league_index,
                    "league_info": parse_league_info(url),
                },
            )

    # ------------------------------------------------------------------
    # 1) Spielplanseite: Spiellinks in Seitenreihenfolge einsammeln
    # ------------------------------------------------------------------
    def parse_spielplan(self, response):
        league_index = response.meta["league_index"]
        league_info = response.meta["league_info"]

        seen = set()
        ordered_links = []
        for href in response.css("a::attr(href)").getall():
            url = response.urljoin(href)
            if "/spiel/" not in urlparse(url).path:
                continue
            if url in seen:
                continue
            seen.add(url)
            ordered_links.append(url)

        if not ordered_links:
            self.logger.warning(
                "Keine /spiel/-Links auf %s gefunden. Vermutlich wird der "
                "Spielplan per JavaScript/AJAX nachgeladen (#!-Fragment) – "
                "siehe Hinweis am Ende des Skripts.",
                response.url,
            )

        for match_index, link in enumerate(ordered_links):
            yield scrapy.Request(
                link,
                callback=self.parse_match,
                meta={
                    "league_index": league_index,
                    "league_info": league_info,
                    "match_index": match_index,
                    "spielplan_url": response.url,
                },
            )

    # ------------------------------------------------------------------
    # 2) Spielseite: Teamnamen + Ergebnis aus data-match-events
    # ------------------------------------------------------------------
    def parse_match(self, response):
        league_info = response.meta["league_info"]

        # Datum aus dem Titel – unabhaengig davon, ob es die Spielverlaufs-
        # Section gibt (abgesagte Spiele haben trotzdem einen Termin).
        date = parse_date(response.css("title::text").get())

        # Halbzeitstand aus dem Klartext-Element – unabhaengig von den
        # Torereignissen und damit die Gegenprobe zum rekonstruierten Endstand.
        home_goals_ht, away_goals_ht = parse_halftime(
            response.css("span.half-result::text").get()
        )

        section = response.css("section#course-quick-view")

        home_team = away_team = PLACEHOLDER
        home_goals = away_goals = PLACEHOLDER

        if section:
            home_team = self._club_name(section.css("div.info-home"))
            away_team = self._club_name(section.css("div.info-away"))

            # Ergebnis aus dem Spielverlauf (data-match-events) statt aus den
            # Torminuten – unabhängig davon, ob Torschützen erfasst wurden.
            attr_text = section.css("[data-match-events]::attr(data-match-events)").get()
            if attr_text:
                home_goals, away_goals = count_goals(parse_match_events(attr_text))
            else:
                self.logger.warning(
                    "Kein data-match-events-Attribut auf %s – Ergebnis bleibt "
                    "'%s'.",
                    response.url,
                    PLACEHOLDER,
                )
        else:
            # Ergebnis-Platzhalter laut Vorgabe; Teamnamen versuchen wir
            # ersatzweise aus dem Seitenkopf zu ziehen (Selektor ggf. an
            # echter Seite verifizieren).
            fallback_names = [
                t.strip()
                for t in response.css(".team-name::text").getall()
                if t.strip()
            ]
            if len(fallback_names) >= 2:
                home_team, away_team = fallback_names[0], fallback_names[1]

        # Item wird direkt an Scrapys Feed (-O/-o) uebergeben – kein eigener
        # CSV-Writer mehr. Chronologie ueber league_index/match_index.
        yield {
            "league_index": response.meta["league_index"],
            "match_index": response.meta["match_index"],
            "liga": league_info["liga"],
            "liga_slug": league_info["liga_slug"],
            "saison": league_info["saison"],
            "date": date,
            "staffel_id": league_info["staffel_id"],
            "home_team": home_team,
            "away_team": away_team,
            "home_goals_ht": home_goals_ht,
            "away_goals_ht": away_goals_ht,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "match_url": response.url,
        }

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------
    @staticmethod
    def _club_name(block) -> str:
        name = block.css("div.club-name::text").get(default="").strip()
        return name or PLACEHOLDER


# ----------------------------------------------------------------------------
# Reihenfolge der Ausgabe:
# Scrapy schreibt Items in der Reihenfolge, in der sie fertig gescrapt werden
# (asynchron) – NICHT zwingend chronologisch. Die Spielplan-Chronologie steckt
# aber in den Spalten league_index/match_index; zum chronologischen Sortieren
# in der Weiterverarbeitung schlicht:
#     df.sort_values(["league_index", "match_index"])
#
# WICHTIGER HINWEIS (bitte vor dem ersten vollen Lauf prüfen):
#
# Die Spielplan-URLs enthalten ein "#!"-Fragment. Fragmente werden NICHT an
# den Server gesendet. Falls die Spieltabelle clientseitig per AJAX geladen
# wird, enthält das rohe HTML der Spielplanseite keine /spiel/-Links, und
# dieser Spider loggt die obige Warnung. Prüfen mit:
#
#     scrapy shell "https://www.fussball.de/spielplan/...-G"
#     >>> response.css('a[href*="/spiel/"]').getall()
#
# Liefert das nichts, gibt es zwei Wege:
#   a) den AJAX-Endpunkt identifizieren (DevTools -> Netzwerk-Tab beim
#      Blättern durch Spieltage) und diesen direkt anfragen, oder
#   b) scrapy-playwright einsetzen, um die Seite zu rendern.
#
# Außerdem zeigen Spielplanseiten oft nur einen Ausschnitt (z. B. einen
# Spieltag); für die ganze Saison muss ggf. über Spieltage iteriert werden.
# ----------------------------------------------------------------------------
