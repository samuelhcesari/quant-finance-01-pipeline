# Financial Intelligence Pipeline — Rapport de recherche

**Projet 1/3 (SQL/PostgreSQL) — portfolio finance quantitative.**
Toutes les données citées proviennent d'exécutions réelles du pipeline le 2026-08-19. Aucune valeur n'est estimée.

## Abstract

Ce rapport présente les résultats d'une plateforme d'analyse financière construite sur 43 entreprises américaines cotées (3 secteurs : pharmaceutique, technologie, construction), 714 exercices annuels normalisés depuis SEC EDGAR, et 5 transactions M&A réelles vérifiées sur leur source primaire. Un moteur de screening à 4 profils (PE Growth, PE Value, Quality, Distressed), aux seuils entièrement paramétrables, classe les entreprises de l'échantillon avec des résultats économiquement plausibles et vérifiables. Une prime de transaction recalculée indépendamment (Amgen/Horizon Therapeutics, 47,92%) correspond exactement à la prime annoncée officiellement (47,9%), validant la méthodologie de bout en bout.

## 1. Introduction

Les plateformes de deal-sourcing professionnelles combinent des données financières normalisées, des ratios de rentabilité et de levier, et des règles de filtrage pour identifier des cibles d'investissement. Ce projet en reconstruit une version pédagogique complète — de la collecte de données brutes au moteur de screening — en s'appuyant exclusivement sur des sources publiques et un SGBD open source (PostgreSQL 16).

## 2. Research Question

*Peut-on construire, à partir de données financières publiques, un système d'aide à la décision capable d'identifier et de classer des entreprises selon des profils d'investissement standards (croissance, valeur, qualité, distressed), tout en rendant explicite la mécanique financière (croissance → marge → levier → multiple) qui sous-tend chaque classement ?*

Sous-questions traitées : (1) quelles entreprises présentent la meilleure combinaison croissance/marge/ROIC ? (2) comment les multiples de valorisation varient-ils par secteur et dans le temps ? (3) quelle est la dynamique des primes et multiples payés en M&A ? (4) quel profil financier est associé à un statut de cible M&A/distressed dans l'échantillon ?

## 3. Background

Les concepts mobilisés (marges, ROIC, leverage, FCF, multiples de valorisation, primes de transaction) suivent les définitions standard de la littérature en corporate finance et valorisation (formules exactes : `docs/00_project_charter.md` section 5). Aucune méthodologie propriétaire n'est utilisée — seulement des ratios et transformations documentés et vérifiables.

## 4. Data

| Source | Contenu | Résultat réel |
|---|---|---|
| SEC EDGAR (Company Facts API, XBRL) | États financiers US GAAP, dépôts 10-K annuels uniquement | 43/43 entreprises, 714 exercices-année extraits |
| FRED | DGS10, spread high-yield (BAMLH0A0HYM2), Fed Funds | 3/3 séries, 17 792 observations |
| Yahoo Finance (`yfinance`) | Prix de marché quotidiens, 5 ans | 43/43 tickers, 53 940 lignes |
| Annonces SEC 8-K | 5 transactions M&A | Chacune vérifiée sur sa source SEC primaire |

**Échantillon** : 43 entreprises, 3 secteurs contrastés (Pharmaceutique/Biotech 14, Technologie 15, Construction/Matériaux 14), choisis manuellement pour représenter des profils de croissance et de cycle différents.

**Taux de remplissage des champs clés** (43 entreprises, 714 exercices) : `net_income` 100,0%, `revenue` 97,8%, `total_equity` 99,4%, `total_assets` 94,1% ; plus bas : `ebit`/`ebitda` ~73-76% (EBITDA reconstruit uniquement quand deux tags XBRL distincts sont tous deux présents), `short_term_debt` 58,7%, `dividends_paid` 57,0%. Détail exhaustif : `docs/data_sources.md`.

## 5. Methodology

Pipeline : fetchers Python (données brutes, jamais modifiées) → normalizers (mapping de tags XBRL vers colonnes, cf. `xbrl_concepts.py`) → loaders idempotents PostgreSQL → 12 vues SQL analytiques (window functions, CTE imbriquées) → moteur de screening générique piloté par YAML.

**Choix méthodologiques documentés** :
- `fiscal_year` dérivé de la date de clôture d'exercice, pas du tag `fy` de SEC EDGAR (peu fiable pour les périodes comparatives, cf. `docs/data_sources.md` section 6).
- Les périodes annuelles sont identifiées via un concept de flux (`NetIncomeLoss`) filtré sur une durée de 350-380 jours, pas un concept de stock (`Assets`) — nécessaire pour exclure les données trimestrielles supplémentaires parfois présentes dans un même 10-K.
- Un exercice apparaissant dans plusieurs 10-K (courant puis comparatif) est résolu en gardant le filing le plus ancien — évite le biais de "look-ahead" via un restatement ultérieur.
- Capitalisation boursière (pour `v_valuation`) approximée par `close_price × shares_diluted` (moyenne pondérée diluée de l'exercice), en l'absence d'historique de nombre d'actions point-in-time dans les données Yahoo Finance collectées.

## 6. Results

### 6.1 Rankings sectoriels

Secteur Technologie, exercice fiscal 2024 (`v_sector_rankings`) : NVIDIA (NVDA) classée #1 sur 15 en croissance du chiffre d'affaires (+125,9%) et #1 en marge EBITDA (56,6%) — cohérent avec le cycle de demande en IA documenté publiquement sur cette période. Texas Instruments (TXN) dernière (-10,7%), cohérent avec le creux du cycle semi-conducteurs. Apple (AAPL), 11ᵉ sur 15 en croissance (+2,0%), illustre une maturité de marché relative face aux hypercroissances du secteur.

### 6.2 Évolution du ROIC (Apple, `v_trailing_trends`)

| Exercice | ROIC |
|---|---|
| 2020 | 42,1% |
| 2021 | 64,3% |
| 2022 | 73,0% |
| 2023 | 71,0% |
| 2024 | 75,6% |
| 2025 | 87,4% |

Progression globale marquée (42% → 87%), avec un léger repli en 2023 (71,0% contre 73,0% en 2022) — cohérent avec le recul du chiffre d'affaires cette année-là (-2,8%, cf. `v_growth`) — avant reprise de la hausse en 2024-2025, portée par la politique de rachat d'actions massive d'Apple (dénominateur `invested_capital` en baisse relative).

### 6.3 Moteur de screening

Exécuté sur les 714 exercices-entreprise de l'échantillon :

| Profil | Passent | Taux |
|---|---|---|
| PE Growth | 54/714 | 7,6% |
| PE Value | 63/714 | 8,8% |
| Quality | 107/714 | 15,0% |
| Distressed | 3/714 | 0,4% |

Le profil "Quality" retient des entreprises largement reconnues comme telles : AAPL, MSFT, NVDA, GOOGL, META, ADBE, CSCO, GILD, ORCL (exercices récents). Le profil "Distressed" (le plus sélectif, comme attendu d'un signal de tension financière) identifie VTRS (dette élevée post scission de l'activité générique Pfizer/Mylan), INTC en 2023 (année difficile documentée pour Intel) et VMC en 2010 (matériaux de construction, récession post-2008) — trois cas économiquement plausibles, aucun résultat absurde.

### 6.4 Transactions M&A : primes et multiples

| Transaction | Prime | EV/Revenue |
|---|---|---|
| Amgen → Horizon Therapeutics | **47,92%** (recalculée) vs 47,9% annoncée | 8,8x |
| Pfizer → Seagen | n/d (prix non-affecté non documenté) | 21,9x |
| IBM → HashiCorp | n/d | 11,0x |

La prime Amgen/Horizon recalculée indépendamment (`116,50 / 78,76 - 1`) correspond à 0,02 point de pourcentage près à celle annoncée officiellement par Amgen — validation croisée directe de la méthodologie de calcul de prime (`v_transaction_premiums`).

### 6.5 Analyse quantitative (corrélations, profil des cibles M&A, contexte macro)

Trois questions posées dans la charte (section 2) n'avaient jusque-là reçu aucune réponse chiffrée — le screening et les rankings sont des outils de classement, pas des tests statistiques. Ajoutés dans `sql/queries/` (corrélations calculées nativement en SQL via `CORR()`, l'agrégat de Pearson de PostgreSQL) :

**Croissance/marge vs multiples de valorisation** (`001_growth_valuation_correlation.sql`, N=118 après exclusion des multiples aberrants) : corrélation globale quasi nulle entre croissance et EV/EBITDA (0,068), légèrement négative pour marge (-0,128) et ROIC (-0,061) — aucun "growth premium" évident à l'échelle de l'échantillon complet. Par secteur, le tableau change beaucoup :

| Secteur | N | Corr. croissance | Corr. marge | Corr. ROIC | EV/EBITDA moyen |
|---|---|---|---|---|---|
| Pharma/Biotech | 23 | -0,182 | **-0,702** | -0,402 | 19,0x |
| Construction | 39 | 0,174 | -0,241 | -0,420 | 16,8x |
| Technologie | 56 | 0,068 | -0,214 | -0,029 | 23,2x |

En pharma/biotech, marge et ROIC sont fortement *négativement* corrélés au multiple — cohérent avec le fait que les biotechs pré-rentables à fort potentiel (type Seagen, EBITDA négatif) se paient souvent plus cher que les majors pharma matures et rentables, sur la promesse du pipeline plutôt que sur la rentabilité actuelle.

**Profil des cibles M&A vs l'univers** (`002_ma_target_profile_vs_universe.sql`, N=4 cibles avec financials disponibles — Splunk et Lhoist North America exclues faute de données) : à titre illustratif, pas comme test d'hypothèse vu la taille de l'échantillon —

| Cible | Marge EBITDA | Percentile dans son secteur |
|---|---|---|
| HashiCorp | -42,0% | **0ᵉ** (pire marge de tout l'échantillon tech, N=232) |
| Seagen | -28,9% | 12ᵉ (pharma, N=123) |
| Horizon Therapeutics | 27,8% | 33ᵉ (pharma, N=123) |

2 des 3 cibles mesurables se situent tout en bas de la distribution de marge de leur secteur — cohérent avec des acquisitions stratégiques de croissance/technologie plutôt que des rachats sur la base de cash-flows actuels.

**Contexte macro des transactions et corrélation avec les multiples** (`003_macro_context.sql`) : le spread de crédit high-yield (`BAMLH0A0HYM2`) n'est disponible qu'à partir du 2023-08-21 dans les données FRED récupérées (limitation découverte en écrivant cette requête, documentée dans `docs/data_sources.md`) — non disponible pour les transactions Horizon Therapeutics et Seagen, antérieures à cette date. Sur les exercices 2023-2026 (N=4, très limité), la corrélation entre EV/EBITDA moyen de l'univers et le spread HY est de 0,558 — signe positif, contre-intuitif si l'on attendait une compression des multiples quand le crédit se tend. Avec seulement 4 points, ce résultat n'est pas robuste statistiquement ; il est rapporté tel quel plutôt que forcé dans une conclusion qu'il ne supporte pas.

## 7. Robustness

**Sensibilité du seuil ROIC (profil Quality)** — combien d'exercices-entreprise passeraient le filtre ROIC seul à différents seuils :

| Seuil ROIC | Exercices qualifiants |
|---|---|
| ≥ 10% | 259/714 (36,3%) |
| ≥ 15% (seuil retenu) | 191/714 (26,8%) |
| ≥ 20% | 144/714 (20,2%) |

Le classement n'est pas un effet de seuil artificiel : la population qualifiante décroît de façon régulière et progressive entre 10% et 20%, sans saut brutal autour de 15% — le seuil retenu ne capture pas un artefact de discontinuité dans la distribution.

**Disponibilité de la fenêtre 3 ans** (moyennes mobiles utilisées par le profil Quality) : 628/714 exercices (88%) disposent des 3 années complètes requises pour `ebitda_margin_3y_avg`/`revenue_growth_3y_avg` ; 86/714 (12%, principalement les premières années de couverture SEC EDGAR par entreprise, ~2009-2011) n'en disposent pas et sont donc explicitement exclus par la règle `years_available_for_avg == 3` du profil Quality plutôt que d'être évalués sur une moyenne partielle silencieusement dégradée.

## 8. Economic Interpretation

Les résultats du screening sont directionnellement cohérents avec des faits publiquement documentés sur la période étudiée (cycle IA 2023-2025, difficultés d'Intel en 2023, récession de la construction 2008-2010, restructuration de Viatris) sans qu'aucune de ces validations n'ait été construite a posteriori pour orienter la méthodologie — les seuils des 4 profils ont été fixés avant l'exécution du screening, à partir de conventions standard de filtrage PE (croissance ≥15% pour "Growth", ROIC ≥15% pour "Quality", etc.), documentées dans `configs/screening/*.yaml`.

## 9. Limitations

- **Échantillon M&A restreint** (5 transactions) : insuffisant pour une analyse statistique de la dynamique des primes par secteur/cycle — seulement illustratif et vérifié individuellement.
- **Biais de survivance** : les 43 entreprises sont toutes cotées et actives à la date de collecte ; aucune entreprise délistée/faillie sur 2021-2026 n'est incluse, ce qui peut surestimer la performance moyenne de l'échantillon.
- **Cohérence comptable imparfaite** : 56 lignes sur les 461 réellement testables (12,1%, pas 714 — `total_liabilities` ne couvre que 64,6% de l'échantillon) hors tolérance de 1% sur l'identité Actif = Passif + Capitaux propres, notamment pour des entreprises ayant porté des capitaux propres temporaires (mezzanine equity) avant introduction en bourse (cas MRNA 2017 documenté en détail).
- **Capitalisation boursière approximée**, pas un nombre d'actions point-in-time exact — les multiples de `v_valuation` sont indicatifs.
- **Portée annuelle uniquement** : le détail trimestriel n'est pas chargé, limitant la granularité de la fenêtre "TTM" utilisée pour les financials des cibles M&A (approximée par le dernier exercice annuel complet avant l'annonce).
- **Qualité Yahoo Finance** : source non officielle, jamais utilisée pour les états financiers eux-mêmes, documentée comme telle conformément à la charte.

## 10. Conclusion

Le pipeline démontre qu'un système de screening d'investissement méthodologiquement rigoureux — traçable jusqu'à la donnée source, avec des seuils explicites et un moteur générique — peut être construit entièrement à partir de données publiques gratuites. Les résultats produits sont vérifiables à trois niveaux : par calcul manuel indépendant (vues de ratios, section 6 de la charte), par recoupement avec une source primaire externe (prime M&A Amgen/Horizon), et par plausibilité économique qualitative (composition des profils de screening). Les limitations documentées (échantillon M&A restreint, biais de survivance, cohérence comptable imparfaite) sont des contraintes de données publiques gratuites, pas des lacunes méthodologiques masquées.

## 11. References

- U.S. Securities and Exchange Commission — [EDGAR Company Facts API documentation](https://www.sec.gov/edgar/sec-api-documentation)
- Federal Reserve Bank of St. Louis — [FRED API documentation](https://fred.stlouisfed.org/docs/api/fred/)
- Sources et URLs exactes de chaque donnée et transaction M&A utilisée dans ce rapport : [`docs/data_sources.md`](../docs/data_sources.md)
- Justification du schéma de données : [`docs/01_data_model.md`](../docs/01_data_model.md)
- Preuves `EXPLAIN ANALYZE` complètes (section optimisation) : [`sql/optimization/README.md`](../sql/optimization/README.md)
