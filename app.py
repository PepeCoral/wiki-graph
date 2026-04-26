import sys
import logging
import threading
import time
import urllib.parse
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as st_components

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import config
import job_store
import src.downloader   as downloader
import src.parser       as parser
import src.graph_loader as loader
import src.queries      as queries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("app")

job_store.reconcile()

st.set_page_config(
    page_title="Wikipedia Graph Explorer",
    page_icon="🌐",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;700&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.app-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #0f172a 100%);
    border-bottom: 2px solid #3b82f6;
    padding: 2rem 2.5rem 1.5rem;
    margin: -4rem -4rem 2rem;
    position: relative; overflow: hidden;
}
.app-header::before {
    content: ""; position: absolute; inset: 0;
    background: radial-gradient(ellipse 80% 60% at 70% 50%, rgba(59,130,246,.18) 0%, transparent 70%);
}
.app-header h1 {
    font-family: 'Space Mono', monospace; font-size: 1.9rem; font-weight: 700;
    color: #f0f9ff; margin: 0 0 .4rem; letter-spacing: -0.5px; position: relative;
}
.app-header p { color: #93c5fd; font-size: .95rem; margin: 0; position: relative; }

.section-title {
    font-family: 'Space Mono', monospace; font-size: .8rem; font-weight: 700;
    letter-spacing: 3px; text-transform: uppercase; color: #3b82f6;
    margin-bottom: 1.2rem; padding-bottom: .6rem; border-bottom: 1px solid #1e3a5f;
}

/*  Path chain  */
.path-chain {
    display: flex; flex-wrap: wrap; align-items: center; gap: .4rem;
    background: #0c1524; border: 1px solid #1e3a5f; border-radius: 10px;
    padding: 1.2rem 1.4rem; margin-top: .8rem;
}
.path-node {
    background: #1e3a5f; color: #bfdbfe;
    font-family: 'Space Mono', monospace; font-size: .8rem;
    padding: .35rem .75rem; border-radius: 5px;
    white-space: nowrap; border: 1px solid transparent;
}
.path-node.node-src { background:#14532d; color:#86efac; border-color:#16a34a; }
.path-node.node-dst { background:#7c2d12; color:#fdba74; border-color:#ea580c; }
.path-arrow { color: #3b82f6; font-size: 1.1rem; user-select: none; }

/*  Wikipedia viewer  */
.wiki-viewer-bar {
    display: flex; align-items: center; gap: .6rem;
    background: #0f172a; border: 1px solid #1e3a5f;
    border-radius: 8px 8px 0 0; padding: .6rem 1rem;
}
.wiki-viewer-title {
    font-family: 'Space Mono', monospace; font-size: .85rem; color: #60a5fa;
    flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.wiki-iframe-wrap {
    border: 1px solid #1e3a5f; border-top: none;
    border-radius: 0 0 8px 8px; overflow: hidden; background: #fff;
}

/*  Stat tiles  */
.stat-row { display: flex; gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap; }
.stat-tile {
    flex: 1 1 120px; background: #0c1524; border: 1px solid #1e3a5f;
    border-radius: 8px; padding: .8rem 1.2rem; text-align: center; min-width: 120px;
}
.stat-value {
    font-family: 'Space Mono', monospace; font-size: 1.5rem;
    font-weight: 700; color: #60a5fa; line-height: 1;
}
.stat-label { font-size: .75rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-top: .3rem; }

/*  Tag list  */
.tag-list { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .5rem; }
.tag {
    background: #0c1524; border: 1px solid #1e3a5f; color: #94a3b8;
    font-family: 'Space Mono', monospace; font-size: .75rem;
    padding: .25rem .6rem; border-radius: 4px;
    text-decoration: none; transition: background .15s;
}
.tag:hover { background: #1e3a5f; color: #bfdbfe; }

/*  Status chips  */
.chip-ok   { color: #4ade80; font-weight: 600; }
.chip-warn { color: #facc15; font-weight: 600; }
.chip-err  { color: #f87171; font-weight: 600; }

/*  Running job banner  */
.job-banner {
    display: flex; align-items: center; gap: .8rem;
    background: #172554; border: 1px solid #3b82f6;
    border-radius: 8px; padding: .75rem 1.2rem; margin-bottom: 1rem;
}
.job-pulse {
    width: 10px; height: 10px; border-radius: 50%;
    background: #3b82f6; animation: pulse 1.2s infinite; flex-shrink: 0;
}
@keyframes pulse {
    0%,100% { opacity:1; transform:scale(1); }
    50%      { opacity:.4; transform:scale(.8); }
}
.job-text { color: #93c5fd; font-size: .9rem; }

[data-testid="stSidebar"] { background: #0a0f1e; border-right: 1px solid #1e3a5f; }

/*  Stats bars  */
.stats-bar-row {
    display: flex; align-items: center; gap: .8rem;
    padding: .45rem .6rem; border-radius: 6px;
    margin-bottom: .35rem; transition: background .1s;
}
.stats-bar-row:hover { background: #0c1524; }
.stats-bar-rank { font-family: 'Space Mono', monospace; font-size: .7rem; color: #475569; width: 1.8rem; text-align: right; flex-shrink: 0; }
.stats-bar-label { font-size: .85rem; color: #cbd5e1; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stats-bar-track { flex: 2; background: #1e293b; border-radius: 3px; height: 8px; overflow: hidden; }
.stats-bar-fill { height: 100%; border-radius: 3px; transition: width .6s ease; }
.stats-bar-value { font-family: 'Space Mono', monospace; font-size: .75rem; color: #60a5fa; width: 4rem; text-align: right; flex-shrink: 0; }

/*  Task panel  */
.task-panel { background: #060d1a; border: 1px solid #1e3a5f; border-radius: 10px; overflow: hidden; margin-top: .5rem; }
.task-panel-header { display: flex; align-items: center; justify-content: space-between; padding: .6rem 1rem; background: #0c1a30; border-bottom: 1px solid #1e3a5f; }
.task-panel-title { font-family: 'Space Mono', monospace; font-size: .7rem; letter-spacing: 2px; text-transform: uppercase; color: #3b82f6; }
.task-panel-badge { font-family: 'Space Mono', monospace; font-size: .65rem; background: #1e3a5f; color: #60a5fa; padding: .1rem .45rem; border-radius: 10px; }
.task-panel-badge.badge-running { background: #172554; color: #93c5fd; animation: badgePulse 1.5s infinite; }
@keyframes badgePulse { 0%,100% { opacity:1; } 50% { opacity:.55; } }
.task-item { display: flex; align-items: flex-start; gap: .65rem; padding: .7rem 1rem; border-bottom: 1px solid #0d1e35; transition: background .15s; }
.task-item:last-child { border-bottom: none; }
.task-item:hover { background: #0c1a30; }
.task-icon { flex-shrink: 0; margin-top: .1rem; width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; }
.task-spinner { width: 14px; height: 14px; border-radius: 50%; border: 2px solid #1e3a5f; border-top-color: #3b82f6; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.task-body { flex: 1; min-width: 0; }
.task-label { font-family: 'Space Mono', monospace; font-size: .72rem; color: #bfdbfe; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: .15rem; }
.task-msg { font-size: .72rem; color: #475569; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.task-msg.msg-error   { color: #f87171; }
.task-msg.msg-done    { color: #4ade80; }
.task-msg.msg-interrupted { color: #facc15; }
.task-elapsed { font-family: 'Space Mono', monospace; font-size: .65rem; color: #334155; flex-shrink: 0; margin-top: .1rem; }
.task-empty { padding: 1.1rem 1rem; text-align: center; font-size: .78rem; color: #334155; font-family: 'Space Mono', monospace; }

/*  Wiki edition pill  */
.wiki-edition-pill {
    display: inline-flex; align-items: center; gap: .35rem;
    background: #0c1a30; border: 1px solid #1e3a5f;
    border-radius: 20px; padding: .25rem .75rem;
    font-family: 'Space Mono', monospace; font-size: .7rem; color: #60a5fa;
}
.wiki-edition-dot { width: 7px; height: 7px; border-radius: 50%; background: #3b82f6; }

/*  SPARQL section  */
.sparql-editor-wrap {
    background: #060d1a; border: 1px solid #1e3a5f; border-radius: 10px;
    overflow: hidden; margin-bottom: 1rem;
}
.sparql-editor-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: .5rem 1rem; background: #0c1a30; border-bottom: 1px solid #1e3a5f;
}
.sparql-editor-label {
    font-family: 'Space Mono', monospace; font-size: .7rem;
    letter-spacing: 2px; text-transform: uppercase; color: #3b82f6;
}
.sparql-endpoint-badge {
    font-family: 'Space Mono', monospace; font-size: .68rem;
    color: #475569; background: #0a0f1e; border: 1px solid #1e3a5f;
    border-radius: 4px; padding: .15rem .5rem;
}

/* result table */
.sparql-table {
    width: 100%; border-collapse: collapse;
    font-size: .82rem; font-family: 'DM Sans', sans-serif;
}
.sparql-table th {
    background: #0c1a30; color: #60a5fa;
    font-family: 'Space Mono', monospace; font-size: .72rem;
    letter-spacing: 1px; text-transform: uppercase;
    padding: .55rem .9rem; text-align: left;
    border-bottom: 2px solid #1e3a5f; white-space: nowrap;
}
.sparql-table td {
    padding: .5rem .9rem; color: #cbd5e1;
    border-bottom: 1px solid #0d1e35; vertical-align: top;
    word-break: break-word; max-width: 420px;
}
.sparql-table tr:last-child td { border-bottom: none; }
.sparql-table tr:hover td { background: #0c1524; }
.sparql-table a { color: #60a5fa; text-decoration: none; }
.sparql-table a:hover { text-decoration: underline; }
.sparql-uri {
    font-family: 'Space Mono', monospace; font-size: .72rem;
    color: #475569; word-break: break-all;
}
.sparql-literal { color: #86efac; }
.sparql-lang { color: #64748b; font-size: .7rem; margin-left: .25rem; }

/* preset query cards */
.preset-grid { display: flex; flex-wrap: wrap; gap: .7rem; margin-bottom: 1.2rem; }
.preset-card {
    flex: 1 1 220px; background: #060d1a; border: 1px solid #1e3a5f;
    border-radius: 8px; padding: .8rem 1rem; cursor: pointer;
    transition: border-color .15s, background .15s;
    text-align: left;
}
.preset-card:hover { background: #0c1a30; border-color: #3b82f6; }
.preset-card-title {
    font-family: 'Space Mono', monospace; font-size: .78rem;
    color: #60a5fa; margin-bottom: .3rem;
}
.preset-card-desc { font-size: .78rem; color: #475569; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="app-header">
  <h1>Wikipedia Graph Explorer</h1>
</div>
""", unsafe_allow_html=True)



_WIKI_EDITIONS = {
    "es":     ("https://es.wikipedia.org/wiki",     "es.wikipedia.org",     "Español (eswiki)"),
    "simple": ("https://simple.wikipedia.org/wiki", "simple.wikipedia.org", "Simple English"),
}

if "wiki_edition" not in st.session_state:
    st.session_state["wiki_edition"] = "es"


def _wiki_base() -> tuple[str, str]:
    """Return (base_url, domain) for the globally selected edition."""
    base, domain, _ = _WIKI_EDITIONS[st.session_state["wiki_edition"]]
    return base, domain


def _wiki_url(title: str) -> str:
    base, _ = _wiki_base()
    return f"{base}/{urllib.parse.quote(title.replace(' ', '_'))}"



_JOB_LABELS = {
    "dl_small":    "Download · simplewiki",
    "dl_full":     "Download · eswiki",
    "parse_small": "Parse · simplewiki",
    "parse_full":  "Parse · eswiki",
    "load_small":  "Load → Neo4j · simplewiki",
    "load_full":   "Load → Neo4j · eswiki",
    "clear_graph": "Clear graph · Neo4j",
}


def _start_job(job_id: str, fn, *args):
    job = job_store.get_job(job_id)
    if job and job["status"] == "running":
        return
    label = _JOB_LABELS.get(job_id, job_id)
    job_store.start_job(job_id, label)

    def _run():
        try:
            fn(*args)
            job_store.finish_job(job_id, "Completed successfully ✓")
        except Exception as exc:
            logger.exception("Job %s failed", job_id)
            job_store.fail_job(job_id, str(exc))

    threading.Thread(target=_run, daemon=True).start()


def _render_job_status(job_id: str):
    job = job_store.get_job(job_id)
    if job is None:
        return
    status = job["status"]
    if status == "running":
        st.markdown(
            f'<div class="job-banner"><div class="job-pulse"></div>'
            f'<span class="job-text">{job["message"]}</span></div>',
            unsafe_allow_html=True,
        )
        time.sleep(1)
        st.rerun()
    elif status == "done":
        st.success(job["message"])
    elif status == "error":
        st.error(job.get("error") or job["message"])
    elif status == "interrupted":
        st.warning("⚠ Interrupted — the process ended before this job finished.")


def _elapsed(job: dict) -> str:
    end   = job.get("ended_at") or time.time()
    start = job.get("started_at") or end
    secs  = int(end - start)
    if secs < 60:
        return f"{secs}s"
    m, s = divmod(secs, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m"


@st.cache_resource(show_spinner=False)
def get_driver():
    try:
        drv = loader.get_driver()
        drv.verify_connectivity()
        return drv, None
    except Exception as e:
        return None, str(e)

driver, neo4j_error = get_driver()


with st.sidebar:

    # GLOBAL Wikipedia edition selector 
    st.markdown("### Wikipedia Edition")
    st.caption("Applies to all article links and the article viewer throughout the app.")

    edition_choice = st.radio(
        "Edición",
        options=list(_WIKI_EDITIONS.keys()),
        format_func=lambda k: _WIKI_EDITIONS[k][2],
        index=list(_WIKI_EDITIONS.keys()).index(st.session_state["wiki_edition"]),
        horizontal=True,
        key="wiki_edition_radio",
        label_visibility="collapsed",
    )
    if edition_choice != st.session_state["wiki_edition"]:
        st.session_state["wiki_edition"] = edition_choice
        # Reset article viewer so it reloads with the new URL
        st.session_state["viewer_page"] = None
        st.session_state["viewer_next"] = None
        st.rerun()

    active_base, active_domain, active_label = _WIKI_EDITIONS[st.session_state["wiki_edition"]]
    st.markdown(
        f'<div class="wiki-edition-pill">'
        f'<span class="wiki-edition-dot"></span>{active_domain}</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    # Neo4j connection 
    st.markdown("### Neo4j Connection")
    if neo4j_error:
        st.markdown('<span class="chip-err">✗ Disconnected</span>', unsafe_allow_html=True)
        st.caption(neo4j_error)
        st.info("Start Neo4j and refresh the page.")
    else:
        st.markdown('<span class="chip-ok">✓ Connected</span>', unsafe_allow_html=True)
        st.caption(config.NEO4J_URI)
        st.divider()
        st.markdown("### Graph Stats")
        if st.button("Refresh stats", use_container_width=True):
            st.cache_data.clear()

        @st.cache_data(ttl=30, show_spinner=False)
        def _stats():
            return queries.graph_stats(driver)
        s = _stats()
        c1, c2 = st.columns(2)
        c1.metric("Pages", f"{s['pages']:,}")
        c2.metric("Links", f"{s['relationships']:,}")

    st.divider()

    # Task panel 
    all_jobs  = job_store.get_all()
    running   = [j for j in all_jobs if j["status"] == "running"]
    n_running = len(running)

    badge_cls  = "badge-running" if n_running else ""
    badge_text = f"{n_running} running" if n_running else (f"{len(all_jobs)} jobs" if all_jobs else "idle")

    st.markdown(
        f'<div class="task-panel-header" style="border-radius:10px 10px 0 0;">'
        f'  <span class="task-panel-title">Tasks</span>'
        f'  <span class="task-panel-badge {badge_cls}">{badge_text}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if not all_jobs:
        st.markdown(
            '<div class="task-panel"><div class="task-empty">No tasks yet</div></div>',
            unsafe_allow_html=True,
        )
    else:
        items_html = ""
        for job in all_jobs:
            status = job["status"]
            if status == "running":
                icon_html = '<div class="task-spinner"></div>'
            elif status == "done":
                icon_html = '<span style="color:#4ade80;font-size:.9rem;">✓</span>'
            elif status == "error":
                icon_html = '<span style="color:#f87171;font-size:.9rem;">✗</span>'
            else:
                icon_html = '<span style="color:#facc15;font-size:.9rem;">⚠</span>'

            msg_cls = {"running":"","done":"msg-done","error":"msg-error","interrupted":"msg-interrupted"}.get(status, "")
            elapsed = _elapsed(job)
            items_html += f"""
<div class="task-item">
  <div class="task-icon">{icon_html}</div>
  <div class="task-body">
    <div class="task-label">{job['label']}</div>
    <div class="task-msg {msg_cls}">{job['message']}</div>
  </div>
  <div class="task-elapsed">{elapsed}</div>
</div>"""
        st.markdown(f'<div class="task-panel">{items_html}</div>', unsafe_allow_html=True)

    finished = [j for j in all_jobs if j["status"] in ("done", "error", "interrupted")]
    if finished:
        if st.button("Clear finished tasks", use_container_width=True):
            job_store.clear_finished()
            st.rerun()

    if n_running:
        time.sleep(1)
        st.rerun()

    st.divider()

    # Local files 
    st.markdown("### Local Files")
    for label, path in [
        ("simplewiki dump", config.SMALL_DUMP_FILE),
        ("eswiki dump",     config.FULL_DUMP_FILE),
        ("simplewiki CSV",  config.SMALL_LINKS_CSV),
        ("eswiki CSV",      config.FULL_LINKS_CSV),
    ]:
        exists = path.exists()
        icon = "✓" if exists else "✗"
        cls  = "chip-ok" if exists else "chip-warn"
        size = f" ({path.stat().st_size // 1_048_576} MB)" if exists else ""
        st.markdown(f'<span class="{cls}">{icon}</span> `{label}`{size}', unsafe_allow_html=True)


# SECTION 1 — Data Management
st.markdown('<div class="section-title">1 Data Management</div>', unsafe_allow_html=True)
tab_dl, tab_parse, tab_load = st.tabs(["Download", "Parse", "Load into Neo4j"])

with tab_dl:
    col_small, col_full = st.columns(2)

    with col_small:
        st.markdown("#### Simple English Wikipedia")
        st.caption("~250 MB compressed · Fast · Good for testing")

        def _do_dl_small():
            def _cb(done, total):
                msg = f"Downloading… {done // 1_048_576} MB"
                if total > 0:
                    msg += f" / {total // 1_048_576} MB"
                job_store.update_job("dl_small", msg)
            downloader.download_small(_cb)

        dl_small_job = job_store.get_job("dl_small")
        btn_disabled = bool(dl_small_job and dl_small_job["status"] == "running")
        if st.button("Download small dataset", use_container_width=True, disabled=btn_disabled):
            _start_job("dl_small", _do_dl_small)
            st.rerun()
        _render_job_status("dl_small")

    with col_full:
        st.markdown("#### Spanish Wikipedia (eswiki)")
        st.caption("~1.6 GB compressed · Complete dataset")
        st.warning("Large file — may take a while to download.")

        def _do_dl_full():
            def _cb(done, total):
                msg = f"Downloading… {done // 1_048_576} MB"
                if total > 0:
                    msg += f" / {total // 1_048_576} MB"
                job_store.update_job("dl_full", msg)
            downloader.download_full(_cb)

        dl_full_job = job_store.get_job("dl_full")
        btn_disabled = bool(dl_full_job and dl_full_job["status"] == "running")
        if st.button("Download full dataset", use_container_width=True, disabled=btn_disabled):
            _start_job("dl_full", _do_dl_full)
            st.rerun()
        _render_job_status("dl_full")

with tab_parse:
    col_ps, col_pf = st.columns(2)

    with col_ps:
        st.markdown("#### Parse small dump")
        st.caption(f"Output → `{config.SMALL_LINKS_CSV}`")

        def _do_parse_small():
            if not config.SMALL_DUMP_FILE.exists():
                raise FileNotFoundError("Download the small dump first.")
            def _cb(n):
                job_store.update_job("parse_small", f"Parsing… {n:,} pages processed")
            parser.parse_small(_cb)

        ps_job = job_store.get_job("parse_small")
        btn_disabled = bool(ps_job and ps_job["status"] == "running")
        if st.button("Parse small dataset", use_container_width=True, key="ps_btn", disabled=btn_disabled):
            _start_job("parse_small", _do_parse_small)
            st.rerun()
        _render_job_status("parse_small")

    with col_pf:
        st.markdown("#### Parse full dump")
        st.caption(f"Output → `{config.FULL_LINKS_CSV}`")
        st.warning("⚠ The full Spanish dump takes several hours to parse.")

        def _do_parse_full():
            if not config.FULL_DUMP_FILE.exists():
                raise FileNotFoundError("Download the full dump first.")
            def _cb(n):
                job_store.update_job("parse_full", f"Parsing… {n:,} pages processed")
            parser.parse_full(_cb)

        pf_job = job_store.get_job("parse_full")
        btn_disabled = bool(pf_job and pf_job["status"] == "running")
        if st.button("Parse full dataset", use_container_width=True, key="pf_btn", disabled=btn_disabled):
            _start_job("parse_full", _do_parse_full)
            st.rerun()
        _render_job_status("parse_full")

with tab_load:
    if neo4j_error:
        st.error("Neo4j is not connected.")
    else:
        col_ls, col_lf = st.columns(2)

        with col_ls:
            st.markdown("#### Load small dataset")

            def _do_load_small():
                if not config.SMALL_LINKS_CSV.exists():
                    raise FileNotFoundError("Parse the small dump first.")
                def _cb(n):
                    job_store.update_job("load_small", f"Loading… {n:,} relationships")
                loader.load_small(driver, _cb)

            ls_job = job_store.get_job("load_small")
            btn_disabled = bool(ls_job and ls_job["status"] == "running")
            if st.button("Load small into Neo4j", use_container_width=True, disabled=btn_disabled):
                _start_job("load_small", _do_load_small)
                st.rerun()
            _render_job_status("load_small")

        with col_lf:
            st.markdown("#### Load full dataset")
            st.warning("May take a while to load.")

            def _do_load_full():
                if not config.FULL_LINKS_CSV.exists():
                    raise FileNotFoundError("Parse the full dump first.")
                def _cb(n):
                    job_store.update_job("load_full", f"Loading… {n:,} relationships")
                loader.load_full(driver, _cb)

            lf_job = job_store.get_job("load_full")
            btn_disabled = bool(lf_job and lf_job["status"] == "running")
            if st.button("Load full into Neo4j", use_container_width=True, disabled=btn_disabled):
                _start_job("load_full", _do_load_full)
                st.rerun()
            _render_job_status("load_full")

        st.divider()
        with st.expander("Danger zone — Clear graph"):
            st.warning("This will DELETE ALL NODES AND RELATIONSHIPS in Neo4j.")

            if not st.session_state.get("clear_confirm"):
                if st.button("Clear entire graph", type="primary"):
                    st.session_state["clear_confirm"] = True
                    st.rerun()
            else:
                st.error("Are you sure? This cannot be undone.")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    clear_job = job_store.get_job("clear_graph")
                    btn_disabled = bool(clear_job and clear_job["status"] == "running")
                    if st.button("Yes, delete everything", type="primary",
                                 use_container_width=True, disabled=btn_disabled):
                        def _do_clear():
                            total_rels = 0
                            total_nodes = 0
                            batch = config.NEO4J_BATCH_SIZE
                            with driver.session() as session:
                                while True:
                                    res = session.run(
                                        "MATCH ()-[r]->() WITH r LIMIT $b DELETE r RETURN count(r) AS d",
                                        b=batch,
                                    )
                                    deleted = res.single()["d"]
                                    total_rels += deleted
                                    if deleted == 0:
                                        break
                                    job_store.update_job("clear_graph", f"Deleting relationships\u2026 {total_rels:,} removed")
                                while True:
                                    res = session.run(
                                        "MATCH (n) WITH n LIMIT $b DETACH DELETE n RETURN count(n) AS d",
                                        b=batch,
                                    )
                                    deleted = res.single()["d"]
                                    total_nodes += deleted
                                    if deleted == 0:
                                        break
                                    job_store.update_job("clear_graph", f"Deleting nodes\u2026 {total_nodes:,} removed ({total_rels:,} rels gone)")
                            st.cache_data.clear()

                        st.session_state["clear_confirm"] = False
                        _start_job("clear_graph", _do_clear)
                        st.rerun()
                with col_no:
                    if st.button("Cancel", use_container_width=True):
                        st.session_state["clear_confirm"] = False
                        st.rerun()

            _render_job_status("clear_graph")


# SECTION 2 — Graph Exploration
st.markdown("")
st.markdown('<div class="section-title">2 Graph Exploration</div>', unsafe_allow_html=True)

if neo4j_error:
    st.info("Connect Neo4j to enable graph exploration.")
else:
    exp_path, exp_nbhd, exp_iso, exp_cc, exp_stats = st.tabs(
        ["Shortest Path", "Neighborhood Graph", "Isolated Pages", "Connected Components", "Top Pages Stats"]
    )

    # Shortest path 
    with exp_path:
        st.markdown("#### Find shortest path between two pages")
        st.caption(
            f"Directed BFS · max {config.SHORTEST_PATH_MAX_DEPTH} hops · "
            "Click a node button below to open its Wikipedia article in the viewer."
        )

        # Edition badge — reads the global state, no local override needed
        st.markdown(
            f'<div class="wiki-edition-pill" style="margin-bottom:.6rem;">'
            f'<span class="wiki-edition-dot"></span>'
            f'Viewer: <strong>{active_label}</strong> &nbsp;·&nbsp; '
            f'change in sidebar</div>',
            unsafe_allow_html=True,
        )

        col_a, col_b = st.columns(2)
        with col_a:
            page_a = st.text_input("Page A (source)",      placeholder="e.g. Madrid")
        with col_b:
            page_b = st.text_input("Page B (destination)", placeholder="e.g. Barcelona")

        if st.button("Compute shortest path", use_container_width=True):
            if not page_a.strip() or not page_b.strip():
                st.warning("Enter both page titles.")
            else:
                with st.spinner("Computing…"):
                    result = queries.shortest_path(driver, page_a.strip(), page_b.strip())
                st.session_state["path_result"] = result
                st.session_state["viewer_page"] = None
                st.session_state["viewer_next"] = None

        res = st.session_state.get("path_result")
        if res is not None:
            if not res["found"]:
                st.error(res["error"] or "No path found.")
            else:
                path_nodes = res["path"]
                st.success(f"Path found - {res['hops']} {'hop' if res['hops'] == 1 else 'hops'}")
                next_in_path = {
                    path_nodes[i]: path_nodes[i + 1]
                    for i in range(len(path_nodes) - 1)
                }
                parts = []
                for i, title in enumerate(path_nodes):
                    if i == 0:
                        cls = "path-node node-src"
                    elif i == len(path_nodes) - 1:
                        cls = "path-node node-dst"
                    else:
                        cls = "path-node"
                    parts.append(f'<span class="{cls}">{title}</span>')
                    if i < len(path_nodes) - 1:
                        parts.append('<span class="path-arrow">→</span>')
                st.markdown(
                    f'<div class="path-chain">{"".join(parts)}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("")
                st.markdown("**Open article in viewer** - click a node:")
                btn_cols = st.columns(min(len(path_nodes), 5))
                for i, title in enumerate(path_nodes):
                    emoji = "🟢" if i == 0 else ("🔴" if i == len(path_nodes) - 1 else "🔵")
                    if btn_cols[i % 5].button(
                        f"{emoji} {title}", key=f"vbtn_{i}", use_container_width=True
                    ):
                        st.session_state["viewer_page"] = title
                        st.session_state["viewer_next"] = next_in_path.get(title)

        viewer_title = st.session_state.get("viewer_page")
        viewer_next  = st.session_state.get("viewer_next")
        if viewer_title:
            st.markdown("---")
            st.markdown("#### Wikipedia Article Viewer")
            article_url = _wiki_url(viewer_title)     # uses global edition

            if viewer_next:
                encoded_next = urllib.parse.quote(viewer_next.replace(" ", "_"))
                highlight_js = f"""
<script>
(function() {{
    var frame   = document.getElementById('wikiframe');
    var note    = document.getElementById('hl-note');
    var nextTitle = "{viewer_next.replace('"', '\\"')}";
    var nextSlug  = "{encoded_next}";
    frame.addEventListener('load', function() {{
        try {{
            var doc = frame.contentDocument || frame.contentWindow.document;
            var style = doc.createElement('style');
            style.id  = 'wge-highlight';
            style.textContent =
                'a[title="' + nextTitle + '"],' +
                'a[href*="/' + nextSlug + '"]' +
                '{{background:#fbbf24!important;color:#000!important;border-radius:3px;' +
                'padding:0 3px;outline:2px solid #f59e0b;font-weight:700;}}';
            doc.head.appendChild(style);
            var targets = doc.querySelectorAll(
                'a[title="' + nextTitle + '"], a[href*="/' + nextSlug + '"]'
            );
            if (targets.length) targets[0].scrollIntoView({{behavior:'smooth',block:'center'}});
            if (note) note.style.display = 'none';
        }} catch(e) {{
            if (note) note.style.display = 'flex';
        }}
    }});
}})();
</script>
"""
                search_url = (
                    f"https://en.wikipedia.org/w/index.php"
                    f"?title={urllib.parse.quote(viewer_title.replace(' ','_'))}"
                    f"&action=view#:~:text={urllib.parse.quote(viewer_next)}"
                )
                fallback_banner = f"""
<div id="hl-note" style="display:none;align-items:center;gap:.7rem;
    background:#78350f;border:1px solid #f59e0b;border-radius:6px;
    padding:.65rem 1.1rem;margin-bottom:.5rem;font-size:.84rem;color:#fde68a;">
  <span>Wikipedia blocks style injection from cross-origin frames.
    Look for <strong style="color:#fbbf24;font-family:'Space Mono',monospace">{viewer_next}</strong>
    (<kbd style="background:#92400e;padding:1px 5px;border-radius:3px">Ctrl+F</kbd>), or
    <a href="{search_url}" target="_blank" style="color:#fbbf24;text-decoration:underline">open full article ↗</a>.
  </span>
</div>
"""
            else:
                highlight_js    = ""
                fallback_banner = ""

            if viewer_next:
                next_info = f"""
<div style="background:#1e3a5f;border:1px solid #3b82f6;border-top:none;
    padding:.55rem 1rem;font-size:.84rem;color:#bfdbfe;
    display:flex;align-items:center;gap:.5rem;">
  <span>Next hop in path →
    <strong style="color:#fbbf24;font-family:'Space Mono',monospace">{viewer_next}</strong>
  </span>
</div>"""
            else:
                next_info = """
<div style="background:#14532d;border:1px solid #16a34a;border-top:none;
    padding:.55rem 1rem;font-size:.84rem;color:#86efac;
    display:flex;align-items:center;gap:.5rem;">
  <span>This is the <strong>final destination</strong> in the path.</span>
</div>"""

            viewer_header = f"""
<div class="wiki-viewer-bar">
  <span class="wiki-viewer-title">{viewer_title}</span>
  <span style="font-family:'Space Mono',monospace;font-size:.7rem;color:#475569;
               padding:0 .4rem;white-space:nowrap;">{active_label}</span>
  <a href="{article_url}" target="_blank"
     style="color:#60a5fa;font-size:.75rem;font-family:'Space Mono',monospace;
            text-decoration:none;white-space:nowrap;">↗ {active_domain}</a>
</div>"""
            iframe_html = (
                '<div class="wiki-iframe-wrap">'
                f'<iframe id="wikiframe" src="{article_url}?useskin=vector"'
                ' width="100%" height="660" style="border:none;display:block;"'
                ' sandbox="allow-scripts allow-same-origin allow-popups allow-forms"'
                ' loading="lazy"></iframe>'
                '</div>'
            )
            st.markdown(
                highlight_js + viewer_header + next_info + fallback_banner + iframe_html,
                unsafe_allow_html=True,
            )

    # Neighborhood Graph — D3 
    with exp_nbhd:
        st.markdown("#### Neighborhood graph — directed reachability")
        st.caption(
            "Follows outgoing LINKS_TO edges only (→). "
            "Node colour encodes hop distance from the origin. "
            "Click any node to open its Wikipedia article. "
            "Use hops carefully on very large graphs — more nodes = slower layout."
        )

        # Edition badge
        st.markdown(
            f'<div class="wiki-edition-pill" style="margin-bottom:.6rem;">'
            f'<span class="wiki-edition-dot"></span>'
            f'Node links → <strong>{active_label}</strong></div>',
            unsafe_allow_html=True,
        )

        nbhd_col1, nbhd_col2 = st.columns([3, 1])
        with nbhd_col1:
            nbhd_origin = st.text_input("Origin page", placeholder="e.g. Madrid", key="nbhd_origin")
        with nbhd_col2:
            nbhd_depth = st.number_input("Max hops", min_value=1, max_value=6, value=2, step=1, key="nbhd_depth")

        if st.button("Build neighborhood graph", use_container_width=True, key="nbhd_btn"):
            if not nbhd_origin.strip():
                st.warning("Enter an origin page title.")
            else:
                with st.spinner("Querying Neo4j…"):
                    nbhd_result = queries.neighborhood_graph(driver, nbhd_origin.strip(), int(nbhd_depth))
                st.session_state["nbhd_result"] = nbhd_result

        nbhd_res = st.session_state.get("nbhd_result")
        if nbhd_res is not None:
            if not nbhd_res["found"]:
                st.error(nbhd_res["error"] or "Could not build neighborhood graph.")
            else:
                nodes  = nbhd_res["nodes"]
                edges  = nbhd_res["edges"]
                origin = nbhd_res["origin"]
                st.success(f"{len(nodes)} pages · {len(edges)} links · origin: **{origin}**")
                if len(nodes) >= 300:
                    st.warning("Node cap reached (300). Increase hops or choose a less connected page.")

                # Use global edition for node click URLs
                wiki_base, _ = _wiki_base()

                import json
                depth_colors = ["#3b82f6","#10b981","#f59e0b","#ef4444","#a78bfa","#ec4899","#14b8a6"]

                d3_nodes = []
                for nd in nodes:
                    nid    = nd["id"]
                    depth  = nd["depth"]
                    col    = depth_colors[min(depth, len(depth_colors) - 1)]
                    radius = 18 if nid == origin else (12 if depth == 1 else 7)
                    url    = f"{wiki_base}/{urllib.parse.quote(nid.replace(' ', '_'))}"
                    d3_nodes.append({
                        "id": nid, "depth": depth, "color": col,
                        "radius": radius, "url": url,
                        "label": nid if depth <= 1 else "",
                    })

                d3_links    = [{"source": e["source"], "target": e["target"]} for e in edges]
                nodes_json  = json.dumps(d3_nodes)
                links_json  = json.dumps(d3_links)
                origin_json = json.dumps(origin)

                d3_html = f"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:#0c1524; font-family:'Space Mono',monospace; overflow:hidden; width:100%; height:640px; }}
#graph-container {{ width:100%; height:100%; position:relative; }}
svg {{ width:100%; height:100%; cursor:grab; }}
svg:active {{ cursor:grabbing; }}
#tooltip {{ position:absolute; background:#0f172a; border:1px solid #3b82f6; border-radius:6px; padding:6px 10px; font-size:11px; color:#bfdbfe; pointer-events:none; opacity:0; transition:opacity .15s; max-width:220px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; z-index:10; }}
#legend {{ position:absolute; top:10px; left:10px; background:rgba(12,21,36,.85); border:1px solid #1e3a5f; border-radius:8px; padding:10px 14px; font-size:11px; color:#94a3b8; backdrop-filter:blur(4px); }}
.legend-row {{ display:flex; align-items:center; gap:7px; margin-bottom:5px; }}
.legend-dot {{ width:10px; height:10px; border-radius:50%; flex-shrink:0; }}
#controls {{ position:absolute; bottom:10px; right:10px; display:flex; gap:6px; }}
.ctrl-btn {{ background:#1e3a5f; border:1px solid #3b82f6; color:#60a5fa; border-radius:5px; padding:5px 10px; font-size:12px; cursor:pointer; font-family:'Space Mono',monospace; transition:background .15s; }}
.ctrl-btn:hover {{ background:#2d4f7c; }}
.link {{ stroke-opacity:0.45; }}
.node {{ cursor:pointer; }}
.node-label {{ font-size:9px; fill:#e2e8f0; pointer-events:none; font-family:'Space Mono',monospace; text-shadow:0 1px 3px #0c1524; }}
</style></head><body>
<div id="graph-container">
  <svg id="svg"></svg>
  <div id="tooltip"></div>
  <div id="legend"></div>
  <div id="controls">
    <button class="ctrl-btn" onclick="resetZoom()">⊙ Reset</button>
    <button class="ctrl-btn" onclick="toggleLabels()">Aa Labels</button>
    <button class="ctrl-btn" onclick="togglePhysics()">⏸ Physics</button>
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>
const NODES={nodes_json},LINKS={links_json},ORIGIN={origin_json};
const DEPTH_COLORS=["#3b82f6","#10b981","#f59e0b","#ef4444","#a78bfa","#ec4899","#14b8a6"];
const maxDepth=Math.max(...NODES.map(n=>n.depth));
const legendEl=document.getElementById('legend');
legendEl.innerHTML=DEPTH_COLORS.slice(0,maxDepth+1).map((c,i)=>`<div class="legend-row"><div class="legend-dot" style="background:${{c}}"></div><span>${{i===0?'Origin':'Hop '+i}}</span></div>`).join('')+`<div style="margin-top:6px;border-top:1px solid #1e3a5f;padding-top:6px;color:#475569;font-size:10px;">Scroll to zoom · Drag to pan<br>Click node → Wikipedia</div>`;
const container=document.getElementById('graph-container');
const W=container.clientWidth||900,H=container.clientHeight||640;
const svg=d3.select('#svg').attr('viewBox',[0,0,W,H]);
const g=svg.append('g');
const defs=svg.append('defs');
DEPTH_COLORS.slice(0,maxDepth+1).forEach((col,i)=>{{defs.append('marker').attr('id',`arrow-${{i}}`).attr('viewBox','0 -4 8 8').attr('refX',18).attr('refY',0).attr('markerWidth',6).attr('markerHeight',6).attr('orient','auto').append('path').attr('d','M0,-4L8,0L0,4').attr('fill',col).attr('opacity',0.7);}});
const nodeMap=Object.fromEntries(NODES.map(n=>[n.id,n]));
const simulation=d3.forceSimulation(NODES).force('link',d3.forceLink(LINKS).id(d=>d.id).distance(d=>{{const s=nodeMap[d.source?.id??d.source],t=nodeMap[d.target?.id??d.target];return 120+((s?.depth??1)+(t?.depth??1))/2*60;}}).strength(0.15)).force('charge',d3.forceManyBody().strength(d=>d.id===ORIGIN?-2000:-400).distanceMax(900)).force('center',d3.forceCenter(W/2,H/2).strength(0.04)).force('collision',d3.forceCollide().radius(d=>d.radius+18).strength(0.9)).force('radial',d3.forceRadial(d=>d.depth*220,W/2,H/2).strength(d=>d.id===ORIGIN?0:0.35));
const link=g.append('g').selectAll('line').data(LINKS).join('line').attr('class','link').attr('stroke',d=>{{const s=nodeMap[d.source?.id??d.source];return DEPTH_COLORS[Math.min(s?.depth??0,DEPTH_COLORS.length-1)];}}).attr('stroke-width',1.2).attr('marker-end',d=>{{const s=nodeMap[d.source?.id??d.source];return `url(#arrow-${{Math.min(s?.depth??0,maxDepth)}})`;}} );
const nodeG=g.append('g').selectAll('g').data(NODES).join('g').attr('class','node-group').call(d3.drag().on('start',dragStart).on('drag',dragged).on('end',dragEnd)).on('click',(e,d)=>{{e.stopPropagation();window.open(d.url,'_blank');}});
nodeG.append('circle').attr('class','node').attr('r',d=>d.radius).attr('fill',d=>d.color).attr('fill-opacity',d=>d.id===ORIGIN?1:0.8).attr('stroke',d=>d.id===ORIGIN?'#ffffff':'#0c1524').attr('stroke-width',d=>d.id===ORIGIN?2.5:1);
nodeG.filter(d=>d.id===ORIGIN).append('circle').attr('r',d=>d.radius+4).attr('fill','none').attr('stroke','#3b82f6').attr('stroke-width',1.5).attr('stroke-opacity',0.5).attr('stroke-dasharray','4 3');
let labelsVisible=true;
const labels=nodeG.append('text').attr('class','node-label').attr('dy',d=>d.radius+11).attr('text-anchor','middle').text(d=>d.label);
const tooltip=document.getElementById('tooltip');
nodeG.on('mouseenter',(e,d)=>{{tooltip.textContent=d.id+(d.depth===0?' (origin)':` (hop ${{d.depth}})`);tooltip.style.opacity='1';}}).on('mousemove',e=>{{const r=container.getBoundingClientRect();tooltip.style.left=(e.clientX-r.left+12)+'px';tooltip.style.top=(e.clientY-r.top-10)+'px';}}).on('mouseleave',()=>{{tooltip.style.opacity='0';}});
simulation.on('tick',()=>{{link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);nodeG.attr('transform',d=>`translate(${{d.x}},${{d.y}})`)}});
const zoom=d3.zoom().scaleExtent([0.1,8]).on('zoom',e=>g.attr('transform',e.transform));
svg.call(zoom);
function resetZoom(){{svg.transition().duration(500).call(zoom.transform,d3.zoomIdentity.translate(W/2,H/2).scale(1).translate(-W/2,-H/2));}}
function toggleLabels(){{labelsVisible=!labelsVisible;labels.attr('display',labelsVisible?null:'none');}}
let physicsOn=true;
function togglePhysics(){{physicsOn=!physicsOn;physicsOn?simulation.alpha(0.3).restart():simulation.stop();document.querySelector('.ctrl-btn:last-child').textContent=physicsOn?'⏸ Physics':'▶ Physics';}}
function dragStart(e,d){{if(!e.active)simulation.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;}}
function dragged(e,d){{d.fx=e.x;d.fy=e.y;}}
function dragEnd(e,d){{if(!e.active)simulation.alphaTarget(0);d.fx=null;d.fy=null;}}
</script></body></html>"""
                st_components.html(d3_html, height=650, scrolling=False)
                st.caption("Drag nodes · scroll to zoom · click a node to open its Wikipedia article")

    # Isolated pages 
    with exp_iso:
        st.markdown("#### Find pages with missing links")
        limit = st.slider("Maximum results to show", 10, 500, config.ISOLATED_PAGES_LIMIT, 10)

        if st.button("Run all queries", use_container_width=True, key="iso_btn"):
            with st.spinner("Querying…"):
                st.session_state["iso_result"] = queries.find_isolated_pages(driver, limit)
                st.session_state["iso_no_in"]  = queries.find_no_incoming(driver, limit)
                st.session_state["iso_no_out"] = queries.find_no_outgoing(driver, limit)

        def _tag_list(pages: list[str]) -> None:
            if not pages:
                st.info("None found.")
                return
            # Uses global _wiki_url — respects selected edition
            tag_html = "".join(
                f'<a class="tag" href="{_wiki_url(p)}" target="_blank">{p}</a>'
                for p in pages
            )
            st.markdown(f'<div class="tag-list">{tag_html}</div>', unsafe_allow_html=True)

        iso_tab1, iso_tab2, iso_tab3 = st.tabs(
            ["🔴 Fully isolated (degree = 0)", "⬅️ No incoming links", "➡️ No outgoing links"]
        )

        with iso_tab1:
            st.caption("Pages with **no incoming and no outgoing** links at all.")
            res = st.session_state.get("iso_result")
            if res:
                st.metric("Total fully isolated", f"{res['total']:,}")
                st.caption(f"Showing first {len(res['pages'])}")
                _tag_list(res["pages"])

        with iso_tab2:
            st.caption("Pages that **no other page links to** (in-degree = 0), but may have outgoing links.")
            res = st.session_state.get("iso_no_in")
            if res:
                st.metric("Total with no incoming links", f"{res['total']:,}")
                st.caption(f"Showing first {len(res['pages'])}")
                _tag_list(res["pages"])

        with iso_tab3:
            st.caption("Pages that **link to no other page** (out-degree = 0), but may have incoming links.")
            res = st.session_state.get("iso_no_out")
            if res:
                st.metric("Total with no outgoing links", f"{res['total']:,}")
                st.caption(f"Showing first {len(res['pages'])}")
                _tag_list(res["pages"])

    # Connected components 
    with exp_cc:
        st.markdown("#### Weakly connected components")
        st.caption(
            "Two pages belong to the same component if any undirected path connects them. "
        )
        if st.button("Compute components", use_container_width=True):
            with st.spinner("Computing (may be slow on large graphs)…"):
                st.session_state["cc_result"] = queries.connected_components(driver)

        cc_res = st.session_state.get("cc_result")
        if cc_res:
            count   = cc_res.get("component_count")
            largest = cc_res.get("largest_component_size")
            count_s   = f"{count:,}"   if isinstance(count,   int) else "?"
            largest_s = f"{largest:,}" if isinstance(largest, int) else "?"
            st.markdown(
                f"""<div class="stat-row">
                  <div class="stat-tile"><div class="stat-value">{count_s}</div><div class="stat-label">Components</div></div>
                  <div class="stat-tile"><div class="stat-value">{largest_s}</div><div class="stat-label">Largest component</div></div>
                  <div class="stat-tile"><div class="stat-value">{cc_res['total_pages']:,}</div><div class="stat-label">Total pages</div></div>
                  <div class="stat-tile"><div class="stat-value">{cc_res['total_relationships']:,}</div><div class="stat-label">Total links</div></div>
                </div>""",
                unsafe_allow_html=True,
            )
            method = cc_res.get("method", "unknown")
            if any(w in method.lower() for w in ("approx", "lower bound", "cypher")):
                st.warning(f"⚠ {method}")
            else:
                st.caption(f"Method: {method}")

    # Top Pages Stats 
    with exp_stats:
        st.markdown("#### Top Pages by Link Activity")
        st.caption(
            "Ranked by in-degree (pages most linked to), out-degree (pages that link the most), "
            "or combined total degree. Click any page name to open it in Wikipedia."
        )

        top_n = st.slider("Top N pages", min_value=5, max_value=50, value=20, step=5, key="stats_top_n")

        if st.button("Compute stats", use_container_width=True, key="stats_btn"):
            with st.spinner("Querying Neo4j…"):
                try:
                    in_data  = queries.top_pages_by_indegree(driver, top_n)
                    out_data = queries.top_pages_by_outdegree(driver, top_n)
                    tot_data = queries.top_pages_by_total_degree(driver, top_n)
                    st.session_state["stats_result"] = {
                        "in": in_data, "out": out_data, "tot": tot_data,
                    }
                except Exception as ex:
                    st.error(f"Query failed: {ex}")

        stats_res = st.session_state.get("stats_result")
        if stats_res:
            def _bar_chart_html(rows: list[dict], value_key: str, color: str, label: str) -> str:
                if not rows:
                    return "<p style='color:#64748b;font-size:.85rem;'>No data.</p>"
                max_val = max(r[value_key] for r in rows) or 1
                # Uses global _wiki_url — respects selected edition
                bars = ""
                for i, row in enumerate(rows):
                    title = row["title"]
                    val   = row[value_key]
                    pct   = val / max_val * 100
                    url   = _wiki_url(title)
                    bars += f"""
<div class="stats-bar-row">
  <span class="stats-bar-rank">#{i+1}</span>
  <a class="stats-bar-label" href="{url}" target="_blank" title="{title}"
     style="color:#cbd5e1;text-decoration:none;">{title}</a>
  <div class="stats-bar-track"><div class="stats-bar-fill"
     style="width:{pct:.1f}%;background:{color};animation:growBar .6s ease {i*0.04:.2f}s both;"></div></div>
  <span class="stats-bar-value">{val:,}</span>
</div>"""
                return (
                    f"<style>@keyframes growBar{{from{{width:0}}}}</style>"
                    f'<div style="margin-bottom:.5rem;"><span style="font-family:\'Space Mono\',monospace;'
                    f'font-size:.7rem;letter-spacing:2px;text-transform:uppercase;color:{color};">'
                    f"{label}</span></div>{bars}"
                )

            tab_in, tab_out, tab_tot = st.tabs(
                ["⬅️ Most Linked-To (In-degree)", "➡️ Most Links Out (Out-degree)", "⬆️ Highest Total Degree"]
            )
            with tab_in:
                st.markdown("Pages that **receive** the most incoming links — the most referenced articles.")
                st.markdown(_bar_chart_html(stats_res["in"], "in_degree", "#3b82f6", "Incoming Links"), unsafe_allow_html=True)
            with tab_out:
                st.markdown("Pages that **send** the most outgoing links — the most prolific linkers.")
                st.markdown(_bar_chart_html(stats_res["out"], "out_degree", "#10b981", "Outgoing Links"), unsafe_allow_html=True)
            with tab_tot:
                st.markdown("Pages with the **highest total connectivity** — in + out combined.")
                st.markdown(_bar_chart_html(stats_res["tot"], "total_degree", "#f59e0b", "Total Links"), unsafe_allow_html=True)

            st.markdown("")
            st.markdown("##### Summary")
            def _safe_first(lst): return lst[0]["title"] if lst else "—"
            def _safe_first_val(lst, key): return f"{lst[0][key]:,}" if lst else "—"
            k1, k2, k3 = st.columns(3)
            k1.metric("Most linked-to page",     _safe_first(stats_res["in"]),  _safe_first_val(stats_res["in"],  "in_degree")    + " inbound links")
            k2.metric("Most outbound-link page", _safe_first(stats_res["out"]), _safe_first_val(stats_res["out"], "out_degree")   + " outbound links")
            k3.metric("Highest total degree",    _safe_first(stats_res["tot"]), _safe_first_val(stats_res["tot"], "total_degree") + " total links")


# SECTION 3 — DBpedia SPARQL Explorer
import requests as _requests
import pandas as _pd

st.markdown("")
st.markdown('<div class="section-title">3 DBpedia SPARQL Explorer</div>', unsafe_allow_html=True)

_SPARQL_ENDPOINT = "https://dbpedia.org/sparql"
_SPARQL_TIMEOUT  = 30  # seconds

# Preset queries 
_PRESETS: list[dict] = [
    {
        "title": "Cities by population",
        "desc":  "Spanish cities ranked by population",
        "query": """\
PREFIX dbo:  <http://dbpedia.org/ontology/>
PREFIX dbp:  <http://dbpedia.org/property/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?city ?label ?population
WHERE {
  ?city a dbo:City ;
        dbo:country <http://dbpedia.org/resource/Spain> ;
        rdfs:label  ?label ;
        dbo:populationTotal ?population .
  FILTER (lang(?label) = "es")
}
ORDER BY DESC(?population)
LIMIT 20""",
    },
    {
        "title": "Places near a point",
        "desc":  "Resources within ~20 km of Madrid centre",
        "query": """\
PREFIX geo:  <http://www.w3.org/2003/01/geo/wgs84_pos#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dbo:  <http://dbpedia.org/ontology/>

SELECT ?place ?label ?lat ?lon
WHERE {
  ?place geo:lat  ?lat ;
         geo:long ?lon .
  OPTIONAL { ?place rdfs:label ?label FILTER (lang(?label) = "es") }
  FILTER (
    ?lat  > 40.30 && ?lat  < 40.55 &&
    ?lon  > -3.85 && ?lon  < -3.55
  )
}
LIMIT 40""",
    },
    {
        "title": "Notable people",
        "desc":  "People born in a given place",
        "query": """\
PREFIX dbo:  <http://dbpedia.org/ontology/>
PREFIX dbr:  <http://dbpedia.org/resource/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?person ?name ?birthDate
WHERE {
  ?person a dbo:Person ;
          dbo:birthPlace dbr:Madrid ;
          rdfs:label     ?name .
  FILTER (lang(?name) = "es")
  OPTIONAL { ?person dbo:birthDate ?birthDate . }
}
ORDER BY ?name
LIMIT 30""",
    },
    {
        "title": "Betis players",
        "desc":  "Football players who have played for Real Betis",
        "query": """\
PREFIX dbo:  <http://dbpedia.org/ontology/>
PREFIX dbr:  <http://dbpedia.org/resource/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?player ?name ?birthDate ?birthPlace ?position
WHERE {
  ?player a dbo:SoccerPlayer .
  ?player dbo:team dbr:Real_Betis .

  ?player rdfs:label ?name .
  FILTER (langMatches(lang(?name), "es"))

  OPTIONAL { ?player dbo:birthDate  ?birthDate . }
  OPTIONAL { ?player dbo:birthPlace ?birthPlace . }
  OPTIONAL { ?player dbo:position   ?position . }
}
LIMIT 50""",
    },

]

def _run_sparql(query: str) -> tuple[list[str], list[dict], str | None]:
    try:
        resp = _requests.get(
            _SPARQL_ENDPOINT,
            params={"query": query, "format": "application/sparql-results+json"},
            timeout=_SPARQL_TIMEOUT,
            headers={"Accept": "application/sparql-results+json"},
        )
        resp.raise_for_status()
        data = resp.json()
        cols = data["head"]["vars"]
        rows = data["results"]["bindings"]
        return cols, rows, None
    except _requests.exceptions.Timeout:
        return [], [], f"Request timed out after {_SPARQL_TIMEOUT}s. Try a more specific query."
    except _requests.exceptions.HTTPError as e:
        return [], [], f"HTTP {e.response.status_code}: {e.response.text[:400]}"
    except Exception as e:
        return [], [], str(e)


def _render_sparql_value(binding: dict) -> str:
    if not binding:
        return '<span style="color:#334155;">—</span>'
    t   = binding.get("type", "")
    val = binding.get("value", "")
    if t == "uri":
        short = val
        for ns in ("http://dbpedia.org/resource/", "http://dbpedia.org/ontology/",
                   "http://dbpedia.org/property/", "http://www.w3.org/2000/01/rdf-schema#",
                   "http://purl.org/dc/terms/"):
            if val.startswith(ns):
                short = val[len(ns):]
                break
        short = urllib.parse.unquote(short).replace("_", " ")
        return (f'<a class="sparql-uri" href="{val}" target="_blank" title="{val}">'
                f'{short}</a>')
    elif t == "literal":
        lang = binding.get("xml:lang", "")
        lang_badge = f'<span class="sparql-lang">@{lang}</span>' if lang else ""
        escaped = val.replace("&", "&amp;").replace("<", "&lt;")
        if len(escaped) > 400:
            escaped = escaped[:400] + "…"
        return f'<span class="sparql-literal">{escaped}</span>{lang_badge}'
    else:
        return f'<code style="color:#94a3b8;font-size:.78rem;">{val}</code>'


def _sparql_table_html(cols: list[str], rows: list[dict]) -> str:
    if not rows:
        return '<p style="color:#475569;font-size:.85rem;padding:.5rem 0;">No results returned.</p>'
    header = "".join(f"<th>{c}</th>" for c in cols)
    body   = ""
    for row in rows:
        cells = "".join(
            f"<td>{_render_sparql_value(row.get(c))}</td>" for c in cols
        )
        body += f"<tr>{cells}</tr>"
    return (
        f'<div style="overflow-x:auto;border:1px solid #1e3a5f;border-radius:8px;">'
        f'<table class="sparql-table"><thead><tr>{header}</tr></thead>'
        f'<tbody>{body}</tbody></table></div>'
    )


# UI 
sparql_tab_preset, sparql_tab_editor = st.tabs(["Preset Queries", "Query Editor"])

with sparql_tab_preset:
    st.markdown("Click a card to load the query, then press **Run**.")
    st.markdown("")

    cols_per_row = 4
    preset_cols  = st.columns(cols_per_row)
    for idx, preset in enumerate(_PRESETS):
        with preset_cols[idx % cols_per_row]:
            st.markdown(
                f'<div class="preset-card" style="pointer-events:none;">'
                f'<div class="preset-card-title">{preset["title"]}</div>'
                f'<div class="preset-card-desc">{preset["desc"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button("Load", key=f"preset_{idx}", use_container_width=True):
                st.session_state["sparql_query"]  = preset["query"]
                st.session_state["sparql_result"] = None
                st.rerun()

with sparql_tab_editor:
    pass

st.markdown("")
st.markdown(
    f'<div class="sparql-editor-wrap">'
    f'  <div class="sparql-editor-bar">'
    f'    <span class="sparql-editor-label">SPARQL Query</span>'
    f'    <span class="sparql-endpoint-badge">endpoint: {_SPARQL_ENDPOINT}</span>'
    f'  </div>'
    f'</div>',
    unsafe_allow_html=True,
)

default_query = st.session_state.get("sparql_query", _PRESETS[0]["query"])
query_input   = st.text_area(
    "sparql_input",
    value=default_query,
    height=260,
    key="sparql_text_area",
    label_visibility="collapsed",
)

run_col, clear_col, info_col = st.columns([2, 1, 5])
with run_col:
    run_clicked = st.button("▶ Run query", type="primary", use_container_width=True)
with clear_col:
    if st.button("✕ Clear", use_container_width=True):
        st.session_state["sparql_result"] = None
        st.rerun()
with info_col:
    st.caption(
        f"Results capped at the LIMIT in your query · "
        f"Timeout: {_SPARQL_TIMEOUT}s · "
        f"Docs: [DBpedia SPARQL](https://dbpedia.org/sparql)"
    )

if run_clicked:
    if not query_input.strip():
        st.warning("Write a SPARQL query first.")
    else:
        st.session_state["sparql_query"] = query_input
        with st.spinner("Querying DBpedia SPARQL endpoint…"):
            cols, rows, err = _run_sparql(query_input)
        st.session_state["sparql_result"] = {
            "cols": cols, "rows": rows, "error": err,
            "count": len(rows),
        }

sparql_res = st.session_state.get("sparql_result")
if sparql_res is not None:
    st.markdown("")
    if sparql_res["error"]:
        st.error(f"**SPARQL error:** {sparql_res['error']}")
    else:
        cols  = sparql_res["cols"]
        rows  = sparql_res["rows"]
        count = sparql_res["count"]

        res_col1, res_col2 = st.columns([6, 1])
        with res_col1:
            st.markdown(
                f'<span style="font-family:\'Space Mono\',monospace;font-size:.78rem;color:#4ade80;">'
                f'✓ {count:,} row{"s" if count != 1 else ""} · {len(cols)} column{"s" if len(cols) != 1 else ""}'
                f'</span>',
                unsafe_allow_html=True,
            )
        with res_col2:
            # Download as CSV
            if rows:
                flat = [{c: (row.get(c, {}) or {}).get("value", "") for c in cols} for row in rows]
                csv_str = _pd.DataFrame(flat).to_csv(index=False)
                st.download_button(
                    "⬇ CSV",
                    data=csv_str,
                    file_name="sparql_results.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        st.markdown("")
        st.markdown(_sparql_table_html(cols, rows), unsafe_allow_html=True)


st.divider()
st.caption(
    "Wikipedia Graph Explorer · Data: Wikimedia Foundation · DBpedia · "
    "Graph DB: Neo4j · UI: Streamlit"
)