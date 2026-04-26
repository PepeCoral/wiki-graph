A Python application that builds and explores a graph of Wikipedia articles
using **Neo4j** as the graph database.


## Prerequisites

### 1. Python 3.11+

```bash
python --version   # must be 3.11 or higher
```

### 2. Neo4j

#### Docker

```bash
docker run \
  --name neo4j-wiki \
  --hostname neo4j-wiki \
  -p 7474:7474 -p 7687:7687 \
  -v neo4j-data:/data \
  -e NEO4J_AUTH=neo4j/password \
  -e NEO4J_PLUGINS='["apoc"]' \
  -e NEO4J_apoc_export_file_enabled=true \
  -e NEO4J_apoc_import_file_enabled=true \
  --memory=4g \
  neo4j:5.19.0

# Verify it's up
open http://localhost:7474
```

## Installation

```bash
# Clone / enter the project 
git clone https://github.com/PepeCoral/wiki-graph.git
cd wiki-graph

# Create a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Running the application

```bash
streamlit run app.py
```

The UI will open at **http://localhost:8501**.

