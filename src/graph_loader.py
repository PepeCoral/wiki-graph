import csv
import logging
from pathlib import Path
from typing import Callable, Optional

from neo4j import GraphDatabase, Driver

import config

logger = logging.getLogger(__name__)


def get_driver() -> Driver:
    return GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
    )


_CONSTRAINT_QUERY = (
    "CREATE CONSTRAINT page_title_unique IF NOT EXISTS "
    "FOR (p:Page) REQUIRE p.title IS UNIQUE"
)

_INDEX_QUERY = (
    "CREATE INDEX page_title_idx IF NOT EXISTS "
    "FOR (p:Page) ON (p.title)"
)


def ensure_schema(driver: Driver) -> None:
    with driver.session() as session:
        session.run(_CONSTRAINT_QUERY)
        logger.info("Constraint ensured: Page.title IS UNIQUE")


_MERGE_NODES_QUERY = """
UNWIND $titles AS t
MERGE (:Page {title: t})
"""

_MERGE_RELS_QUERY = """
UNWIND $pairs AS pair
MATCH (src:Page {title: pair[0]})
MATCH (tgt:Page {title: pair[1]})
MERGE (src)-[:LINKS_TO]->(tgt)
"""


def _flush_nodes(session, titles: list[str]) -> None:
    session.run(_MERGE_NODES_QUERY, titles=titles)


def _flush_rels(session, pairs: list[tuple[str, str]]) -> None:
    session.run(_MERGE_RELS_QUERY, pairs=[[s, t] for s, t in pairs])


def load_csv(
    csv_path: Path,
    driver: Optional[Driver] = None,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"Links CSV not found: {csv_path}")

    _driver = driver or get_driver()
    ensure_schema(_driver)

    batch_size = config.NEO4J_BATCH_SIZE
    commit_every = config.LOADER_COMMIT_EVERY

    logger.info("Pass 1: creating Page nodes…")
    title_buf: list[str] = []
    total_nodes = 0

    with _driver.session() as session:
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh, delimiter="\t")
            for row in reader:
                if len(row) < 2:
                    continue
                src, tgt = row[0], row[1]
                title_buf.append(src)
                title_buf.append(tgt)

                if len(title_buf) >= batch_size * 2:
                    _flush_nodes(session, list(set(title_buf)))
                    total_nodes += len(title_buf)
                    title_buf.clear()

                    if total_nodes % commit_every == 0:
                        logger.info("  Nodes pass: %d titles processed", total_nodes)

        if title_buf:
            _flush_nodes(session, list(set(title_buf)))
            total_nodes += len(title_buf)

    logger.info("Pass 1 complete: ~%d titles seen", total_nodes)

    logger.info("Pass 2: creating LINKS_TO relationships…")
    rel_buf: list[tuple[str, str]] = []
    total_rels = 0

    with _driver.session() as session:
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh, delimiter="\t")
            for row in reader:
                if len(row) < 2:
                    continue
                rel_buf.append((row[0], row[1]))

                if len(rel_buf) >= batch_size:
                    _flush_rels(session, rel_buf)
                    total_rels += len(rel_buf)
                    rel_buf.clear()

                    if progress_cb:
                        progress_cb(total_rels)
                    if total_rels % commit_every == 0:
                        logger.info("  Rels pass: %d relationships created", total_rels)

        if rel_buf:
            _flush_rels(session, rel_buf)
            total_rels += len(rel_buf)
            if progress_cb:
                progress_cb(total_rels)

    logger.info("Pass 2 complete: %d relationships created", total_rels)

    if driver is None:
        _driver.close()


def load_small(
    driver: Optional[Driver] = None,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> None:
    load_csv(config.SMALL_LINKS_CSV, driver, progress_cb)


def load_full(
    driver: Optional[Driver] = None,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> None:
    load_csv(config.FULL_LINKS_CSV, driver, progress_cb)


def clear_graph(driver: Optional[Driver] = None) -> None:
    _driver = driver or get_driver()
    batch = config.NEO4J_BATCH_SIZE

    with _driver.session() as session:
        while True:
            result = session.run(
                "MATCH ()-[r]->() "
                "WITH r LIMIT $batch "
                "DELETE r "
                "RETURN count(r) AS deleted",
                batch=batch,
            )
            deleted = result.single()["deleted"]
            logger.info("  Cleared %d relationships", deleted)
            if deleted == 0:
                break

        while True:
            result = session.run(
                "MATCH (n) "
                "WITH n LIMIT $batch "
                "DETACH DELETE n "
                "RETURN count(n) AS deleted",
                batch=batch,
            )
            deleted = result.single()["deleted"]
            logger.info("  Cleared %d nodes", deleted)
            if deleted == 0:
                break

    logger.info("Graph cleared.")
    if driver is None:
        _driver.close()