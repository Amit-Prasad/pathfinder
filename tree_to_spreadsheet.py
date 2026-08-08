import json
import csv
from pathlib import Path

def convert_tree_to_csv():
    # Find absolute paths relative to this script
    pathfinder_dir = Path(__file__).resolve().parent
    state_file = pathfinder_dir / "results" / "tree_state.json"
    output_csv = pathfinder_dir / "results" / "tree_state.csv"
    
    if not state_file.exists():
        print(f"Error: Tree state JSON not found at: {state_file}")
        return
        
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        print(f"Failed to read tree state JSON: {e}")
        return
        
    nodes = state.get("nodes", {})
    if not nodes:
        print("No nodes found in tree state.")
        return
        
    scenarios = ["random_30_days", "random_range", "random_days", "random_hours"]
    scenario_labels = {
        "random_30_days": "Random 30 Days",
        "random_range": "Random Range",
        "random_days": "Random Days",
        "random_hours": "Random Hours"
    }
    
    # Columns to write
    fieldnames = [
        "Node ID",
        "Parent ID",
        "Idea Description",
        "Visits",
        "Raw Score",
        "Cumulative Score",
        "Max Score",
        "Prior Prob",
        "Model Used",
        "Profit %",
        "Drawdown %",
        "Sharpe Ratio",
        "Expectancy",
        "Profit Factor",
        "Total Trades",
        "Is Expanded"
    ]
    
    for sc in scenarios:
        label = scenario_labels[sc]
        fieldnames.extend([
            f"{label} Score",
            f"{label} Profit %",
            f"{label} Drawdown %",
            f"{label} Sharpe Ratio",
            f"{label} Profit Factor",
            f"{label} Total Trades"
        ])
    
    rows = []
    for k, node in nodes.items():
        metrics = node.get("metrics", {})
        row = {
            "Node ID": node.get("id"),
            "Parent ID": node.get("parent_id") if node.get("parent_id") is not None else "",
            "Idea Description": node.get("idea_description", ""),
            "Visits": node.get("visits", 0),
            "Raw Score": round(node.get("raw_score", 0.0), 6),
            "Cumulative Score": round(node.get("cumulative_score", 0.0), 6),
            "Max Score": round(node.get("max_score", 0.0), 6),
            "Prior Prob": round(node.get("prior_prob", 0.0), 6),
            "Model Used": node.get("model_used", "Unknown"),
            "Profit %": round(metrics.get("profit_percentage", 0.0), 6) if "profit_percentage" in metrics else "-",
            "Drawdown %": round(metrics.get("drawdown", 0.0), 6) if "drawdown" in metrics else "-",
            "Sharpe Ratio": round(metrics.get("sharpe_ratio", 0.0), 6) if "sharpe_ratio" in metrics else "-",
            "Expectancy": round(metrics.get("expectancy", 0.0), 6) if "expectancy" in metrics else "-",
            "Profit Factor": round(metrics.get("profit_factor", 0.0), 6) if "profit_factor" in metrics else "-",
            "Total Trades": metrics.get("total_trades", "-"),
            "Is Expanded": node.get("is_expanded", False)
        }
        
        breakdown = metrics.get("scenario_breakdown", {})
        for sc in scenarios:
            label = scenario_labels[sc]
            sc_data = breakdown.get(sc, {})
            sc_metrics = sc_data.get("metrics", {})
            
            row[f"{label} Score"] = round(sc_data.get("score", 0.0), 6) if "score" in sc_data else "-"
            row[f"{label} Profit %"] = round(sc_metrics.get("profit_percentage", 0.0), 6) if "profit_percentage" in sc_metrics else "-"
            row[f"{label} Drawdown %"] = round(sc_metrics.get("drawdown", 0.0), 6) if "drawdown" in sc_metrics else "-"
            row[f"{label} Sharpe Ratio"] = round(sc_metrics.get("sharpe_ratio", 0.0), 6) if "sharpe_ratio" in sc_metrics else "-"
            row[f"{label} Profit Factor"] = round(sc_metrics.get("profit_factor", 0.0), 6) if "profit_factor" in sc_metrics else "-"
            row[f"{label} Total Trades"] = sc_metrics.get("total_trades", "-")
            
        rows.append(row)
        
    # Sort by ID
    rows.sort(key=lambda x: int(x["Node ID"]))
    
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Spreadsheet CSV generated successfully at:\n{output_csv}")

if __name__ == "__main__":
    convert_tree_to_csv()
