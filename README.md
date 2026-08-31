# Leistungsstärke im Sport — Autokorrelationsanalyse der Tordifferenz

Code zur Bachelorarbeit. Untersucht wird, wie konstant die relative
Leistungsstärke eines Teams über eine Saison ist. Da der Zufall Einzelergebnisse
dominiert, geschieht das indirekt über die **Autokorrelationsfunktion (ACF) der
um den Heimvorteil bereinigten Tordifferenz**:

```
K(Δm) = E[ X_ij(m) · X_ij(m+Δm) ] ≈ E[ S_i,m · S_i,m+Δm ]
```

An die ACF wird `K(Δm) = a + b·exp(−Δm/τ)` gefittet: `a` ist der zeitlich
konstante Anteil der Stärke, `b·exp(−Δm/τ)` die abklingende Formphase. Die
vollständige Herleitung steht im Text der Bachelorarbeit.

## Hinweis zu den Daten

**Die empirischen Datensätze werden in diesem Repository nicht zur Verfügung
gestellt.** Die Rechte an ihnen sind nicht übertragbar; sie sind per
`.gitignore` ausgeschlossen (`data/raw/`, `data/scraped/`, `data/acf-ready/`).
Im Repo liegen ausschließlich **synthetische** Datensätze (`data/simulated/`),
der als Simulationsgerüst genutzte Spielplan (`data/schedule/`) sowie die
aggregierten Ergebnisse in `results/` und `figures/`.

Aus demselben Grund ist auch die **Datenaufbereitung** (Rohdaten → `long_df`)
nicht Teil des Repositorys: ihre Zwischenausgaben zeigen die Daten selbst. Der
hier veröffentlichte Code setzt deshalb **beim fertigen `long_df` an** — dem
Format, das im nächsten Abschnitt beschrieben ist.

Die Notebooks zur Simulation und zur ACF auf simulierten Daten laufen dadurch
ohne weitere Voraussetzungen. Die Notebooks zu den echten Datensätzen erwarten
eine passende CSV unter `data/acf-ready/`; der Dateiname steht jeweils als
`DATA_FILE` in der Setup-Zelle.

## Eingangsformat: `long_df`

Ein Team pro Spiel und Zeile — jedes Spiel erscheint also zweimal, einmal je
Perspektive.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `season_id` | str | eindeutige Saison-ID |
| `date` | datetime | Datum des Spiels (nur zur Nachvollziehbarkeit) |
| `team_id` | int | ID des betrachteten Teams, nur innerhalb einer Saison eindeutig |
| `opponent_id` | int | ID des Gegners, gleiche Kodierung |
| `X` | float | **um den Heimvorteil `2h` bereinigte** Tordifferenz aus Sicht von `team_id` |
| `is_home` | bool | True, falls `team_id` Heimteam war |
| `match_number` | int | chronologischer Spielindex innerhalb der Saison, beginnend bei 0 |

Zwei Voraussetzungen, auf die sich der ACF-Code verlässt:

- **`X` ist bereits bereinigt.** Der Heimvorteil wird saisonweise als Mittelwert
  der Tordifferenz aus Heimsicht geschätzt und abgezogen. Ohne diesen Schritt
  erzeugt der Heim-/Auswärtswechsel ein Zick-Zack-Muster in der ACF.
- **Die Zeilen sind sortiert** nach `["season_id", "team_id", "date"]`.
  `compute_acf` liest `match_number` nicht, sondern nutzt die Reihenfolge der
  Zeilen innerhalb jeder Team-Saison.

Die simulierten Datensätze in `data/simulated/` erfüllen dasselbe Schema —
deshalb läuft derselbe ACF-Code unverändert auf echten und simulierten Daten.

## Hinweis zur Nutzung von KI

Für das Programmieren wurde das KI-Sprachmodell Claude (Anthropic) als
Hilfsmittel eingesetzt. Der Code wurde vollständig von mir geprüft und
nachvollzogen. Diese README-File wurde von der KI generiert.

## Installation und Ausführung

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .        # macht `import acf_analysis` verfügbar
.venv/bin/jupyter lab                        # Notebooks öffnen
```

Getestet mit Python 3.14 (`pyproject.toml` verlangt ≥ 3.11). Jedes Notebook ist
von oben nach unten ausführbar und läuft jeweils unter einer Minute.
Reihenfolge:

1. `notebooks/02_simulation/simulation.ipynb` — erzeugt `data/simulated/*.csv`
2. `notebooks/03_acf/acf_simulated_data.ipynb` — ACF auf den simulierten Daten
   (Referenzverhalten der Szenarien)
3. `notebooks/03_acf/acf_amateur_fb.ipynb` und die übrigen ACF-Notebooks — ACF
   der echten Datensätze; setzt ein eigenes `long_df` unter `data/acf-ready/`
   voraus (siehe oben)

## Aufbau

```
src/acf_analysis/   ACF-Logik: compute_acf, bin_acf, fit_acf, plot_acf
notebooks/
  01_dataprep/      Aufbereitung und Bereitstellung der Daten im Long-Format
                    (Nicht Teil des Repos)
  02_simulation/    Simulationspipeline (Logik bewusst inline im Notebook)
  03_acf/           ACF-Auswertung je Datensatz
scraper/            Scrapy-Projekt zur Beschaffung des Amateurdatensatzes
data/               Datensätze als CSV (siehe Hinweis zu den Daten)
results/, figures/  Ergebnistabellen und Abbildungen der Arbeit
```

Die Modularisierung folgt einer Regel: **Logik, die auf echten *und*
simulierten Daten läuft, liegt in einem Modul** — deshalb steht die ACF in
`src/acf_analysis/` und wird von allen Notebooks importiert statt dupliziert.
Die Simulation läuft nur an einer einzigen Stelle und bleibt deshalb bewusst
inline im Notebook sichtbar.
