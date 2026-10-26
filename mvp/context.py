"""Research context for AI insight generation.

Loads and indexes the key research papers so they can be injected as
background context when generating hypotheses for any node.
"""

import os
from typing import Dict, List

RESEARCH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research")

# Map node types/patterns to relevant research papers
RESEARCH_INDEX = {
    "experiment": ["experiment-initiative-design.md"],
    "harness": ["agentic-harnesses-strategy-advisors.md"],
    "constraint": ["constraints-modelling.md"],
    "kpi": ["kpi-trees-benchmarking.md"],
    "graph": ["transformation-graph.md", "transformation-algebra.md"],
    "iteration": ["iteration-speed.md"],
    "systems": ["systems-dynamics-toc.md"],
    "value_chain": ["value-chain-capabilities-layers.md"],
    "failure": ["business-graph-projects-failures.md"],
    "revenue": ["transformation-graph.md", "kpi-trees-benchmarking.md", "experiment-initiative-design.md"],
    "cost": ["transformation-algebra.md", "constraints-modelling.md", "experiment-initiative-design.md"],
    "staff": ["constraints-modelling.md", "agentic-harnesses-strategy-advisors.md"],
    "overhead": ["transformation-algebra.md", "experiment-initiative-design.md"],
    "product": ["kpi-trees-benchmarking.md", "experiment-initiative-design.md"],
    "pnl": ["transformation-graph.md", "kpi-trees-benchmarking.md", "experiment-initiative-design.md", "systems-dynamics-toc.md"],
    "cogs": ["transformation-algebra.md", "value-chain-capabilities-layers.md"],
    "process": ["transformation-algebra.md", "value-chain-capabilities-layers.md", "iteration-speed.md"],
}

# Core papers always included
CORE_PAPERS = [
    "transformation-graph.md",
    "experiment-initiative-design.md",
    "constraints-modelling.md",
]

_cache: Dict[str, str] = {}

def _load_paper(filename: str) -> str:
    if filename in _cache:
        return _cache[filename]
    path = os.path.join(RESEARCH_DIR, filename)
    if os.path.exists(path):
        with open(path) as f:
            content = f.read()
        _cache[filename] = content
        return content
    return ""


def get_research_context(node_id: str, node_type: str, label: str, max_chars: int = 15000) -> str:
    """Get relevant research context for a node."""
    papers_to_load = set(CORE_PAPERS)
    
    # Add node-specific papers
    for pattern, paper_list in RESEARCH_INDEX.items():
        if pattern in node_id.lower() or pattern in node_type.lower() or pattern in label.lower():
            papers_to_load.update(paper_list)
    
    # Build context string
    parts = []
    total_chars = 0
    for paper in sorted(papers_to_load):
        content = _load_paper(paper)
        if not content:
            continue
        # Take first portion, leaving room for other papers
        budget = max(max_chars - total_chars, 0)
        chunk = content[:budget] if budget > 0 else ""
        if chunk:
            parts.append(f"--- {paper} ---\n{chunk}\n")
            total_chars += len(chunk)
    
    return "\n".join(parts)


def get_all_papers_summary() -> str:
    """Brief summary of all research papers for system prompt."""
    summaries = []
    for filename in sorted(_cache.keys()):
        content = _cache[filename]
        # Extract section headers for summary
        headers = [line.strip() for line in content.split("\n") if line.strip().startswith("## ")]
        summaries.append(f"### {filename}\n" + "\n".join(f"- {h.replace('## ', '')}" for h in headers[:10]))
    return "\n".join(summaries)
