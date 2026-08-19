-- v_valuation — multiples de valorisation (docs/00_project_charter.md, section 5) :
-- EV = Market Cap + Total Debt - Cash, puis EV/EBITDA, EV/Revenue, EV/EBIT,
-- P/E, P/B, FCF Yield = FCF / Market Cap.
--
-- LIMITATION DE DONNÉES EXPLICITE (cf. docs/data_sources.md section 6) :
-- market_prices ne contient PAS de nombre d'actions en circulation
-- point-in-time (yfinance ne fournit qu'un snapshot actuel, pas un historique
-- fiable). Cette vue approxime donc la capitalisation boursière par
-- close_price x shares_diluted (moyenne pondérée diluée de l'EXERCICE, pas le
-- nombre d'actions à la date de clôture précise) — une approximation standard
-- en l'absence de mieux, mais PAS un market cap exact. Toute valeur dérivée
-- (EV, EV/EBITDA, P/B, FCF Yield...) hérite de cette approximation, à traiter
-- comme indicative, pas comme une référence de marché précise.
--
-- Cours retenu : le dernier close_price disponible à la date de clôture de
-- l'exercice ou avant (DISTINCT ON ... ORDER BY price_date DESC). Comme
-- market_prices ne couvre que les 5 dernières années (fetch_yahoo.py, period
-- 5y), cette vue ne renvoie des valeurs que pour les exercices récents ayant
-- un prix de marché disponible — NULL pour les exercices plus anciens, ce qui
-- est attendu, pas un bug.

CREATE VIEW v_valuation AS
WITH price_at_period AS (
    SELECT DISTINCT ON (fp.fiscal_period_id)
        fp.fiscal_period_id,
        mp.close_price,
        mp.price_date
    FROM fiscal_periods fp
    JOIN market_prices mp
        ON mp.company_id = fp.company_id AND mp.price_date <= fp.period_end_date
    WHERE fp.period_type = 'FY'
    ORDER BY fp.fiscal_period_id, mp.price_date DESC
),
base AS (
    SELECT
        fp.company_id,
        fp.fiscal_period_id,
        fp.fiscal_year,
        pap.close_price,
        pap.price_date AS price_as_of,
        i.eps_diluted,
        i.shares_diluted,
        i.revenue,
        i.ebitda,
        i.ebit,
        b.total_equity,
        b.cash_and_equivalents,
        CASE
            WHEN b.short_term_debt IS NULL AND b.long_term_debt IS NULL THEN NULL
            ELSE COALESCE(b.short_term_debt, 0) + COALESCE(b.long_term_debt, 0)
        END AS total_debt,
        (cf.cfo - cf.capex) AS fcf
    FROM fiscal_periods fp
    JOIN income_statements i ON i.fiscal_period_id = fp.fiscal_period_id
    JOIN balance_sheets b ON b.fiscal_period_id = fp.fiscal_period_id
    JOIN cash_flow_statements cf ON cf.fiscal_period_id = fp.fiscal_period_id
    LEFT JOIN price_at_period pap ON pap.fiscal_period_id = fp.fiscal_period_id
    WHERE fp.period_type = 'FY'
)
SELECT
    company_id,
    fiscal_period_id,
    fiscal_year,
    close_price,
    price_as_of,
    shares_diluted,
    (close_price * shares_diluted) AS market_cap_approx,
    ((close_price * shares_diluted) + total_debt - cash_and_equivalents) AS ev_approx,

    ((close_price * shares_diluted) + total_debt - cash_and_equivalents)
        / NULLIF(ebitda, 0) AS ev_to_ebitda,
    ((close_price * shares_diluted) + total_debt - cash_and_equivalents)
        / NULLIF(revenue, 0) AS ev_to_revenue,
    ((close_price * shares_diluted) + total_debt - cash_and_equivalents)
        / NULLIF(ebit, 0) AS ev_to_ebit,

    close_price / NULLIF(eps_diluted, 0) AS price_to_earnings,
    (close_price * shares_diluted) / NULLIF(total_equity, 0) AS price_to_book,
    fcf / NULLIF(close_price * shares_diluted, 0) AS fcf_yield
FROM base;
