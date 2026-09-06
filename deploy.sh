#!/usr/bin/env bash
# ==================================================================
# Azure Market Insights ELT - Linux/macOS/WSL Deployment Script
# ==================================================================
set -e

ACTION="${1:-all}"
INTERVAL_MINUTES="${2:-15}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

write_step() { echo -e "\n${CYAN}🚀 [DEPLOY] $1${NC}"; }
write_success() { echo -e "${GREEN}✅ [SUCCESS] $1${NC}"; }
write_warn() { echo -e "${YELLOW}⚠️  [WARNING] $1${NC}"; }
write_fail() { echo -e "${RED}❌ [ERROR] $1${NC}"; }

test_prerequisites() {
    write_step "Checking prerequisites..."
    if command -v python3 &>/dev/null; then
        echo "  • Python: $(python3 --version)"
    else
        write_fail "Python 3.13+ is required but not found in PATH."
        exit 1
    fi

    if command -v uv &>/dev/null; then
        echo "  • uv: $(uv --version)"
    else
        write_warn "uv not found in PATH. Consider installing: https://docs.astral.sh/uv/"
    fi

    if command -v docker &>/dev/null; then
        echo "  • Docker detected"
    else
        write_warn "Docker not detected. Ensure local PostgreSQL and Azurite are accessible."
    fi
}

setup_env_file() {
    write_step "Verifying .env configuration..."
    if [ ! -f ".env" ]; then
        if [ -f "example.env" ]; then
            cp example.env .env
            write_warn "Created .env from example.env. Please configure your Twitch API keys!"
        else
            write_fail "example.env not found."
            exit 1
        fi
    else
        write_success ".env file exists."
    fi
}

start_containers() {
    write_step "Starting Docker Compose services (PostgreSQL + Azurite)..."
    if command -v docker &>/dev/null; then
        docker compose up -d
        write_success "Containers started."
        sleep 3
    else
        write_warn "Docker not found, skipping container launch."
    fi
}

stop_containers() {
    write_step "Stopping Docker Compose services..."
    if command -v docker &>/dev/null; then
        docker compose down
        write_success "Containers stopped."
    fi
}

sync_dependencies() {
    write_step "Syncing dependencies..."
    if command -v uv &>/dev/null; then
        uv sync
        write_success "Dependencies synchronized via uv."
    else
        pip install -e .
        write_success "Dependencies installed via pip."
    fi
}

get_python_cmd() {
    if [ -f ".venv/bin/python" ]; then
        echo ".venv/bin/python"
    elif [ -f ".venv/Scripts/python.exe" ]; then
        echo ".venv/Scripts/python.exe"
    else
        echo "python3"
    fi
}

apply_migrations() {
    write_step "Applying database migrations (log_schemas.sql)..."
    PYTHON_CMD=$(get_python_cmd)
    
    python_script='
import os
from src.database.auth import init_database_engine
from src.database.core import execute_sql_from_file

pool = init_database_engine()
if not pool:
    print("DB_CONN_FAIL")
    exit(1)

ddl_path = os.path.join("src", "database", "models", "log_schemas.sql")
try:
    execute_sql_from_file(pool, ddl_path)
    print("MIGRATIONS_OK")
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
'
    res=$("$PYTHON_CMD" -c "$python_script" 2>&1 || true)
    if [[ "$res" == *"MIGRATIONS_OK"* ]]; then
        write_success "Governance schemas and tables applied."
    else
        write_warn "Could not apply migrations automatically: $res"
    fi
}

run_tests() {
    write_step "Running unit tests..."
    PYTHON_CMD=$(get_python_cmd)
    "$PYTHON_CMD" -m unittest discover tests/public
    write_success "All unit tests passed!"
}

run_pipeline() {
    write_step "Starting ELT Pipeline (main.py)..."
    PYTHON_CMD=$(get_python_cmd)
    "$PYTHON_CMD" main.py
}

open_browser() {
    local url="${1:-http://localhost:5000}"
    write_step "Opening browser at $url..."
    if command -v xdg-open &>/dev/null; then
        xdg-open "$url" &>/dev/null &
    elif command -v open &>/dev/null; then
        open "$url" &>/dev/null &
    elif command -v wslview &>/dev/null; then
        wslview "$url" &>/dev/null &
    else
        echo -e "${YELLOW}Could not open browser automatically. Please open: $url${NC}"
    fi
}

run_app() {
    write_step "Starting Governance Dashboard (app/server.py)..."
    echo -e "${GREEN}  Dashboard available at: http://localhost:5000${NC}"
    open_browser "http://localhost:5000"
    PYTHON_CMD=$(get_python_cmd)
    "$PYTHON_CMD" app/server.py
}

run_schedule() {
    local interval="${1:-15}"
    write_step "Continuous Scheduler: running pipeline automatically every $interval minute(s)..."
    echo "Press Ctrl+C to stop."
    run_pipeline
    while true; do
        echo -e "\n${CYAN}⏳ Next execution in $interval minute(s)...${NC}"
        sleep "$((interval * 60))"
        run_pipeline
    done
}

case "$ACTION" in
    all)
        test_prerequisites
        setup_env_file
        start_containers
        sync_dependencies
        apply_migrations
        run_tests
        run_pipeline
        echo -e "\n${GREEN}🎉 [READY] Pipeline completed! Launching dashboard...${NC}"
        run_app
        ;;
    setup)
        test_prerequisites
        setup_env_file
        start_containers
        sync_dependencies
        apply_migrations
        run_tests
        echo -e "\n${GREEN}🎉 [DONE] Environment ready!${NC}"
        echo "  • Run all-in-one : ./deploy.sh all"
        echo "  • Run pipeline   : ./deploy.sh pipeline"
        echo "  • Run scheduler  : ./deploy.sh schedule 15"
        echo "  • Run dashboard  : ./deploy.sh app"
        ;;
    check)
        test_prerequisites
        setup_env_file
        sync_dependencies
        run_tests
        write_success "System integrity check passed."
        ;;
    up)
        start_containers
        ;;
    down)
        stop_containers
        ;;
    test)
        run_tests
        ;;
    pipeline)
        run_pipeline
        ;;
    schedule)
        run_schedule "$INTERVAL_MINUTES"
        ;;
    app)
        run_app
        ;;
    help|*)
        echo "Usage: ./deploy.sh [all|setup|check|up|down|test|pipeline|schedule|app|help] [interval_minutes]"
        echo ""
        echo "Actions:"
        echo "  all       : (Default) Full setup, test, run pipeline, open browser and launch dashboard"
        echo "  setup     : Prepare containers, dependencies, migrations and tests"
        echo "  pipeline  : Run single ELT batch (main.py)"
        echo "  schedule  : Run ELT pipeline in continuous loop (default: every 15 min)"
        echo "  app       : Open browser and start Flask governance dashboard"
        echo "  test      : Run unit tests suite"
        echo "  check     : Verify system prerequisites and environment"
        echo "  up        : Start Docker containers (PostgreSQL + Azurite)"
        echo "  down      : Stop Docker containers"
        echo "  help      : Display this message"
        ;;
esac
