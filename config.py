import os
from pathlib import Path

# Base Paths
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
PATHFINDER_DIR = WORKSPACE_DIR / "pathfinder"
STRATEGY_FILE = WORKSPACE_DIR / "live_trading_strategies_local" / "strategy.py"
RESULTS_DIR = PATHFINDER_DIR / "results"

# Ensure directories exist
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Simple custom dotenv loader to read .env file
def load_dotenv():
    env_file = PATHFINDER_DIR / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        k, v = line.split("=", 1)
                        # Strip quotes if present
                        val = v.strip().strip("'\"")
                        os.environ[k.strip()] = val

# Load .env variables before config resolution
load_dotenv()

# API Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
MOONSHOT_API_KEY = os.environ.get("MOONSHOT_API_KEY", os.environ.get("KIMI_API_KEY", ""))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Vertex AI Configuration
USE_VERTEXAI = os.environ.get("USE_VERTEXAI", "false").lower() == "true"
GCP_PROJECT = os.environ.get("GCP_PROJECT", "")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "us-central1")

if GCP_PROJECT:
    os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = GCP_PROJECT

# LLM Providers and Models
RESEARCH_PROVIDER = os.environ.get("RESEARCH_PROVIDER", "gemini")
RESEARCH_MODEL = os.environ.get("RESEARCH_MODEL", "gemini-2.5-flash")

GENERATOR_PROVIDER = os.environ.get("GENERATOR_PROVIDER", "openrouter")
GENERATOR_MODEL = os.environ.get("GENERATOR_MODEL", "openrouter/free")

# Fallback for code expecting MODEL_NAME
MODEL_NAME = RESEARCH_MODEL


# Search Parameters
C_PUCT = 1.4              # Exploration parameter
SEARCH_MODE = os.environ.get("SEARCH_MODE", "puct")  # Search algorithm: 'puct' or 'mcts'
ROOT_NUM_CHILDREN = 10    # Breadth of expansion for the root node
NUM_CHILDREN = 1          # Breadth of expansion for subsequent nodes
MAX_ITERATIONS = 10       # Number of MCTS selection/expansion loops
SANDBOX_TIMEOUT = 600     # Subprocess execution timeout in seconds


# Evaluation defaults
DEFAULT_START_DATE = "2026-04-01"
DEFAULT_END_DATE = "2026-04-05"
DEFAULT_TEST_STRATEGY = "combined"  # Options: combined, random_30_days, random_range, random_days, random_hours, fixed
USE_CHARGES = os.environ.get("USE_CHARGES", "true").lower() == "true"
