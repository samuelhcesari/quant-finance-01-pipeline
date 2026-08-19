-- Répond à une question de recherche posée dans la charte (section 2) et
-- jamais testée jusqu'ici : "les multiples de valorisation varient-ils avec
-- la croissance et la marge (proxy d'un growth-adjusted multiple) ?"
--
-- CORR() est l'agrégat de corrélation de Pearson natif de PostgreSQL — pas de
-- calcul externe, pas de librairie stats. Échantillon limité aux lignes où
-- ev_to_ebitda est disponible (couverture Yahoo Finance ~5 ans, cf.
-- docs/data_sources.md), donc N est rapporté à chaque fois plutôt que
-- présenté comme représentatif de tout l'historique 2009-2026.

-- 1. Corrélation globale, tous secteurs confondus
SELECT
    COUNT(*) AS n,
    ROUND(CORR(revenue_growth, ev_to_ebitda)::numeric, 3) AS corr_growth_ev_ebitda,
    ROUND(CORR(ebitda_margin, ev_to_ebitda)::numeric, 3) AS corr_margin_ev_ebitda,
    ROUND(CORR(roic, ev_to_ebitda)::numeric, 3) AS corr_roic_ev_ebitda
FROM v_screening_base
WHERE ev_to_ebitda IS NOT NULL AND ev_to_ebitda BETWEEN 0 AND 100;  -- exclut les multiples aberrants (EBITDA proche de 0)

-- 2. Même corrélation, décomposée par secteur (les normes de valorisation
-- diffèrent structurellement entre pharma/tech/construction, une corrélation
-- globale masquerait ça)
SELECT
    sector_name,
    COUNT(*) AS n,
    ROUND(CORR(revenue_growth, ev_to_ebitda)::numeric, 3) AS corr_growth_ev_ebitda,
    ROUND(CORR(ebitda_margin, ev_to_ebitda)::numeric, 3) AS corr_margin_ev_ebitda,
    ROUND(CORR(roic, ev_to_ebitda)::numeric, 3) AS corr_roic_ev_ebitda,
    ROUND(AVG(ev_to_ebitda)::numeric, 1) AS avg_ev_ebitda
FROM v_screening_base
WHERE ev_to_ebitda IS NOT NULL AND ev_to_ebitda BETWEEN 0 AND 100
GROUP BY sector_name
ORDER BY sector_name;
