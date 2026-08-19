-- v_trailing_trends — évolutions temporelles (docs/00_project_charter.md,
-- section 9 étape 5 : "window functions pour rankings et évolutions
-- temporelles").
--
-- Moyenne mobile 3 ans (ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) : lisse le
-- bruit d'un seul exercice pour juger une tendance de fond plutôt qu'un pic
-- ponctuel — utile pour le profil de screening "Quality" (étape 6), qui doit
-- privilégier la régularité à la performance d'une seule année.
-- Ne filtre PAS sur "au moins 3 exercices disponibles" : la moyenne mobile
-- est calculée sur autant d'exercices précédents que réellement disponibles
-- (1, 2 ou 3) — comportement standard d'une fenêtre ROWS BETWEEN, pas un bug ;
-- years_available_for_avg expose explicitement la taille réelle de la fenêtre
-- pour que le lecteur puisse juger la fiabilité de la moyenne.
-- roic_3y_ago (LAG avec décalage 3, pas 1) : mesure l'évolution de la
-- rentabilité du capital sur le cycle plutôt que d'une année sur l'autre.
--
-- Source : mv_company_financial_profile (vue matérialisée) depuis l'étape
-- d'optimisation (sql/optimization/001_...sql).

CREATE OR REPLACE VIEW v_trailing_trends AS
SELECT
    company_id,
    ticker,
    fiscal_year,

    revenue_growth,
    AVG(revenue_growth) OVER w AS revenue_growth_3y_avg,

    ebitda_margin,
    AVG(ebitda_margin) OVER w AS ebitda_margin_3y_avg,

    roic,
    LAG(roic, 3) OVER (PARTITION BY company_id ORDER BY fiscal_year) AS roic_3y_ago,

    COUNT(*) OVER w AS years_available_for_avg
FROM mv_company_financial_profile
WINDOW w AS (PARTITION BY company_id ORDER BY fiscal_year ROWS BETWEEN 2 PRECEDING AND CURRENT ROW);
