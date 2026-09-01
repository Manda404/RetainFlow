SHELL := /bin/bash

PROJECT_NAME := RetainFlow
CONFIG := config/churn_model.yml
N_CUSTOMERS ?= 10000

API_HOST ?= 127.0.0.1
API_PORT ?= 8000
APP_HOST ?= 127.0.0.1
APP_PORT ?= 5500
MLFLOW_HOST ?= 127.0.0.1
MLFLOW_PORT ?= 5050

PYTHON := .venv/bin/python
POETRY := poetry
LOG_DIR := logs
PID_DIR := .run
API_LOG := $(LOG_DIR)/api.log
APP_LOG := $(LOG_DIR)/app.log
MLFLOW_LOG := $(LOG_DIR)/mlflow_ui.log
API_PID := $(PID_DIR)/api.pid
APP_PID := $(PID_DIR)/app.pid
MLFLOW_PID := $(PID_DIR)/mlflow.pid

.DEFAULT_GOAL := help

.PHONY: help setup install postgres postgres-stop status data-status \
	build-data drift train queue recommendations pipeline \
	api api-stop app app-stop mlflow mlflow-stop start stop restart test lint format clean-logs

help:
	@echo "$(PROJECT_NAME) - commandes disponibles"
	@echo ""
	@echo "Setup"
	@echo "  make setup             Installer les dependances Poetry"
	@echo "  make postgres          Demarrer PostgreSQL avec Docker"
	@echo "  make postgres-stop     Arreter PostgreSQL sans supprimer les donnees"
	@echo ""
	@echo "Pipelines"
	@echo "  make build-data        Generer/recharger les donnees (N_CUSTOMERS=$(N_CUSTOMERS))"
	@echo "  make drift             Generer le dashboard de drift"
	@echo "  make train             Entrainer le modele churn CatBoost"
	@echo "  make queue             Construire la file de retention"
	@echo "  make recommendations   Generer les recommandations de retention"
	@echo "  make pipeline          Executer data -> drift -> train -> queue -> recommendations"
	@echo ""
	@echo "Run"
	@echo "  make api               Lancer l'API FastAPI en arriere-plan"
	@echo "  make app               Lancer l'interface web en arriere-plan"
	@echo "  make mlflow            Lancer MLflow UI en arriere-plan"
	@echo "  make start             Demarrer PostgreSQL + API + interface web"
	@echo "  make stop              Arreter API + interface + MLflow + PostgreSQL"
	@echo "  make restart           Redemarrer l'application"
	@echo ""
	@echo "Controle"
	@echo "  make status            Voir l'etat des services locaux"
	@echo "  make data-status       Compter les principaux fichiers generes"
	@echo "  make test              Lancer les tests"
	@echo "  make lint              Lancer Ruff"
	@echo "  make format            Formater avec Ruff"
	@echo ""
	@echo "URLs"
	@echo "  API:      http://$(API_HOST):$(API_PORT)"
	@echo "  App:      http://$(APP_HOST):$(APP_PORT)"
	@echo "  MLflow:   http://$(MLFLOW_HOST):$(MLFLOW_PORT)"

setup: install

install:
	$(POETRY) install

postgres:
	docker compose up -d postgres

postgres-stop:
	docker compose stop postgres

build-data: postgres
	$(POETRY) run retainflow-build-data --reset --n-customers $(N_CUSTOMERS)

drift:
	$(POETRY) run retainflow-drift-dashboard --config $(CONFIG)

train:
	$(POETRY) run retainflow-train-churn --config $(CONFIG)

queue:
	$(POETRY) run retainflow-build-retention-queue --config $(CONFIG)

recommendations:
	$(POETRY) run retainflow-build-retention-recommendations --config $(CONFIG)

pipeline: build-data drift train queue recommendations

api:
	@mkdir -p $(LOG_DIR) $(PID_DIR)
	@if [ -f "$(API_PID)" ] && kill -0 "$$(cat $(API_PID))" 2>/dev/null; then \
		echo "API deja lancee: http://$(API_HOST):$(API_PORT)"; \
	else \
		echo "Lancement API: http://$(API_HOST):$(API_PORT)"; \
		RETAINFLOW_API_HOST=$(API_HOST) RETAINFLOW_API_PORT=$(API_PORT) \
			$(POETRY) run retainflow-api > "$(API_LOG)" 2>&1 & \
		echo $$! > "$(API_PID)"; \
		sleep 2; \
		echo "Logs: $(API_LOG)"; \
	fi

api-stop:
	@if [ -f "$(API_PID)" ]; then \
		if kill -0 "$$(cat $(API_PID))" 2>/dev/null; then \
			kill "$$(cat $(API_PID))"; \
			echo "API arretee"; \
		else \
			echo "API deja arretee"; \
		fi; \
		rm -f "$(API_PID)"; \
	else \
		echo "Aucun PID API trouve"; \
	fi

app:
	@mkdir -p $(LOG_DIR) $(PID_DIR)
	@if [ -f "$(APP_PID)" ] && kill -0 "$$(cat $(APP_PID))" 2>/dev/null; then \
		echo "Interface deja lancee: http://$(APP_HOST):$(APP_PORT)"; \
	else \
		echo "Lancement interface: http://$(APP_HOST):$(APP_PORT)"; \
		$(PYTHON) -m http.server $(APP_PORT) --bind $(APP_HOST) --directory app > "$(APP_LOG)" 2>&1 & \
		echo $$! > "$(APP_PID)"; \
		sleep 1; \
		echo "Logs: $(APP_LOG)"; \
	fi

app-stop:
	@if [ -f "$(APP_PID)" ]; then \
		if kill -0 "$$(cat $(APP_PID))" 2>/dev/null; then \
			kill "$$(cat $(APP_PID))"; \
			echo "Interface arretee"; \
		else \
			echo "Interface deja arretee"; \
		fi; \
		rm -f "$(APP_PID)"; \
	else \
		echo "Aucun PID interface trouve"; \
	fi

mlflow:
	@mkdir -p $(LOG_DIR) $(PID_DIR)
	@if [ -f "$(MLFLOW_PID)" ] && kill -0 "$$(cat $(MLFLOW_PID))" 2>/dev/null; then \
		echo "MLflow deja lance: http://$(MLFLOW_HOST):$(MLFLOW_PORT)"; \
	else \
		echo "Lancement MLflow: http://$(MLFLOW_HOST):$(MLFLOW_PORT)"; \
		MLFLOW_TRACKING_URI=sqlite:////Users/surelmanda/.mlflow/mlflow.db \
		MLFLOW_REGISTRY_URI=sqlite:////Users/surelmanda/.mlflow/mlflow.db \
			$(POETRY) run mlflow server \
			--backend-store-uri sqlite:////Users/surelmanda/.mlflow/mlflow.db \
			--default-artifact-root file:///Users/surelmanda/.mlflow/artifacts \
			--registry-store-uri sqlite:////Users/surelmanda/.mlflow/mlflow.db \
			--host $(MLFLOW_HOST) \
			--port $(MLFLOW_PORT) \
			--workers 1 > "$(MLFLOW_LOG)" 2>&1 & \
		echo $$! > "$(MLFLOW_PID)"; \
		sleep 3; \
		echo "Logs: $(MLFLOW_LOG)"; \
	fi

mlflow-stop:
	@if [ -f "$(MLFLOW_PID)" ]; then \
		if kill -0 "$$(cat $(MLFLOW_PID))" 2>/dev/null; then \
			kill "$$(cat $(MLFLOW_PID))"; \
			echo "MLflow arrete"; \
		else \
			echo "MLflow deja arrete"; \
		fi; \
		rm -f "$(MLFLOW_PID)"; \
	else \
		echo "Aucun PID MLflow trouve"; \
	fi

start: postgres api app
	@echo ""
	@echo "$(PROJECT_NAME) lance."
	@echo "API: http://$(API_HOST):$(API_PORT)"
	@echo "App: http://$(APP_HOST):$(APP_PORT)"

stop: api-stop app-stop mlflow-stop postgres-stop

restart: stop start

status:
	@echo "Docker/PostgreSQL:"
	@docker compose ps || true
	@echo ""
	@echo "Process locaux:"
	@if [ -f "$(API_PID)" ] && kill -0 "$$(cat $(API_PID))" 2>/dev/null; then \
		echo "API running pid=$$(cat $(API_PID)) http://$(API_HOST):$(API_PORT)"; \
	else \
		echo "API stopped http://$(API_HOST):$(API_PORT)"; \
	fi
	@if [ -f "$(APP_PID)" ] && kill -0 "$$(cat $(APP_PID))" 2>/dev/null; then \
		echo "APP running pid=$$(cat $(APP_PID)) http://$(APP_HOST):$(APP_PORT)"; \
	else \
		echo "APP stopped http://$(APP_HOST):$(APP_PORT)"; \
	fi
	@if [ -f "$(MLFLOW_PID)" ] && kill -0 "$$(cat $(MLFLOW_PID))" 2>/dev/null; then \
		echo "MLFLOW running pid=$$(cat $(MLFLOW_PID)) http://$(MLFLOW_HOST):$(MLFLOW_PORT)"; \
	else \
		echo "MLFLOW stopped http://$(MLFLOW_HOST):$(MLFLOW_PORT)"; \
	fi

data-status:
	@$(PYTHON) -c "from pathlib import Path; files=['data/raw/retainflow_csv/dim_customer.csv','data/raw/retainflow_csv/customer_360_snapshot.csv','data/raw/retainflow_csv/churn_label.csv','reports/tables/retention_priority_queue.csv','reports/tables/retention_recommendation.csv','reports/tables/shap_summary.csv'];\
print('Artefacts RetainFlow');\
[print(f'{f}: {sum(1 for _ in Path(f).open(encoding=\"utf-8\"))-1} rows' if Path(f).exists() else f'{f}: missing') for f in files]"

test:
	$(POETRY) run pytest

lint:
	$(POETRY) run ruff check .

format:
	$(POETRY) run ruff format .

clean-logs:
	rm -f $(API_LOG) $(APP_LOG) $(MLFLOW_LOG)
