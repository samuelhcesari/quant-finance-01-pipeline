DB_USER := fida
DB_NAME := financial_intelligence
SCHEMA_DIR := sql/schema

.PHONY: up down schema psql logs fetch-data normalize load screen visualize test

up:
	docker compose up -d postgres
	@echo "Waiting for postgres to become healthy..."
	@until docker compose exec -T postgres pg_isready -U $(DB_USER) -d $(DB_NAME) > /dev/null 2>&1; do sleep 1; done
	@echo "postgres is up."

down:
	docker compose down

# Applies the full DB structure (tables, views, materialized view + indexes)
# inside the running container (sql/ is bind-mounted read-only at /sql).
# Order matters and crosses directories: views 008-010 use CREATE OR REPLACE
# VIEW against mv_company_financial_profile, which sql/optimization/001
# creates — so optimization must run between views 007 and 008, not after
# every view. A plain glob over sql/schema, then sql/views, then
# sql/optimization would apply views 008-010 too early and fail. Stops on
# the first error.
SCHEMA_FILES := \
	schema/001_init.sql \
	schema/002_transactions_unique.sql \
	views/001_v_growth.sql \
	views/002_v_margins.sql \
	views/003_v_returns.sql \
	views/004_v_leverage.sql \
	views/005_v_cash_flow.sql \
	views/006_v_valuation.sql \
	views/007_v_company_financial_profile.sql \
	optimization/001_mv_company_financial_profile.sql \
	views/008_v_sector_rankings.sql \
	views/009_v_trailing_trends.sql \
	views/010_v_screening_base.sql \
	views/011_v_transaction_premiums.sql \
	views/012_v_transaction_multiples.sql \
	views/013_v_data_quality_flags.sql

schema:
	@for f in $(SCHEMA_FILES); do \
		echo "Applying $$f"; \
		docker compose exec -T postgres psql -U $(DB_USER) -d $(DB_NAME) -v ON_ERROR_STOP=1 -f /sql/$$f || exit 1; \
	done

psql:
	docker compose exec postgres psql -U $(DB_USER) -d $(DB_NAME)

logs:
	docker compose logs -f postgres

# Les cibles ci-dessous tournent côté hôte (pas dans le conteneur Docker) : le
# venv Python doit être activé, et .env doit pointer DB_HOST/DB_PORT vers le
# Postgres accessible (Docker via 5432, ou toute autre instance atteignable).
fetch-data:
	python -m financial_intelligence.data.fetch_sec_edgar
	python -m financial_intelligence.data.fetch_fred
	python -m financial_intelligence.data.fetch_yahoo

normalize:
	python -m financial_intelligence.data.normalize_sec_edgar
	python -m financial_intelligence.data.normalize_yahoo
	python -m financial_intelligence.data.normalize_fred

load:
	python -m financial_intelligence.data.load_to_postgres
	python -m financial_intelligence.data.load_ma_transactions

screen:
	python -m financial_intelligence.analytics.screening_engine

visualize:
	python -m financial_intelligence.analytics.visualize

test:
	pytest
