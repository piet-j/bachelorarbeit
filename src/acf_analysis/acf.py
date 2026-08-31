"""ACF der bereinigten Tordifferenz X: Berechnung, Fit und Binning.

Zentrale, importierbare Logik fuer die Autokorrelationsanalyse.
Derselbe Code laeuft unveraendert auf simulierten UND echten
long_df-Datensaetzen -- die Notebooks importieren nur diese Funktionen, statt sie
erneut zu implementieren.

Enthaelt:
    compute_acf(df, max_lag=None)   -> acf_df [lag, K, N, S, SQ, s2, sigma]
    acf_model(d, a, b, tau)         -> Fit-Modell mit freier Abklingzeit
    acf_model_tau7(d, a, b)         -> Fit-Modell mit fixer Abklingzeit tau=7
    fit_acf(acf_df)                 -> FitResult (freier Fit + Fit mit tau=7)
    bin_acf(acf_df, n_min=9000)     -> bins_df [lag_bin, K_bin, N_bin, sigma_bin, lags_merged]
    plot_acf(bins_df, result, ...)  -> Achse mit gebinnten Punkten + einer Fit-Kurve
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit


def compute_acf(df, max_lag=None):
    """Empirische ACF K(Delta m) der bereinigten Tordifferenz X.

    Einheit ist die Team-Saison (Gruppierung ["season_id","team_id"]) -> Within-Season-Regel.
    Je Lag d werden nur drei laufende Summen akkumuliert (N, S, SQ), keine Einzelprodukte.
    Ausschlussregel: Paare mit gleichem Gegner (opponent_id[m]==opponent_id[m+d]) entfallen.
    Rueckgabe: DataFrame [lag, K, N, S, SQ, s2, sigma] fuer alle Lags d = 1..max_lag.
    """
    groups = df.groupby(["season_id", "team_id"], sort=False)
    if max_lag is None:                                        # Wird für die Lag-Achse 0..max_lag des jeweiligen Datensatzes benötigt
        max_lag = int(groups.size().max()) - 1
    N  = np.zeros(max_lag + 1, dtype=np.int64)
    S  = np.zeros(max_lag + 1)
    SQ = np.zeros(max_lag + 1)
    for _, g in groups:
        X   = g["X"].to_numpy(dtype=float)
        opp = g["opponent_id"].to_numpy()
        n = len(X)
        for d in range(1, min(max_lag, n - 1) + 1):            # Anzahl der Teams pro Saison variiert, jede Saison steuert mit maximal möglichem Lag bei
            valid = opp[:-d] != opp[d:]                        
            prod  = (X[:-d] * X[d:])[valid]                    # Ausschlussregel als Boolsche Maske
            N[d]  += prod.size
            S[d]  += prod.sum()
            SQ[d] += np.square(prod).sum()
    lag = np.arange(max_lag + 1)
    with np.errstate(invalid="ignore", divide="ignore"):      # Lags ohne Paare -> Code läuft weiter, NaN wird gesetzt
        K  = S / N
        s2 = (SQ - N * K**2) / (N - 1)                         # Stichprobenvarianz der Produkte (Verschiebungsformel)
        sigma = np.sqrt(s2 / N)                                # Standardfehler des Mittels
    acf = pd.DataFrame({"lag": lag, "K": K, "N": N, "S": S, "SQ": SQ, "s2": s2, "sigma": sigma})
    return acf[acf["lag"] >= 1].reset_index(drop=True)         # Lag 0 (=Varianz) ist nicht Teil der ACF-Auswertung


def acf_model(d, a, b, tau):
    """Fit-Modell K(Delta m) = a + b*exp(-Delta m/tau)."""
    return a + b * np.exp(-d / tau)                            # Plateau a + exponentiell abklingende Formphase


def acf_model_tau7(d, a, b):
    """Gleiches Modell, aber tau auf den Literaturwert 7 festgelegt."""
    return a + b * np.exp(-d / 7.0)                            # nur a, b frei


@dataclass
class FitResult:
    """Ergebnis von fit_acf: freier Fit (a, b, tau) und Vergleichsfit mit fixem tau=7."""
    # --- Fit mit freier Abklingzeit tau ---
    a: float; b: float; tau: float                            # Parameter
    a_err: float; b_err: float; tau_err: float               # 1-sigma-Fehler
    chi2: float; dof: int; chi2_red: float                   # Guete
    corr_b_tau: float                                        # Korrelation von Amplitude und Abklingzeit
    # --- Vergleichsfit mit fixem tau = 7 ---
    a7: float; b7: float; a7_err: float; b7_err: float       # Parameter + Fehler
    chi2_7: float; dof7: int; chi2_red7: float               # Guete
    # --- verwendete Fit-Punkte (für Plot/Diagnose) ---
    d_fit: np.ndarray; K_fit: np.ndarray; sigma_fit: np.ndarray


def fit_acf(acf_df):
    """Gewichteter Least-Square-Fit von K(Delta m) auf allen individuellen Lags.

    Rechnet zwei Varianten: (1) freie Abklingzeit tau, (2) fixes tau = 7 (Literaturwert).
    Gewichtet mit der Spalte sigma; absolute_sigma=False -> nur relative Gewichtung, damit
    Lags mit wenigen Paaren (grosses sigma) weniger zählen (nach Rücksprache mit Prof. Heuer).
    Rueckgabe: FitResult.
    """
    # --- nur auswertbare Lags: endliches K, endliches sigma, sigma > 0 --------
    mask = np.isfinite(acf_df["K"]) & np.isfinite(acf_df["sigma"]) & (acf_df["sigma"] > 0)  # gueltige Fit-Punkte
    d_fit     = acf_df["lag"].to_numpy()[mask]                    # Lags Delta m (ALLE, ungebinnt)
    K_fit     = acf_df["K"].to_numpy()[mask]                      # K(Delta m)
    sigma_fit = acf_df["sigma"].to_numpy()[mask]                  # Standardfehler je Lag (fuer die Gewichtung)

    # --- Startwerte: Plateau aus dem Mittel der letzten Lags, Amplitude relativ dazu
    plateau_init   = np.mean(K_fit[-5:])                          # a-Startwert: Niveau bei grossen Delta m
    amplitude_init = K_fit[0] - plateau_init                      # b-Startwert: Abstand von K[0] zum Plateau
    param_init = [plateau_init, amplitude_init, 7.0]              # [a, b, tau]; 7.0 nur Startwert, NICHT fixiert

    # --- gewichteter Least-Square-Fit auf ALLEN individuellen Lags (keine Bins)
    # absolute_sigma=False -> nur RELATIVE Gewichtung: Punkte mit weniger Paaren (grosses sigma)
    # zaehlen im chi^2 weniger; der absolute Fehler ist hier nicht das Ziel (Vorgabe Betreuer).
    # curve_fit erwartet die Standardabweichungen sigma, NICHT die Gewichte 1/sigma^2.
    param_opt, param_cov = curve_fit(
        acf_model, d_fit, K_fit, p0=param_init,                   # Modell, x, y, Startwerte
        sigma=sigma_fit, absolute_sigma=False,                    # relative Gewichtung
        bounds=([-np.inf, -np.inf, 0.5], [np.inf, np.inf, 60.0]))  # tau positiv, physikalisch sinnvoll (0.5..60)
    param_err = np.sqrt(np.diag(param_cov))                       # 1-sigma-Fehler der Parameter
    a, b, tau = param_opt                                         # entpacken fuer die Ausgabe
    a_err, b_err, tau_err = param_err                             # zugehoerige Fehler

    residuals = (K_fit - acf_model(d_fit, *param_opt)) / sigma_fit  # gewichtete Residuen
    chi2 = np.sum(residuals**2)                                   # chi^2 = Summe der quadrierten Residuen
    dof  = len(d_fit) - 3                                         # Freiheitsgrade: Punkte minus 3 Parameter
    # b und tau kompensieren einander (kleineres b <-> groesseres tau) -> tendenziell korreliert:
    corr_b_tau = param_cov[1, 2] / (b_err * tau_err)             # Korrelationskoeffizient aus der Kovarianzmatrix

    # --- Vergleichsfit mit FIXER Abklingzeit tau = 7 (Literaturwert) ----------
    param_opt7, param_cov7 = curve_fit(                          # Fit mit zwei freien Parametern
        acf_model_tau7, d_fit, K_fit, p0=[plateau_init, amplitude_init],
        sigma=sigma_fit, absolute_sigma=False)                   # gleiche relative Gewichtung
    param_err7 = np.sqrt(np.diag(param_cov7))                    # Fehler von a, b
    residuals7 = (K_fit - acf_model_tau7(d_fit, *param_opt7)) / sigma_fit  # Residuen
    chi2_7 = np.sum(residuals7**2)                              # chi^2 der fixen Variante
    dof7 = len(d_fit) - 2                                       # Freiheitsgrade: Punkte minus 2 Parameter

    return FitResult(
        a=a, b=b, tau=tau, a_err=a_err, b_err=b_err, tau_err=tau_err,
        chi2=chi2, dof=dof, chi2_red=chi2 / dof, corr_b_tau=corr_b_tau,
        a7=param_opt7[0], b7=param_opt7[1], a7_err=param_err7[0], b7_err=param_err7[1],
        chi2_7=chi2_7, dof7=dof7, chi2_red7=chi2_7 / dof7,
        d_fit=d_fit, K_fit=K_fit, sigma_fit=sigma_fit)


def bin_acf(acf_df, n_min=9000):
    """Greedy-Binning grosser Lags -- NUR fuer die Darstellung.

    Aufsteigend in Delta m: Einzel-Lags mit N(d) >= n_min bleiben eigene Bins; ab dem ersten
    Lag mit N(d) < n_min werden benachbarte Lags akkumuliert, bis die kumulierte Paarzahl
    >= n_min ist. Reicht der Rest am Ende nicht, wird er in den vorherigen Bin gefaltet.
    Beide Koordinaten werden paarzahlgewichtet gemittelt (= Pooling aller Einzelprodukte des
    Bins). n_min ist ABSOLUT (9000), NICHT mit der Datensatzgroesse skalieren.
    """
    lag = acf_df["lag"].to_numpy()                            # Lags Delta m
    K   = acf_df["K"].to_numpy()                              # K(Delta m)
    N   = acf_df["N"].to_numpy()                              # Paarzahl N(Delta m)
    S   = acf_df["S"].to_numpy()                              # Summe der Produkte je Lag
    SQ  = acf_df["SQ"].to_numpy()                             # Summe der quadrierten Produkte je Lag

    # --- greedy: Lag-Indizes zu Bins gruppieren --------------------------
    bins, current, acc = [], [], 0                            # fertige Bins, aktueller Bin, kumulierte Paarzahl
    for i in range(len(lag)):                                 # Lags aufsteigend durchgehen
        current.append(i)                                    # Lag zum aktuellen Bin hinzufuegen
        acc += N[i]                                          # Paarzahl aufaddieren
        if acc >= n_min:                                     # genug Paare zusammen?
            bins.append(current)                             # Bin schliessen
            current, acc = [], 0                             # neuen Bin beginnen
    if current:                                              # unvollstaendiger Rest am Ende?
        bins[-1].extend(current)                             # in den vorherigen Bin falten (kein Rest-Bin)

    # --- je Bin aus den gepoolten Summen konsistent berechnen ------------
    rows = []                                                # eine Zeile je Bin
    for idx in bins:                                         # ueber alle Bins
        idx = np.asarray(idx)                                # Index-Array der enthaltenen Lags
        N_bin  = N[idx].sum()                                # gepoolte Paarzahl
        S_bin  = S[idx].sum()                                # gepoolte Produktsumme
        SQ_bin = SQ[idx].sum()                               # gepoolte Quadratsumme
        K_bin   = S_bin / N_bin                              # == sum(N*K)/sum(N): paarzahlgewichtetes Mittel
        lag_bin = (N[idx] * lag[idx]).sum() / N_bin          # paarzahlgewichteter x-Wert des Bins
        s2_bin  = (SQ_bin - N_bin * K_bin**2) / (N_bin - 1)  # Varianz der gepoolten Produkte
        sigma_bin = np.sqrt(s2_bin / N_bin)                  # Standardfehler des Bins
        rows.append({"lag_bin": lag_bin, "K_bin": K_bin, "N_bin": int(N_bin),
                     "sigma_bin": sigma_bin,
                     "lags_merged": tuple(int(lag[j]) for j in idx)})  # welche Lags zusammengefasst
    return pd.DataFrame(rows)                                # Bin-Tabelle


# --- Default-Achsenbeschriftungen (Fussball/simulierte Daten) -------------
# Sportartabhaengig: bei Volleyball ist Delta m in PARTIEN zu zaehlen (kein Spieltagsraster)
# und X ist eine Punktedifferenz, keine Tordifferenz. Deshalb sind die Labels Parameter.
XLABEL_DEFAULT = r"Lag $\Delta m$ (Spieltage)"                    # x-Achse: Lag in Spieltagen
YLABEL_DEFAULT = r"$K(\Delta m)\,/\,(a+b)$"                       # y-Achse: normierter ACF-Wert
POINT_LABEL_DEFAULT = "ACF (gebinnt, nur Darstellung)"            # Label der Datenpunkte (keine Legende per Default)


def plot_acf(bins_df, result, primary="free", ax=None, title=None,
             xlabel=XLABEL_DEFAULT, ylabel=YLABEL_DEFAULT, point_label=POINT_LABEL_DEFAULT,
             normalize=True):
    """Gebinnte ACF-Punkte mit Fehlerbalken + Fit-Kurve aus fit_acf (auf ungebinnten Lags).

    Das Binning dient NUR der Darstellung und geht NICHT in den Fit ein.

    Gezeichnet wird IMMER genau EINE Fit-Kurve, und zwar immer in Rot: welche der beiden
    Varianten (freie Abklingzeit oder fixer Literaturwert tau = 7), steuert `primary`. Die
    jeweils andere Variante wird bewusst nicht mitgezeichnet -- welcher Fit gezeigt wird,
    steht im Kurzbericht bzw. in der Ergebnistabelle des Notebooks. Ebenso stehen die
    Zahlenwerte der Fit-Parameter bewusst nicht in der Grafik (kein Legendenkasten), sondern
    werden im Notebook ausgegeben (print / Ergebnistabelle).

    Normierung: Punkte UND Kurve werden durch
    a + b = K_fit(0) geteilt, sodass die Fitkurve bei Delta m = 0 bei 1 startet. Der
    Fit selbst bleibt davon unberuehrt -- geteilt wird erst sein Ergebnis. Die
    Absolutwerte von K sind einheitenbehaftet (X^2, also Tore^2 bzw. Punkte^2) und
    zwischen Datensaetzen nicht vergleichbar; das normierte Plateau a/(a+b) dagegen
    schon: es ist der Anteil der saisonkonstanten Leistungsstaerke.

    Args:
        bins_df    : Ausgabe von bin_acf (gebinnte Punkte fuer die Darstellung).
        result     : FitResult aus fit_acf (Kurve aus dem Fit auf allen Lags).
        primary    : WELCHE Fit-Variante gezeichnet wird -- "free" -> freie Abklingzeit tau,
                     "tau7" -> fixer Literaturwert tau = 7 (fuer Szenarien ohne
                     identifizierbares tau, siehe Notebook-Anmerkung). Es wird stets nur
                     diese eine Kurve gezeigt, in Rot.
        ax         : optionale Achse (fuer Subplot-Gitter); sonst neue Figure.
        title      : optionaler Titel. Liegen mehrere Achsen in der Figur, wird
                     automatisch "(a) ", "(b) ", ... vorangestellt.
        xlabel     : Beschriftung der x-Achse; None -> Achse unbeschriftet lassen
                     (nuetzlich in Subplot-Gittern mit sharex, wo nur die untere Reihe
                     beschriftet wird). Default: Spieltage (Fussball/Simulation).
        ylabel     : Beschriftung der y-Achse; None -> unbeschriftet (analog sharey).
        point_label: Label der gebinnten Datenpunkte (nur fuer eine ggf. im Notebook
                     manuell gesetzte Legende; die Funktion selbst zeichnet keine).
        normalize  : durch a+b teilen (Default). False nur fuer den entarteten Fall
                     a+b ~ 0 -- dort ist die Normierung sinnlos (z.B. simuliertes
                     Szenario "zufaellige Tagesform": K(Delta m) ~ 0 fuer alle Lags).
    """
    if ax is None:                                               # eigene Figure, falls keine Achse uebergeben
        _, ax = plt.subplots(figsize=(8, 5))

    # --- Normierung auf K_fit(0) = a + b; NUR Darstellung, der Fit bleibt unveraendert
    scale = (result.a + result.b) if normalize else 1.0          # gemeinsamer Massstab der Achse
    ax.errorbar(bins_df["lag_bin"], bins_df["K_bin"] / scale,    # gebinnte ACF-Punkte
                yerr=bins_df["sigma_bin"] / scale,
                fmt="o", ms=5, capsize=3, color="#1f77b4", label=point_label)

    d_curve = np.linspace(result.d_fit.min(), result.d_fit.max(), 300)  # feine x-Achse fuer eine glatte Kurve
    # Genau EINE Kurve, immer rot -- unabhaengig davon, welche Variante gewaehlt ist. So sehen
    # alle Panels eines Vergleichsgitters gleich aus.
    if primary == "free":                                        # freie Abklingzeit ist die Hauptaussage (z.B. AR(1))
        curve = acf_model(d_curve, result.a, result.b, result.tau)
        label = r"Fit: freies $\tau$"
    else:                                                        # tau nicht identifizierbar -> Literaturwert tau = 7
        curve = acf_model_tau7(d_curve, result.a7, result.b7)
        label = r"Fit: $\tau = 7$ (fix)"
    ax.plot(d_curve, curve / scale, "-", color="red", label=label)  # Fit-Kurve durchgezogen, rot

    ax.axhline(0, color="black", lw=0.6)                        # Nulllinie

    # --- Panel-Nummerierung (a), (b), (c), ... bei mehreren Achsen in EINER Figur
    # fig.axes ist bei plt.subplots die Erzeugungsreihenfolge, also zeilenweise --
    # genau die gewuenschte Durchnummerierung.
    fig_axes = ax.get_figure().axes
    if len(fig_axes) > 1:
        letter = chr(ord("a") + fig_axes.index(ax))
        title = f"({letter}) {title}" if title else f"({letter})"

    if xlabel is not None:                                      # None -> Achse bewusst unbeschriftet (sharex-Gitter)
        ax.set_xlabel(xlabel)
    if ylabel is not None:                                      # None -> unbeschriftet (analog sharey)
        ax.set_ylabel(ylabel)
    if title:                                                   # optionaler Titel (ggf. mit Panel-Buchstabe)
        ax.set_title(title)
    return ax
