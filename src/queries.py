import logging
from typing import Any, Dict, List, Optional

from neo4j import Driver

import config

logger = logging.getLogger(__name__)


_ISOLATED_QUERY = """
MATCH (p:Page)
WHERE NOT (p)-[:LINKS_TO]->()
  AND NOT ()-[:LINKS_TO]->(p)
RETURN p.title AS title
LIMIT $limit
"""

_ISOLATED_COUNT_QUERY = """
MATCH (p:Page)
WHERE NOT (p)-[:LINKS_TO]->()
  AND NOT ()-[:LINKS_TO]->(p)
RETURN count(p) AS total
"""


def find_isolated_pages(
    driver: Driver,
    limit: int = config.ISOLATED_PAGES_LIMIT,
) -> Dict[str, Any]:
    with driver.session() as session:
        total_rec = session.run(_ISOLATED_COUNT_QUERY).single()
        total = total_rec["total"] if total_rec else 0

        result = session.run(_ISOLATED_QUERY, limit=limit)
        pages = [r["title"] for r in result]

    logger.info("Isolated pages: %d total, returning %d", total, len(pages))
    return {"pages": pages, "total": total}



_GDS_WCC_QUERY = """
CALL gds.wcc.stats('wiki-graph')
YIELD componentCount, componentDistribution
RETURN componentCount,
       componentDistribution.max AS largestComponentSize
"""

_APOC_COMPONENT_SEED_QUERY = """
MATCH (seed:Page)
WITH seed LIMIT 1
CALL apoc.path.subgraphNodes(seed, {
    relationshipFilter: 'LINKS_TO',
    bfs: true
}) YIELD node
RETURN count(node) AS largestComponentSize
"""

_CYPHER_LARGEST_COMPONENT_QUERY = """
MATCH (seed:Page)
WITH seed LIMIT 1
MATCH (seed)-[:LINKS_TO*0..12]-(reachable)
RETURN count(DISTINCT reachable) AS largestComponentSize
"""

_CYPHER_COUNT_SINGLETONS_QUERY = """
MATCH (p:Page)
WHERE NOT (p)-[:LINKS_TO]-() AND NOT ()-[:LINKS_TO]->(p)
RETURN count(p) AS singletons
"""

_TOTAL_PAGES_QUERY = "MATCH (p:Page) RETURN count(p) AS total"
_TOTAL_RELS_QUERY  = "MATCH ()-[r:LINKS_TO]->() RETURN count(r) AS total"



def _has_apoc(driver: Driver) -> bool:
    try:
        with driver.session() as session:
            result = session.run(
                "CALL apoc.path.subgraphNodes($n, {maxLevel: 0}) YIELD node RETURN node LIMIT 0",
                n=None,
            )
            list(result)
        return True
    except Exception:
        return False


def _ensure_gds_projection(driver: Driver) -> None:
    with driver.session() as session:
        try:
            session.run("CALL gds.graph.drop('wiki-graph', false) YIELD graphName")
        except Exception:
            pass
        session.run(
        )


def connected_components(driver: Driver) -> Dict[str, Any]:
    with driver.session() as s:
        total_pages = s.run(_TOTAL_PAGES_QUERY).single()["total"]
        total_rels  = s.run(_TOTAL_RELS_QUERY).single()["total"]

    base = {"total_pages": total_pages, "total_relationships": total_rels}

    if _has_apoc(driver):
        logger.info("WCC: using APOC path BFS")
        try:
            with driver.session() as s:
                seed_rec = s.run(
                    "MATCH (p:Page)-[:LINKS_TO]->() "
                    "RETURN p ORDER BY rand() LIMIT 1"
                ).single()

                if seed_rec:
                    seed = seed_rec["p"]
                    size_rec = s.run(
                        """
                        CALL apoc.path.subgraphNodes($seed, {
                            relationshipFilter: 'LINKS_TO>|<LINKS_TO',
                            bfs: true
                        }) YIELD node
                        RETURN count(node) AS largestComponentSize
                        """,
                        seed=seed,
                    ).single()
                    largest = size_rec["largestComponentSize"] if size_rec else 0
                else:
                    largest = 0

                singletons_rec = s.run(_CYPHER_COUNT_SINGLETONS_QUERY).single()
                singletons = singletons_rec["singletons"] if singletons_rec else 0

            estimated_count = 1 + singletons
            base.update(
                component_count=estimated_count,
                largest_component_size=largest,
                method="APOC path BFS (component count is lower bound; size of largest is exact)",
            )
            return base
        except Exception as e:
            logger.warning("APOC WCC failed: %s", e)

    logger.warning("WCC: no plugins — using pure-Cypher BFS approximation")
    with driver.session() as s:
        largest_rec = s.run(_CYPHER_LARGEST_COMPONENT_QUERY).single()
        largest = largest_rec["largestComponentSize"] if largest_rec else 0

        singletons_rec = s.run(_CYPHER_COUNT_SINGLETONS_QUERY).single()
        singletons = singletons_rec["singletons"] if singletons_rec else 0

    base.update(
        component_count=1 + singletons,
        largest_component_size=largest,
    )
    return base



_PAGE_EXISTS_QUERY = "MATCH (p:Page {title: $title}) RETURN p LIMIT 1"


def _build_shortest_path_query(max_depth: int) -> str:
    return f"""
MATCH (src:Page {{title: $src_title}}),
      (tgt:Page {{title: $tgt_title}}),
      path = shortestPath((src)-[:LINKS_TO*1..{max_depth}]->(tgt))
RETURN [node IN nodes(path) | node.title] AS path,
       length(path) AS hops
"""


def shortest_path(
    driver: Driver,
    src_title: str,
    tgt_title: str,
    max_depth: int = config.SHORTEST_PATH_MAX_DEPTH,
) -> Dict[str, Any]:
    query = _build_shortest_path_query(max_depth)

    with driver.session() as session:
        for title in (src_title, tgt_title):
            rec = session.run(_PAGE_EXISTS_QUERY, title=title).single()
            if rec is None:
                return {
                    "found": False,
                    "path": [],
                    "hops": -1,
                    "error": f"Page not found in graph: '{title}'",
                }

        result = session.run(
            query,
            src_title=src_title,
            tgt_title=tgt_title,
        ).single()

    if result is None:
        return {
            "found": False,
            "path": [],
            "hops": -1,
            "error": f"No path found within {max_depth} hops.",
        }

    return {
        "found": True,
        "path": result["path"],
        "hops": result["hops"],
        "error": None,
    }

def graph_stats(driver: Driver) -> Dict[str, int]:
    with driver.session() as s:
        pages = s.run(_TOTAL_PAGES_QUERY).single()["total"]
        rels  = s.run(_TOTAL_RELS_QUERY).single()["total"]
    return {"pages": pages, "relationships": rels}


_SEARCH_QUERY = """
MATCH (p:Page)
WHERE p.title STARTS WITH $prefix
RETURN p.title AS title
ORDER BY p.title
LIMIT $limit
"""


def search_pages(driver: Driver, prefix: str, limit: int = 20) -> List[str]:
    with driver.session() as s:
        return [r["title"] for r in s.run(_SEARCH_QUERY, prefix=prefix, limit=limit)]



_NEIGHBORHOOD_NODE_CAP = 300


def _build_neighborhood_query(max_depth: int) -> str:
    return f"""
MATCH (origin:Page {{title: $origin_title}})
CALL {{
    WITH origin
    MATCH (origin)-[:LINKS_TO*1..{max_depth}]->(reachable:Page)
    RETURN DISTINCT reachable
    LIMIT {_NEIGHBORHOOD_NODE_CAP}
}}
WITH origin, collect(reachable) AS reachables
UNWIND reachables AS n
OPTIONAL MATCH (src)-[r:LINKS_TO]->(tgt)
WHERE src IN reachables + [origin]
  AND tgt IN reachables + [origin]
  AND src <> tgt
RETURN
    src.title AS src_title,
    tgt.title AS tgt_title,
    n.title   AS node_title
"""


def neighborhood_graph(
    driver: Driver,
    origin_title: str,
    max_depth: int = 2,
) -> Dict[str, Any]:
    max_depth = max(1, min(max_depth, 6))

    with driver.session() as session:
        rec = session.run(_PAGE_EXISTS_QUERY, title=origin_title).single()
        if rec is None:
            return {
                "found": False,
                "nodes": [],
                "edges": [],
                "origin": origin_title,
                "error": f"Page not found in graph: '{origin_title}'",
            }

        depth_query = f"""
MATCH (origin:Page {{title: $origin_title}})
MATCH path = (origin)-[:LINKS_TO*1..{max_depth}]->(reachable:Page)
WITH reachable, min(length(path)) AS depth
RETURN reachable.title AS title, depth
ORDER BY depth, reachable.title
LIMIT {_NEIGHBORHOOD_NODE_CAP}
"""
        depth_rows = session.run(depth_query, origin_title=origin_title)
        node_depth: Dict[str, int] = {origin_title: 0}
        for row in depth_rows:
            node_depth[row["title"]] = row["depth"]

        nodes = [{"id": t, "depth": d} for t, d in node_depth.items()]

        if len(node_depth) > 1:
            titles = list(node_depth.keys())
            edge_query = """
MATCH (src:Page)-[:LINKS_TO]->(tgt:Page)
WHERE src.title IN $titles AND tgt.title IN $titles
RETURN src.title AS src_title, tgt.title AS tgt_title
"""
            edge_rows = session.run(edge_query, titles=titles)
            edges = [
                {"source": r["src_title"], "target": r["tgt_title"]}
                for r in edge_rows
            ]
        else:
            edges = []

    logger.info(
        "Neighborhood of '%s' depth=%d: %d nodes, %d edges",
        origin_title, max_depth, len(nodes), len(edges),
    )
    return {
        "found": True,
        "nodes": nodes,
        "edges": edges,
        "origin": origin_title,
        "error": None,
    }


def top_pages_by_indegree(driver, limit: int = 20) -> list[dict]:
    query = """
        MATCH (p:Page)
        WHERE (()-[:LINKS_TO]->(p))
        RETURN p.title AS title, count{ ()-[:LINKS_TO]->(p) } AS in_degree
        ORDER BY in_degree DESC
        LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [{"title": r["title"], "in_degree": r["in_degree"]} for r in result]


def top_pages_by_outdegree(driver, limit: int = 20) -> list[dict]:
    query = """
        MATCH (p:Page)
        WHERE (p)-[:LINKS_TO]->()
        RETURN p.title AS title, count{ (p)-[:LINKS_TO]->() } AS out_degree
        ORDER BY out_degree DESC
        LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [{"title": r["title"], "out_degree": r["out_degree"]} for r in result]


def top_pages_by_total_degree(driver, limit: int = 20) -> list[dict]:
    query = """
        MATCH (p:Page)
        WITH p,
             count{ ()-[:LINKS_TO]->(p) } AS in_deg,
             count{ (p)-[:LINKS_TO]->() } AS out_deg
        WITH p, in_deg, out_deg, (in_deg + out_deg) AS total_deg
        WHERE total_deg > 0
        RETURN p.title    AS title,
               in_deg     AS in_degree,
               out_deg    AS out_degree,
               total_deg  AS total_degree
        ORDER BY total_degree DESC
        LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [
            {
                "title":        r["title"],
                "in_degree":    r["in_degree"],
                "out_degree":   r["out_degree"],
                "total_degree": r["total_degree"],
            }
            for r in result
        ]


def find_no_incoming(driver, limit: int = 200) -> dict:
    query = """
        MATCH (p:Page)
        WHERE NOT ()-[:LINKS_TO]->(p)
        RETURN count(p) AS total, collect(p.title)[..$limit] AS pages
    """
    with driver.session() as session:
        r = session.run(query, limit=limit).single()
        return {"total": r["total"], "pages": list(r["pages"])}


def find_no_outgoing(driver, limit: int = 200) -> dict:
    query = """
        MATCH (p:Page)
        WHERE NOT (p)-[:LINKS_TO]->()
        RETURN count(p) AS total, collect(p.title)[..$limit] AS pages
    """
    with driver.session() as session:
        r = session.run(query, limit=limit).single()
        return {"total": r["total"], "pages": list(r["pages"])}


def top_pages_by_indegree(driver, limit: int = 20) -> list[dict]:
    query = """
        MATCH (p:Page)
        WHERE (()-[:LINKS_TO]->(p))
        RETURN p.title AS title, count{ ()-[:LINKS_TO]->(p) } AS in_degree
        ORDER BY in_degree DESC
        LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [{"title": r["title"], "in_degree": r["in_degree"]} for r in result]


def top_pages_by_outdegree(driver, limit: int = 20) -> list[dict]:
    query = """
        MATCH (p:Page)
        WHERE (p)-[:LINKS_TO]->()
        RETURN p.title AS title, count{ (p)-[:LINKS_TO]->() } AS out_degree
        ORDER BY out_degree DESC
        LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [{"title": r["title"], "out_degree": r["out_degree"]} for r in result]


def top_pages_by_total_degree(driver, limit: int = 20) -> list[dict]:
    query = """
        MATCH (p:Page)
        WITH p,
             count{ ()-[:LINKS_TO]->(p) } AS in_deg,
             count{ (p)-[:LINKS_TO]->() } AS out_deg
        WITH p, in_deg, out_deg, (in_deg + out_deg) AS total_deg
        WHERE total_deg > 0
        RETURN p.title    AS title,
               in_deg     AS in_degree,
               out_deg    AS out_degree,
               total_deg  AS total_degree
        ORDER BY total_degree DESC
        LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [
            {
                "title":        r["title"],
                "in_degree":    r["in_degree"],
                "out_degree":   r["out_degree"],
                "total_degree": r["total_degree"],
            }
            for r in result
        ]