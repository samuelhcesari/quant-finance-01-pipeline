"""Table de correspondance concept normalisé -> tags US-GAAP candidats.

Les filers SEC ne taguent pas tous la même ligne comptable avec le même concept
XBRL (ex. le revenu peut être `Revenues`, `RevenueFromContractWithCustomer...`,
ou `SalesRevenueNet` selon l'entreprise et l'année). Chaque entrée liste les tags
par ordre de préférence ; le premier tag présent dans le filing est utilisé.
Si aucun ne l'est, le champ reste NULL.
"""

from __future__ import annotations

# --- Compte de résultat (concepts "duration", unité USD) -------------------
INCOME_STATEMENT_TAGS: dict[str, list[str]] = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ],
    "cogs": [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsSold",
        "CostOfServices",
    ],
    "gross_profit": ["GrossProfit"],
    "sga_expense": [
        "SellingGeneralAndAdministrativeExpense",
        "SellingGeneralAndAdministrativeExpenses",
        "GeneralAndAdministrativeExpense",
    ],
    "ebit": ["OperatingIncomeLoss"],
    "interest_expense": [
        "InterestExpense",
        "InterestExpenseDebt",
        "InterestExpenseDebtExcludingAmortization",
        "InterestAndDebtExpense",
    ],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
    ],
    "tax_expense": ["IncomeTaxExpenseBenefit"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
}

INCOME_STATEMENT_PER_SHARE_TAGS: dict[str, list[str]] = {
    "eps_basic": ["EarningsPerShareBasic"],
    "eps_diluted": ["EarningsPerShareDiluted"],
}

INCOME_STATEMENT_SHARES_TAGS: dict[str, list[str]] = {
    "shares_basic": ["WeightedAverageNumberOfSharesOutstandingBasic"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}

# D&A n'est pas persisté (pas de colonne dédiée dans cash_flow_statements) —
# utilisé uniquement en mémoire pour reconstruire ebitda = ebit + D&A.
DEPRECIATION_AMORTIZATION_TAGS: list[str] = [
    "DepreciationDepletionAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
    "DepreciationAndAmortization",
    "Depreciation",
]

# --- Bilan (concepts "instant", unité USD) ----------------------------------
BALANCE_SHEET_TAGS: dict[str, list[str]] = {
    "cash_and_equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "total_current_assets": ["AssetsCurrent"],
    "total_assets": ["Assets"],
    "short_term_debt": ["ShortTermBorrowings", "DebtCurrent", "LongTermDebtCurrent"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "total_current_liabilities": ["LiabilitiesCurrent"],
    "total_liabilities": ["Liabilities"],
    "total_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
}

# --- Tableau de flux de trésorerie (concepts "duration", unité USD) --------
CASH_FLOW_TAGS: dict[str, list[str]] = {
    "cfo": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForCapitalImprovements",
        "PaymentsToAcquireProductiveAssets",
    ],
    "cfi": [
        "NetCashProvidedByUsedInInvestingActivities",
        "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations",
    ],
    "cff": [
        "NetCashProvidedByUsedInFinancingActivities",
        "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
    ],
    "dividends_paid": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
}


# Concepts ancres pour définir l'ensemble des périodes annuelles. Doit être un
# concept "duration" (pas "instant") : certains 10-K contiennent des données
# trimestrielles supplémentaires (note "quarterly financial data") elles aussi
# taguées form=10-K/fp=FY avec la même date de fin que le T4 annuel — seule la
# durée (~365 jours vs ~90 jours) permet de les distinguer de l'exercice complet.
# `Assets` (instant) ne permettrait pas cette distinction, d'où le choix d'un
# concept de flux comme ancre.
ANCHOR_TAGS: list[str] = ["NetIncomeLoss", "ProfitLoss"]
ANNUAL_DURATION_MIN_DAYS = 350
ANNUAL_DURATION_MAX_DAYS = 380
