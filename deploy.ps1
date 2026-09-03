<#
.SYNOPSIS
    Script de déploiement et d'orchestration pour Azure Market Insights ELT.

.DESCRIPTION
    Ce script automatise la configuration de l'environnement, le lancement
    de l'infrastructure locale (PostgreSQL + Azurite), l'installation des
    dépendances, l'application des schémas DDL et l'exécution des tests.

.PARAMETER Action
    L'action à exécuter: 'setup' (par défaut), 'check', 'up', 'down', 'pipeline', 'app', 'test'.
#>

param(
    [Parameter(Position=0)]
    [ValidateSet("setup", "check", "up", "down", "pipeline", "app", "test", "help")]
    [string]$Action = "setup"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

function Write-Step {
    param([string]$Message)
    Write-Host "`n🚀 [DEPLOIEMENT] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✅ [SUCCES] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "⚠️  [ATTENTION] $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "❌ [ERREUR] $Message" -ForegroundColor Red
}

function Test-Prerequisites {
    Write-Step "Vérification des prérequis système..."

    # 1. Check Python
    try {
        $pyVer = python --version 2>&1
        Write-Host "  • Python détecté : $pyVer" -ForegroundColor Gray
    } catch {
        Write-Fail "Python 3.13+ est requis mais n'a pas été trouvé dans le PATH."
        exit 1
    }

    # 2. Check uv
    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uvCmd) {
        Write-Warn "uv n'a pas été trouvé dans le PATH. Installation recommandée: https://docs.astral.sh/uv/"
        Write-Host "  Tentative d'utilisation de Python direct..." -ForegroundColor Gray
    } else {
        $uvVer = uv --version
        Write-Host "  • uv détecté : $uvVer" -ForegroundColor Gray
    }

    # 3. Check Docker
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCmd) {
        Write-Warn "Docker n'est pas disponible dans le PATH. Assurez-vous d'avoir une base PostgreSQL et Azurite active."
    } else {
        Write-Host "  • Docker détecté" -ForegroundColor Gray
    }
}

function Setup-EnvironmentFile {
    Write-Step "Vérification de la configuration d'environnement (.env)..."
    if (-not (Test-Path ".env")) {
        if (Test-Path "example.env") {
            Copy-Item "example.env" ".env"
            Write-Warn "Fichier .env créé à partir de example.env !"
            Write-Warn "Veuillez renseigner vos identifiants Twitch (TWITCH_CLIENT_ID / SECRET) dans le fichier .env."
        } else {
            Write-Fail "Fichier example.env introuvable pour initialiser .env"
            exit 1
        }
    } else {
        Write-Success "Fichier .env présent."
    }
}

function Start-Containers {
    Write-Step "Démarrage des conteneurs locaux (PostgreSQL + Azurite)..."
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if ($dockerCmd) {
        docker compose up -d
        Write-Success "Conteneurs démarrés via Docker Compose."
        
        Write-Host "  Attente de la disponibilité de PostgreSQL (port 5432)..." -ForegroundColor Gray
        Start-Sleep -Seconds 3
    } else {
        Write-Warn "Docker absent, étape sautée. Assurez-vous que Postgres et Azurite tournent localement."
    }
}

function Stop-Containers {
    Write-Step "Arrêt des conteneurs locaux..."
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if ($dockerCmd) {
        docker compose down
        Write-Success "Conteneurs arrêtés."
    }
}

function Sync-Dependencies {
    Write-Step "Synchronisation des dépendances avec uv..."
    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvCmd) {
        uv sync
        Write-Success "Dépendances synchronisées avec succès."
    } else {
        pip install -e .
        Write-Success "Dépendances installées via pip."
    }
}

function Apply-DatabaseMigrations {
    Write-Step "Application des schémas de base de données (logs_schemas.sql)..."
    $pythonExec = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }

    $initScript = @"
import os
from src.database.auth import init_database_engine
from src.database.core import execute_sql_from_file

pool = init_database_engine()
if not pool:
    print('DATABASE_POOL_ERROR: Impossible de se connecter à la base de données. Vérifiez votre .env et vos conteneurs.')
    exit(1)

ddl_path = os.path.join('src', 'database', 'models', 'log_schemas.sql')
try:
    execute_sql_from_file(pool, ddl_path)
    print('MIGRATIONS_OK')
except Exception as e:
    print(f'MIGRATION_ERROR: {e}')
    exit(1)
"@

    $res = & $pythonExec -c $initScript 2>&1
    if ($res -match "MIGRATIONS_OK") {
        Write-Success "Schémas et tables de gouvernance appliqués avec succès dans PostgreSQL."
    } else {
        Write-Warn "Impossible d'appliquer automatiquement les migrations SQL : $res"
        Write-Warn "Vérifiez que PostgreSQL est bien démarré."
    }
}

function Run-Tests {
    Write-Step "Exécution des tests unitaires..."
    $pythonExec = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
    & $pythonExec -m unittest discover tests/public
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Tous les tests unitaires ont réussi !"
    } else {
        Write-Fail "Certains tests unitaires ont échoué."
        exit 1
    }
}

function Run-Pipeline {
    Write-Step "Lancement du pipeline ELT (main.py)..."
    $pythonExec = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
    & $pythonExec main.py
}

function Run-App {
    Write-Step "Démarrage du Dashboard de Gouvernance (app/server.py)..."
    Write-Host "  Accès web local : http://localhost:5000" -ForegroundColor Green
    $pythonExec = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
    & $pythonExec app/server.py
}

# --- Router d'actions ---
switch ($Action) {
    "setup" {
        Test-Prerequisites
        Setup-EnvironmentFile
        Start-Containers
        Sync-Dependencies
        Apply-DatabaseMigrations
        Run-Tests
        Write-Host "`n🎉 [TERMINE] L'environnement est prêt !" -ForegroundColor Green
        Write-Host "  • Lancer le pipeline : .\deploy.ps1 pipeline" -ForegroundColor Gray
        Write-Host "  • Lancer le dashboard: .\deploy.ps1 app" -ForegroundColor Gray
    }
    "check" {
        Test-Prerequisites
        Setup-EnvironmentFile
        Sync-Dependencies
        Run-Tests
        Write-Success "Vérification d'intégrité terminée avec succès."
    }
    "up" {
        Start-Containers
    }
    "down" {
        Stop-Containers
    }
    "test" {
        Run-Tests
    }
    "pipeline" {
        Run-Pipeline
    }
    "app" {
        Run-App
    }
    "help" {
        Write-Host "Usage: .\deploy.ps1 [setup|check|up|down|test|pipeline|app|help]"
    }
}
