"""Génère les visualisations des résultats déjà calculés par le pipeline —
aucune nouvelle logique financière ici, uniquement de la lecture des vues SQL
existantes (v_screening_base, screening_results) et du rendu matplotlib.

Les 4 figures répondent à des questions que les tableaux markdown du README
et de reports/research_report.md laissent difficiles à voir d'un coup d'œil :
combien d'entreprises passent chaque profil de screening, comment se
distribuent les multiples de valorisation, comment les secteurs se comparent
sur les métriques clés, et comment ces métriques sont corrélées entre elles.

Sorties : results/figures/*.png (commitées volontairement, cf. .gitignore,
pour être visibles directement sur GitHub sans exécuter le pipeline).

Usage : python -m financial_intelligence.analytics.visualize
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless : ce script ne tourne jamais dans un terminal interactif

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psycopg

from financial_intelligence.utils.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER, PROJECT_ROOT

FIGURES_DIR = PROJECT_ROOT / "results" / "figures"

SECTOR_COLORS = {
    "Pharmaceutique / Biotech": "#2C7FB8",
    "Technologie": "#41AB5D",
    "Construction / Matériaux / E&C": "#D95F0E",
}
DEFAULT_COLOR = "#555555"


def _connect() -> psycopg.Connection:
    return psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )


def _fetch_df(conn: psycopg.Connection, sql: str) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql)
        columns = [c.name for c in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=columns)


def _clean_numeric(series: pd.Series) -> pd.Series:
    """NULL SQL -> NaN pandas (déjà le cas via psycopg), +/-inf -> NaN (peut
    arriver sur un ratio dont le dénominateur est proche de 0), puis les NaN
    sont retirés par l'appelant (dropna) avant tout calcul agrégé — jamais une
    valeur inventée à la place d'une donnée manquante."""
    s = pd.to_numeric(series, errors="coerce")
    return s.replace([np.inf, -np.inf], np.nan)


def plot_screening_funnel(conn: psycopg.Connection) -> None:
    """Combien d'exercices-entreprise passent chaque profil, sur le run de
    screening le plus récent (screening_results contient l'historique de
    plusieurs runs — on ne prend que le dernier par profil, sinon les
    décomptes s'additionneraient across runs)."""
    df = _fetch_df(
        conn,
        """
        WITH latest_run AS (
            SELECT screening_profile_id, MAX(run_date) AS max_run_date
            FROM screening_results GROUP BY screening_profile_id
        )
        SELECT sp.code, sp.name,
               COUNT(*) FILTER (WHERE sr.passed) AS n_passed,
               COUNT(*) AS n_total
        FROM screening_results sr
        JOIN latest_run lr ON lr.screening_profile_id = sr.screening_profile_id
                           AND lr.max_run_date = sr.run_date
        JOIN screening_profiles sp ON sp.screening_profile_id = sr.screening_profile_id
        GROUP BY sp.code, sp.name
        ORDER BY sp.code
        """,
    )
    if df.empty:
        print("  [SKIP] plot_screening_funnel : screening_results vide (lancer le screening engine d'abord).")
        return

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(df["name"], df["n_passed"], color="#2C7FB8")
    ax.bar_label(bars, padding=3)
    total = df["n_total"].iloc[0]
    ax.set_ylabel(f"Exercices-entreprise passant le profil (sur {total} évalués)")
    ax.set_title("Screening — combien d'observations passent chaque profil")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "screening_funnel.png", dpi=150)
    plt.close(fig)
    print(f"  screening_funnel.png : {dict(zip(df['code'], df['n_passed']))}")


def plot_valuation_distributions(conn: psycopg.Connection) -> None:
    """Distribution de P/E, EV/EBITDA, FCF Yield — v_valuation n'a de données
    que sur les ~5 dernières années (couverture Yahoo Finance, documenté dans
    docs/data_sources.md), donc ces distributions portent sur un
    sous-ensemble de l'échantillon, pas les 714 lignes complètes."""
    df = _fetch_df(
        conn,
        "SELECT price_to_earnings, ev_to_ebitda, fcf_yield FROM v_screening_base",
    )
    pe = _clean_numeric(df["price_to_earnings"])
    pe = pe[(pe > 0) & (pe < 100)].dropna()  # P/E négatif ou >100x : peu lisible sur un histogramme, cf. docstring
    ev = _clean_numeric(df["ev_to_ebitda"])
    ev = ev[(ev > 0) & (ev < 100)].dropna()
    fy = _clean_numeric(df["fcf_yield"]).dropna()
    fy = fy[fy.between(fy.quantile(0.01), fy.quantile(0.99))] if len(fy) > 10 else fy

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    specs = [(pe, "P/E", axes[0]), (ev, "EV/EBITDA", axes[1]), (fy, "FCF Yield", axes[2])]
    for series, label, ax in specs:
        if series.empty:
            ax.text(0.5, 0.5, "pas de données", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(label)
            continue
        ax.hist(series, bins=20, color="#2C7FB8", edgecolor="white")
        ax.axvline(series.median(), color="#D95F0E", linestyle="--", linewidth=1.5,
                    label=f"médiane {series.median():.2f}")
        ax.set_title(f"{label}  (n={len(series)})")
        ax.legend(fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Distribution des multiples de valorisation (v_valuation, ~5 dernières années)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "valuation_distributions.png", dpi=150)
    plt.close(fig)
    print(f"  valuation_distributions.png : P/E n={len(pe)}, EV/EBITDA n={len(ev)}, FCF Yield n={len(fy)}")


def plot_sector_comparison(conn: psycopg.Connection) -> None:
    """MÉDIANE, pas moyenne : ROIC en particulier explose quand
    invested_capital (dette + capitaux propres - cash) est proche de zéro —
    constaté sur ABBV 2016 (ROIC -8144%, cf. tests manuels), qui à lui seul
    suffit à faire passer la moyenne du secteur pharma sous -100%. Une
    moyenne brute rendrait le graphique inutilisable ; la médiane reste
    représentative sans qu'un seul point aberrant écrase tout le reste."""
    df = _fetch_df(
        conn,
        """
        SELECT sector_name, revenue_growth, ebitda_margin, roic, fcf_margin
        FROM v_screening_base
        """,
    )
    for col in ["revenue_growth", "ebitda_margin", "roic", "fcf_margin"]:
        df[col] = _clean_numeric(df[col])

    grouped = df.groupby("sector_name")[["revenue_growth", "ebitda_margin", "roic", "fcf_margin"]].median()
    if grouped.empty:
        print("  [SKIP] plot_sector_comparison : pas de données.")
        return

    metrics = ["revenue_growth", "ebitda_margin", "roic", "fcf_margin"]
    labels = ["Revenue Growth", "EBITDA Margin", "ROIC", "FCF Margin"]
    sectors = grouped.index.tolist()
    x = np.arange(len(metrics))
    width = 0.8 / max(len(sectors), 1)

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, sector in enumerate(sectors):
        values = grouped.loc[sector, metrics].values * 100  # ratios -> %
        ax.bar(x + i * width, values, width, label=sector, color=SECTOR_COLORS.get(sector, DEFAULT_COLOR))
    ax.set_xticks(x + width * (len(sectors) - 1) / 2)
    ax.set_xticklabels(labels)
    ax.set_ylabel("%  (médiane toutes années confondues)")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Comparaison sectorielle — médianes sur l'échantillon complet")
    ax.legend(fontsize=8, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "sector_comparison.png", dpi=150)
    plt.close(fig)
    print(f"  sector_comparison.png : {len(sectors)} secteurs, {grouped.shape[0]}x{grouped.shape[1]} médianes")


def plot_correlation_heatmap(conn: psycopg.Connection) -> None:
    df = _fetch_df(
        conn,
        """
        SELECT revenue_growth, ebitda_margin, roic, debt_to_equity, ev_to_ebitda, fcf_yield
        FROM v_screening_base
        """,
    )
    for col in df.columns:
        df[col] = _clean_numeric(df[col])
    # ev_to_ebitda a la même queue extrême que dans sql/queries/001_...sql
    # (EBITDA proche de 0) -> même filtre, pour cohérence avec l'analyse déjà publiée.
    df = df[df["ev_to_ebitda"].isna() | df["ev_to_ebitda"].between(0, 100)]

    labels = {
        "revenue_growth": "Revenue Growth", "ebitda_margin": "EBITDA Margin", "roic": "ROIC",
        "debt_to_equity": "Debt/Equity", "ev_to_ebitda": "EV/EBITDA", "fcf_yield": "FCF Yield",
    }
    corr = df.rename(columns=labels).corr(method="pearson", min_periods=10)
    n_rows = df.dropna(how="all").shape[0]

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(corr.values, vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr.columns)))
    ax.set_yticklabels(corr.columns)
    for i in range(len(corr.columns)):
        for j in range(len(corr.columns)):
            val = corr.values[i, j]
            if np.isnan(val):
                continue
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                     color="white" if abs(val) > 0.6 else "black", fontsize=8)
    fig.colorbar(im, ax=ax, label="corrélation de Pearson")
    ax.set_title(f"Corrélations entre métriques (n<={n_rows} exercices)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "correlation_heatmap.png", dpi=150)
    plt.close(fig)
    print(f"  correlation_heatmap.png : matrice {corr.shape[0]}x{corr.shape[1]}, n<={n_rows}")


def run() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Connexion à {DB_HOST}:{DB_PORT}/{DB_NAME} ...")
    conn = _connect()
    try:
        print("Génération des visualisations...")
        plot_screening_funnel(conn)
        plot_valuation_distributions(conn)
        plot_sector_comparison(conn)
        plot_correlation_heatmap(conn)
        print(f"\nTerminé sans erreur. Figures dans {FIGURES_DIR}")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
