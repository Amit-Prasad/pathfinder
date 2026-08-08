import json
import math
import shutil
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("update_tree_scores")

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = WORKSPACE_DIR / "pathfinder" / "results"
TREE_STATE_PATH = RESULTS_DIR / "tree_state.json"
BACKUP_PATH = RESULTS_DIR / "tree_state_backup_before_recalc.json"

SCENARIO_SPANS = {
    "random_30_days": 180.0 / 365.25,
    "random_range": 180.0 / 365.25,
    "random_days": 12.0 / 365.25,
    "random_hours": 24.0 / 365.25
}

WEIGHTS = {
    "random_30_days": 0.4,
    "random_range": 0.3,
    "random_days": 0.2,
    "random_hours": 0.1,
}

def calc_single_score(metrics: dict, years_span: float = 1.0) -> float:
    if not metrics:
        return 0.0
    total_trades = metrics.get("total_trades", 0)
    if total_trades == 0:
        return -5.0

    sharpe = metrics.get("sharpe_ratio", 0.0)
    drawdown = metrics.get("drawdown", 0.0)
    profit_factor = metrics.get("profit_factor", 1.0)

    if profit_factor == float('inf') or profit_factor is None:
        profit_factor = 5.0

    trades_per_year = total_trades / years_span if years_span > 0 else total_trades
    trades_term = math.log2(1 + max(trades_per_year, 0.0))

    score = sharpe * trades_term * profit_factor / (1.0 + drawdown)
    return round(score, 6)

def update_tree():
    if not TREE_STATE_PATH.exists():
        logger.error(f"Tree state not found at {TREE_STATE_PATH}")
        return

    shutil.copy2(TREE_STATE_PATH, BACKUP_PATH)
    logger.info(f"Backup created at {BACKUP_PATH}")

    with open(TREE_STATE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("nodes", {})
    logger.info(f"Recalculating scores for {len(nodes)} nodes using Sharpe-based formula...")

    updated_count = 0

    for nid, node in nodes.items():
        metrics = node.get("metrics", {})
        if not metrics or node.get("raw_score", -100.0) <= -100.0:
            continue

        sb = metrics.get("scenario_breakdown", {})
        if sb:
            weighted_score = 0.0
            for s_name, w in WEIGHTS.items():
                if s_name in sb:
                    sub_data = sb[s_name]
                    sub_metrics = sub_data.get("metrics", {})
                    s_score = calc_single_score(sub_metrics, years_span=SCENARIO_SPANS.get(s_name, 1.0))
                    sub_data["score"] = s_score
                    weighted_score += s_score * w

            weighted_score = round(weighted_score, 6)
            metrics["combined_score"] = weighted_score
            node["raw_score"] = weighted_score
        else:
            new_score = calc_single_score(metrics, years_span=1.0)
            node["raw_score"] = new_score

        updated_count += 1

    # Reset visit / max_score propagation
    for nid, node in nodes.items():
        node["visits"] = 0
        node["cumulative_score"] = 0.0
        node["max_score"] = -999999.0

    # Backpropagate scores from root to leaves
    sorted_node_ids = sorted([int(k) for k in nodes.keys()])
    for nid in sorted_node_ids:
        node = nodes[str(nid)]
        score = node.get("raw_score", -100.0)
        
        # Walk up to root
        curr = node
        while curr is not None:
            curr["visits"] += 1
            curr["cumulative_score"] += score
            if score > curr["max_score"]:
                curr["max_score"] = score
            parent_id = curr.get("parent_id")
            if parent_id is not None and str(parent_id) in nodes:
                curr = nodes[str(parent_id)]
            else:
                curr = None

    with open(TREE_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Successfully updated scores for {updated_count} nodes in {TREE_STATE_PATH}")

if __name__ == "__main__":
    update_tree()
