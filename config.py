import os
from pathlib import Path

# Paths
BASE_DIR       = Path(__file__).parent
DATA_RAW_DIR   = BASE_DIR / "data" / "raw"
DATA_PROC_DIR  = BASE_DIR / "data" / "processed"

DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_PROC_DIR.mkdir(parents=True, exist_ok=True)

# Small Wikipedia
SMALL_DUMP_URL  = "https://dumps.wikimedia.org/simplewiki/latest/simplewiki-latest-pages-articles.xml.bz2"
SMALL_DUMP_FILE = DATA_RAW_DIR / "simplewiki-latest-pages-articles.xml.bz2"
SMALL_LINKS_CSV = DATA_PROC_DIR / "simplewiki_links.csv"

# ESWIki
FULL_DUMP_URL   = "https://dumps.wikimedia.org/eswiki/latest/eswiki-latest-pages-articles.xml.bz2"
FULL_DUMP_FILE  = DATA_RAW_DIR / "eswiki-latest-pages-articles.xml.bz2"
FULL_LINKS_CSV  = DATA_PROC_DIR / "eswiki_links.csv"

# Neo4j
NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Parser settings
ARTICLE_NAMESPACE = 0

# Loader settings 
NEO4J_BATCH_SIZE = 5_000
LOADER_COMMIT_EVERY = 50_000

# Query settings
ISOLATED_PAGES_LIMIT    = 200
COMPONENTS_SAMPLE_LIMIT = 20
SHORTEST_PATH_MAX_DEPTH = 200
