"""AI insights engine — generates actionable hypotheses for each node.

Uses the LLM (via OpenRouter API) to produce:
  - 3-5 hypotheses to improve the metric
  - Each with: description, expected impact, confidence, constraints, timeline
  - All hypotheses respect the constraint model
  - Research context injected into every prompt
"""

import json
import os
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any

from .model.constraints import ConstraintStore, Constraint
from .context import get_research_context


SYSTEM_PROMPT = """You are a business strategy advisor for an independent UK coffee shop called JonCo Coffee Limited in Handcross, West Sussex.

## CONTEXT
JonCo is a small independent coffee shop operating at barely break-even (0.4% operating margin).
- Monthly revenue: ~£20,763
- Monthly COGS: ~£4,937 (23.8% of revenue)
- Monthly staff costs: ~£11,062 (53.3% of revenue — benchmark: 30%)
- Monthly overheads: ~£4,674 (22.5% of revenue — benchmark: 20%)
- Monthly operating profit: ~£91 (0.4% margin — benchmark: 10%)
- 9,432 transactions over 3 months (Oct-Dec 2024)
- 5 staff: 3 baristas, 1 shift supervisor, 1 manager
- 17 menu items across coffee, pastry, hot drinks, cold drinks
- 5 suppliers: Has Bean Coffee Co (beans), Arla/Oatly/Alpro (milk), Bakers Delight (pastries), Vegware (packaging), various (consumables)

The business is modelled as a transformation graph: inputs → processes → revenue → costs → profit.
Every node has rolling 7-day and 30-day change metrics, benchmarks, and optimisation levers.

## RESEARCH BACKGROUND
The research papers below contain deep analysis of business modelling, transformation graphs,
constraint modelling, experiment design, and agentic strategy. Use them to inform your hypotheses.

{research_context}

## ACTIVE CONSTRAINTS
The following constraints limit what actions are feasible. Your hypotheses MUST respect these:

{constraints_text}

## TASK
For the node "{node_label}" (currently £{node_value}/month, 7d trend: {node_trend} {node_change_7d_pct}%),
generate 3-5 specific, actionable hypotheses to improve performance.

Each hypothesis should include:
1. **title** — short, specific action
2. **description** — 2-3 sentences explaining the mechanism
3. **expected_impact_gbp** — estimated monthly revenue/cost impact in GBP
4. **confidence** — "high", "medium", or "low" based on evidence strength
5. **timeline** — "immediate" (0-2 weeks), "short" (1-3 months), or "medium" (3-12 months)
6. **constraints_affected** — list of constraint IDs this hypothesis interacts with
7. **risk** — what could go wrong
8. **metrics_to_track** — which KPIs to monitor to validate the hypothesis
9. **counterfactual** — what would happen if we did NOT do this

Return ONLY valid JSON in this format:
{{
  "node_id": "{node_id}",
  "node_label": "{node_label}",
  "current_value": {node_value},
  "hypotheses": [
    {{
      "title": "...",
      "description": "...",
      "expected_impact_gbp": 0.0,
      "confidence": "medium",
      "timeline": "short",
      "constraints_affected": [],
      "risk": "...",
      "metrics_to_track": ["..."],
      "counterfactual": "..."
    }}
  ]
}}"""


def _build_constraints_text(constraints: List[Constraint], node_id: str) -> str:
    """Format constraints as text for the prompt."""
    if not constraints:
        return "No active constraints for this node."
    
    lines = []
    for c in constraints:
        severity = "🔴 HARD" if c.severity.value == "hard" else "🟡 SOFT"
        lines.append(f"- [{severity}] **{c.name}** ({c.id})")
        lines.append(f"  {c.description}")
        if c.parameters:
            params_str = ", ".join(f"{k}={v}" for k, v in c.parameters.items())
            lines.append(f"  Parameters: {params_str}")
        if c.severity.value == "soft":
            lines.append(f"  Penalty: £{c.penalty_per_unit:.2f} per {c.penalty_unit}")
        lines.append("")
    
    return "\n".join(lines)


def call_llm(messages: List[dict], model: str = "deepseek/deepseek-v4.1-flash", timeout: int = 120,
             max_tokens: int = 4000) -> str:
    """Call OpenRouter API directly via curl."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        # Try to read from hermes config
        import yaml
        config_path = os.path.expanduser("~/.hermes/config.yaml")
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = yaml.safe_load(f)
            # Check providers
            for prov_name, prov_config in config.get("providers", {}).items():
                if "api_key" in str(prov_config):
                    api_key = prov_config.get("api_key", "")
                    if api_key and "sk-or" in api_key:
                        break
                    api_key = ""  # not OpenRouter
    
    if not api_key:
        return json.dumps({
            "error": "No OpenRouter API key found. Set OPENROUTER_API_KEY env var.",
            "hypotheses": []
        })
    
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens,
        "reasoning": {"max_tokens": 1200, "exclude": False}
    })
    
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:8080",
            "X-Title": "Business as a Machine MVP"
        },
        method="POST"
    )
    
    import concurrent.futures
    def _do_request():
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"].get("content")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_do_request)
            content = fut.result(timeout=timeout + 10)
        if not content:
            return json.dumps({"error": "empty response from model", "hypotheses": []})
        return content
    except concurrent.futures.TimeoutError:
        return json.dumps({"error": f"LLM hard timeout after {timeout+10}s", "hypotheses": []})
    except Exception as e:
        return json.dumps({"error": str(e), "hypotheses": []})


def generate_insights(
    node_id: str,
    node_label: str,
    node_value: float,
    node_trend: str,
    node_change_7d_pct: float,
    node_change_30d_pct: float,
    node_type: str,
    constraint_store: ConstraintStore,
    graph=None,
    model: str = "deepseek/deepseek-v4.1-flash"
) -> dict:
    """Generate AI-powered insights for a node."""
    
    # Get constraints
    constraints = constraint_store.get_for_node(node_id, graph)
    constraints_text = _build_constraints_text(constraints, node_id)
    
    # Get research context
    research_context = get_research_context(node_id, node_type, node_label)
    
    # Build prompt
    system_prompt = SYSTEM_PROMPT.format(
        research_context=research_context[:6000],
        constraints_text=constraints_text,
        node_id=node_id,
        node_label=node_label,
        node_value=f"{node_value:,.2f}",
        node_trend=node_trend,
        node_change_7d_pct=f"{node_change_7d_pct:+.1f}",
    )
    
    user_prompt = f"Generate hypotheses for {node_label}. Current: £{node_value:,.2f}/month. 7d trend: {node_trend} ({node_change_7d_pct:+.1f}%). 30d trend: {node_change_30d_pct:+.1f}%."
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    raw = call_llm(messages, model=model)
    
    # Parse JSON response
    try:
        # Find JSON in response (might be wrapped in code blocks)
        if raw.startswith("```"):
            # Strip code fences
            lines = raw.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```json") or line.startswith("```"):
                    in_json = not in_json if line.startswith("```") else True
                    continue
                if in_json:
                    json_lines.append(line)
            raw = "\n".join(json_lines)
        
        result = json.loads(raw)
        return result
    except json.JSONDecodeError:
        return {"error": "Failed to parse LLM response", "raw": raw[:500], "hypotheses": []}
