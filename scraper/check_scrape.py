"""
Vollstaendigkeitspruefung fuer die gescrapten Spielplaene.

Prueft je Saison/Staffel, ob der Lauf lueckenlos war – gedacht als Pflichtschritt
nach jedem grossen Crawl, bevor die Daten in die Aufbereitung gehen:

  1. Fehlende Spiele: match_index muss 0..N-1 lueckenlos abdecken.
  2. Doppelrunde: bei n Teams sind n*(n-1) Spiele zu erwarten, und jedes Team
     spielt (n-1)-mal heim und (n-1)-mal auswaerts.
  3. Ergebnis-Platzhalter "NA" (Spielseite ohne data-match-events).
  4. Doppelte match_url (dieselbe Spielseite mehrfach im Datensatz).
  5. Halbzeitstand groesser als Endstand – logisch unmoeglich und damit ein
     harter Beleg fuer ein falsches Ergebnis (siehe unten).

Zu Punkt 5: der Endstand wird aus den Torereignissen rekonstruiert, der
Halbzeitstand steht dagegen im Klartext auf der Seite. Partien ohne erfasste
Torereignisse (abgebrochen, am gruenen Tisch gewertet) landen deshalb als 0:0
im Datensatz, obwohl die Seite einen Halbzeitstand ausweist. Diese Zeilen
gehoeren vor der Aufbereitung verworfen.

Aufruf:
    python check_scrape.py ../data/scraped/*.csv

Exit-Code 0 = alles sauber, 1 = mindestens ein Befund. Befunde heissen nicht
zwingend "Fehler": abgebrochene Saisons (z. B. 2019/20) oder Staffeln mit
Auf-/Abstiegsrunden weichen legitim von der Doppelrunden-Erwartung ab.
"""

import sys

import pandas as pd

PLACEHOLDER = "NA"


def check_group(key, df) -> list:
    """Prueft eine (liga_slug, saison)-Gruppe und gibt gefundene Befunde zurueck."""
    findings = []

    # 1. Luecken in der Spielplan-Reihenfolge
    idx = sorted(df["match_index"].astype(int))
    expected_idx = set(range(len(idx)))
    missing = sorted(expected_idx - set(idx))
    if missing:
        findings.append(
            f"{len(missing)} fehlende match_index-Positionen, z. B. {missing[:10]}"
        )

    # 2. Doppelrunde: n Teams -> n*(n-1) Spiele, je (n-1) heim und auswaerts
    teams = set(df["home_team"]) | set(df["away_team"])
    teams.discard(PLACEHOLDER)
    n = len(teams)
    expected_games = n * (n - 1)
    if len(df) != expected_games:
        findings.append(
            f"{len(df)} Spiele, erwartet {expected_games} bei {n} Teams "
            f"(Differenz {len(df) - expected_games:+d})"
        )

    home_counts = df["home_team"].value_counts()
    away_counts = df["away_team"].value_counts()
    unbalanced = []
    for team in sorted(teams):
        h, a = int(home_counts.get(team, 0)), int(away_counts.get(team, 0))
        if h != n - 1 or a != n - 1:
            unbalanced.append(f"{team} ({h}H/{a}A)")
    if unbalanced:
        # Nur eine Zeile, sonst erschlaegt ein unvollstaendiger Lauf die Ausgabe.
        beispiele = ", ".join(unbalanced[:3])
        rest = f", … (+{len(unbalanced) - 3})" if len(unbalanced) > 3 else ""
        findings.append(
            f"{len(unbalanced)} Teams mit falscher Heim-/Auswaertszahl "
            f"(erwartet je {n - 1}): {beispiele}{rest}"
        )

    # 3. Platzhalter statt Ergebnis
    na = (df["home_goals"].astype(str) == PLACEHOLDER).sum()
    if na:
        findings.append(f"{na} Spiele ohne Ergebnis ('{PLACEHOLDER}')")

    # 4. Doppelte Spielseiten
    dupes = df["match_url"].duplicated().sum()
    if dupes:
        findings.append(f"{dupes} doppelte match_url")

    # 5. Halbzeitstand > Endstand -> Ergebnis nachweislich falsch
    for url in impossible_halftime(df):
        findings.append(f"Halbzeitstand groesser als Endstand: {url}")

    return findings


def impossible_halftime(df) -> list:
    """
    Gibt die match_urls zurueck, deren Halbzeitstand ueber dem Endstand liegt.

    Beide Werte stammen aus unabhaengigen Quellen (Endstand aus den
    Torereignissen, Halbzeitstand aus dem Klartext der Seite), deshalb ist die
    Abweichung ein harter Fehlerbeleg und keine Ermessensfrage. Fehlt eine der
    Angaben (Platzhalter "NA"), ist kein Vergleich moeglich und die Zeile wird
    uebersprungen.
    """
    if "home_goals_ht" not in df.columns:
        return []   # aeltere Scrapes ohne Halbzeitspalten

    num = {c: pd.to_numeric(df[c], errors="coerce")
           for c in ("home_goals", "away_goals", "home_goals_ht", "away_goals_ht")}
    unmoeglich = (num["home_goals_ht"] > num["home_goals"]) | (
        num["away_goals_ht"] > num["away_goals"]
    )
    return df.loc[unmoeglich.fillna(False), "match_url"].tolist()


def main(paths) -> int:
    frames = []
    for p in paths:
        # keep_default_na=False: der Platzhalter "NA" soll die Zeichenkette
        # "NA" bleiben und nicht als NaN gelesen werden – sonst mischen sich
        # Floats unter die Teamnamen und die Platzhalter-Zaehlung geht fehl.
        d = pd.read_csv(p, keep_default_na=False)
        d["_datei"] = p
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)

    problems = 0
    for key, grp in df.groupby(["liga_slug", "saison"], dropna=False):
        findings = check_group(key, grp)
        status = "OK  " if not findings else "PRUE"
        teams = len((set(grp["home_team"]) | set(grp["away_team"])) - {PLACEHOLDER})
        print(f"{status} {key[1]:>9}  {key[0][:48]:48} {len(grp):>4} Spiele, {teams:>2} Teams")
        for f in findings:
            print(f"       - {f}")
        problems += bool(findings)

    print(f"\n{len(df)} Spiele gesamt, {df.groupby(['liga_slug', 'saison']).ngroups} "
          f"Saison/Staffel-Kombinationen, {problems} mit Befund")
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Aufruf: python check_scrape.py <csv> [<csv> ...]")
    sys.exit(main(sys.argv[1:]))
