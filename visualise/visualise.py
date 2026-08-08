import os
import json
import logging
import webbrowser
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("pathfinder.visualiser")
logging.basicConfig(level=logging.INFO)

def build_hierarchy(nodes: Dict[str, Any], curr_id: str) -> Dict[str, Any]:
    """Recursively builds the hierarchical JSON structure from flat nodes map."""
    node = nodes.get(curr_id)
    if not node:
        return {}

    children = []
    for cid in node.get("children_ids", []):
        child_struct = build_hierarchy(nodes, str(cid))
        if child_struct:
            children.append(child_struct)

    # Clean short name for labels
    desc = node.get("idea_description", "")
    short_name = desc[:30] + "..." if len(desc) > 30 else desc
    
    return {
        "id": node.get("id"),
        "name": short_name,
        "full_description": desc,
        "visits": node.get("visits", 0),
        "score": node.get("raw_score", 0.0),
        "cumulative_score": node.get("cumulative_score", 0.0),
        "max_score": node.get("max_score", 0.0),
        "prior_prob": node.get("prior_prob", 0.0),
        "metrics": node.get("metrics", {}),
        "research_context": node.get("research_context", ""),
        "model_used": node.get("model_used", "Unknown"),
        "dag_parent_ids": node.get("dag_parent_ids", None),
        "children": children
    }


def generate_html(tree_data: Dict[str, Any], flat_nodes: list[Dict[str, Any]]) -> str:
    """Generates the interactive HTML content using D3.js and a premium dark design."""
    json_data = json.dumps(tree_data, indent=2)
    flat_nodes_json = json.dumps(flat_nodes, indent=2)
    
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Pathfinder Tree Visualisation</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        :root {
            --bg-color: #0c0c0e;
            --sidebar-bg: #141417;
            --border-color: #232329;
            --text-primary: #f4f4f6;
            --text-secondary: #9499a6;
            --accent-green: #10b981;
            --accent-yellow: #f59e0b;
            --accent-red: #ef4444;
            --accent-gray: #6b7280;
            --accent-blue: #3b82f6;
            --font-family: 'Inter', sans-serif;
            --header-font: 'Outfit', sans-serif;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: var(--font-family);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            height: 100vh;
            padding-top: 56px;
        }

        /* Navigation Bar */
        #nav-bar {
            display: flex;
            background-color: var(--sidebar-bg);
            border-bottom: 1px solid var(--border-color);
            width: 100%;
            height: 56px;
            align-items: center;
            justify-content: flex-start;
            padding: 0 24px;
            gap: 8px;
            z-index: 100;
            position: fixed;
            top: 0;
            left: 0;
        }
        
        .nav-tab {
            color: var(--text-secondary);
            font-family: var(--header-font);
            font-size: 13.5px;
            font-weight: 600;
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 8px;
            border: 1px solid transparent;
            user-select: none;
        }
        
        .nav-tab:hover {
            color: var(--text-primary);
            background-color: rgba(255, 255, 255, 0.03);
        }
        
        .nav-tab.active {
            color: var(--accent-blue);
            background-color: rgba(59, 130, 246, 0.08);
            border: 1px solid rgba(59, 130, 246, 0.15);
        }

        /* App Layout */
        #main-layout {
            display: flex;
            flex-direction: row;
            width: 100%;
            height: calc(100vh - 56px);
        }

        #visualisation-area {
            flex: 1;
            position: relative;
            height: 100%;
        }

        #sidebar {
            width: 420px;
            background-color: var(--sidebar-bg);
            border-left: 1px solid var(--border-color);
            height: 100%;
            overflow-y: auto;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            box-shadow: -4px 0 20px rgba(0, 0, 0, 0.4);
            z-index: 10;
        }

        /* Header Info */
        h1 {
            font-family: var(--header-font);
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 4px;
            letter-spacing: -0.5px;
        }

        h2 {
            font-family: var(--header-font);
            font-size: 18px;
            font-weight: 600;
            margin-top: 10px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
        }

        .subtitle {
            color: var(--text-secondary);
            font-size: 13px;
        }

        /* D3 Elements */
        .node circle {
            stroke-width: 2.5px;
            cursor: pointer;
            transition: r 0.2s, stroke-width 0.2s;
        }

        .node circle:hover {
            r: 10px;
            stroke-width: 4px;
        }

        .node text {
            font-size: 11px;
            fill: var(--text-primary);
            font-weight: 500;
            text-shadow: 0 1px 3px rgba(0,0,0,0.9);
        }

        .link {
            fill: none;
            stroke: #2e2e38;
            stroke-width: 1.5px;
            transition: stroke 0.2s;
        }

        .link.active {
            stroke: var(--accent-blue);
            stroke-width: 2.5px;
        }

        .link.dag-link {
            stroke: var(--accent-blue);
            stroke-dasharray: 4,4;
            stroke-width: 1.5px;
            opacity: 0.8;
        }

        /* Sidebar content styling */
        .detail-card {
            background: #1c1c21;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .detail-row {
            display: flex;
            justify-content: space-between;
            font-size: 13px;
        }

        .detail-label {
            color: var(--text-secondary);
        }

        .detail-value {
            font-weight: 600;
            font-family: var(--header-font);
        }

        .metrics-pre {
            background-color: #0c0c0e;
            border: 1px solid #232329;
            padding: 12px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 12px;
            color: #a7f3d0;
            overflow-x: auto;
            white-space: pre-wrap;
        }

        .research-box {
            font-size: 13px;
            color: #d1d5db;
            line-height: 1.6;
            background: #18181f;
            border-left: 3px solid var(--accent-blue);
            padding: 12px;
            border-radius: 0 8px 8px 0;
            max-height: 250px;
            overflow-y: auto;
            white-space: pre-wrap;
        }

        /* Controls Panel */
        #controls {
            position: absolute;
            top: 24px;
            left: 24px;
            background-color: rgba(20, 20, 23, 0.85);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border-color);
            padding: 12px 18px;
            border-radius: 12px;
            display: flex;
            gap: 16px;
            font-size: 13px;
            color: var(--text-secondary);
        }

        .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .legend-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }

        /* Tooltip */
        .tooltip {
            position: absolute;
            padding: 8px 12px;
            background: #141417;
            border: 1px solid var(--border-color);
            color: white;
            border-radius: 8px;
            font-size: 11px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
            z-index: 100;
        }

        /* Spreadsheet Container */
        #spreadsheet-container {
            flex: 1;
            height: calc(100vh - 56px);
            padding: 32px;
            overflow-y: auto;
            background-color: var(--bg-color);
            display: flex;
            flex-direction: column;
            gap: 20px;
            width: 100%;
        }

        .spreadsheet-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .search-bar {
            background-color: var(--sidebar-bg);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            font-family: var(--font-family);
            font-size: 13.5px;
            padding: 10px 16px;
            border-radius: 8px;
            width: 320px;
            transition: all 0.2s;
        }

        .search-bar:focus {
            outline: none;
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
        }

        .table-wrapper {
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: auto;
            background-color: var(--sidebar-bg);
            flex: 1;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }

        th {
            background-color: #1a1a1f;
            color: var(--text-secondary);
            font-family: var(--header-font);
            font-weight: 600;
            padding: 14px 16px;
            border-bottom: 1px solid var(--border-color);
            position: sticky;
            top: 0;
            cursor: pointer;
            user-select: none;
            z-index: 10;
        }

        th:hover {
            color: var(--text-primary);
            background-color: #222229;
        }

        th .sort-icon {
            display: inline-block;
            margin-left: 6px;
            opacity: 0.7;
        }

        td {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            font-family: var(--font-family);
            color: #d1d5db;
        }

        tr:last-child td {
            border-bottom: none;
        }

        tr {
            transition: background-color 0.15s;
        }

        tr:hover {
            background-color: rgba(255, 255, 255, 0.02);
            cursor: pointer;
        }

        .score-badge {
            font-weight: 600;
            font-family: var(--header-font);
        }

        .action-btn {
            background: rgba(59, 130, 246, 0.1);
            color: var(--accent-blue);
            border: 1px solid rgba(59, 130, 246, 0.2);
            padding: 4px 8px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 11px;
            font-weight: 600;
            transition: all 0.2s;
        }

        .action-btn:hover {
            background: var(--accent-blue);
            color: white;
        }
    </style>
</head>
<body>
    <div id="nav-bar">
        <div class="nav-tab active" onclick="switchTab('tree')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
            Tree Diagram
        </div>
        <div class="nav-tab" onclick="switchTab('spreadsheet')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line><line x1="15" y1="3" x2="15" y2="21"></line><line x1="3" y1="9" x2="21" y2="9"></line><line x1="3" y1="15" x2="21" y2="15"></line></svg>
            Spreadsheet Table
        </div>
    </div>

    <div id="main-layout" class="tab-content">
        <div id="visualisation-area">
            <div id="controls">
                <div class="legend-item">
                    <span class="legend-dot" style="background-color: var(--accent-green)"></span> Score &gt; 2.0
                </div>
                <div class="legend-item">
                    <span class="legend-dot" style="background-color: var(--accent-yellow)"></span> Score 0 - 2
                </div>
                <div class="legend-item">
                    <span class="legend-dot" style="background-color: var(--accent-red)"></span> Score &lt; 0
                </div>
                <div class="legend-item">
                    <span class="legend-dot" style="background-color: var(--accent-gray)"></span> Unvisited (Visits=0)
                </div>
            </div>
            <div id="tooltip" class="tooltip"></div>
        </div>
        
        <div id="sidebar">
            <div>
                <h1>Pathfinder Tree</h1>
                <span class="subtitle">Click any node to explore details and code artifacts</span>
            </div>
            
            <h2>Node Properties</h2>
            <div class="detail-card">
                <div class="detail-row">
                    <span class="detail-label">Node ID:</span>
                    <span id="prop-id" class="detail-value">-</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Model Used:</span>
                    <span id="prop-model" class="detail-value">-</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Visits count:</span>
                    <span id="prop-visits" class="detail-value">-</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Prior Probability:</span>
                    <span id="prop-prior" class="detail-value">-</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Raw Evaluation Score:</span>
                    <span id="prop-score" class="detail-value" style="color: var(--accent-green);">-</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Subtree Max Score:</span>
                    <span id="prop-max-score" class="detail-value">-</span>
                </div>
                <div class="detail-row" id="prop-dag-row" style="display: none;">
                    <span class="detail-label">DAG Parents:</span>
                    <span id="prop-dag-parents" class="detail-value">-</span>
                </div>
            </div>

            <h2>Optimization Idea</h2>
            <div class="detail-card" style="font-size: 13.5px; line-height: 1.5;" id="prop-desc">
                Select a node in the tree diagram to inspect the generated idea.
            </div>

            <h2>Sandbox Evaluation Metrics</h2>
            <pre id="prop-metrics" class="metrics-pre">{ "No data" }</pre>

            <h2>Research Context</h2>
            <div id="prop-research" class="research-box">No research summary associated with this node.</div>
        </div>
    </div>

    <div id="spreadsheet-container" class="tab-content" style="display: none;">
        <div class="spreadsheet-header">
            <div>
                <h1 style="margin-bottom: 2px;">Tree Metrics Spreadsheet</h1>
                <span class="subtitle">A flat tabular view of all generated nodes and metrics. Click a row to inspect its location in the tree.</span>
            </div>
            <input type="text" id="search-input" class="search-bar" placeholder="Search by ID, idea, model...">
        </div>
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th data-col="id" onclick="handleSort('id')">Node ID</th>
                        <th data-col="model" onclick="handleSort('model')">Model Used</th>
                        <th data-col="idea" onclick="handleSort('idea')">Idea Description</th>
                        <th data-col="visits" onclick="handleSort('visits')">Visits</th>
                        <th data-col="score" onclick="handleSort('score')">Raw Score</th>
                        <th data-col="max_score" onclick="handleSort('max_score')">Subtree Max</th>
                        <th data-col="profit" onclick="handleSort('profit')">Profit %</th>
                        <th data-col="drawdown" onclick="handleSort('drawdown')">Max DD</th>
                        <th data-col="sharpe" onclick="handleSort('sharpe')">Sharpe</th>
                        <th data-col="expectancy" onclick="handleSort('expectancy')">Expectancy</th>
                        <th data-col="pf" onclick="handleSort('pf')">Profit Factor</th>
                        <th data-col="trades" onclick="handleSort('trades')">Trades</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="table-body">
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        const treeData = __TREE_DATA__;
        const flatNodes = __FLAT_NODES__;

        function switchTab(tabId) {
            const tabs = document.querySelectorAll('.nav-tab');
            tabs[0].classList.toggle('active', tabId === 'tree');
            tabs[1].classList.toggle('active', tabId === 'spreadsheet');
            
            document.getElementById('main-layout').style.display = tabId === 'tree' ? 'flex' : 'none';
            document.getElementById('spreadsheet-container').style.display = tabId === 'spreadsheet' ? 'flex' : 'none';
            
            if (tabId === 'spreadsheet') {
                renderTable();
            }
        }

        function toggleRowExpansion(nodeId, event) {
            event.stopPropagation();
            const detailRow = document.getElementById(`detail-${nodeId}`);
            const arrow = document.getElementById(`arrow-${nodeId}`);
            if (detailRow.style.display === 'none') {
                detailRow.style.display = 'table-row';
                arrow.style.transform = 'rotate(90deg)';
            } else {
                detailRow.style.display = 'none';
                arrow.style.transform = 'rotate(0deg)';
            }
        }

        function focusTree(nodeId) {
            switchTab('tree');
            const d3Node = root.descendants().find(d => Number(d.data.id) === Number(nodeId));
            if (d3Node) {
                selectNode(d3Node.data);
            }
        }

        let currentSortColumn = 'id';
        let sortDirection = 'asc';
        let searchQuery = '';

        function renderTable() {
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = '';
            
            let filteredNodes = flatNodes.filter(node => {
                const idStr = String(node.id);
                const desc = (node.idea_description || '').toLowerCase();
                const model = (node.model_used || '').toLowerCase();
                const query = searchQuery.toLowerCase();
                
                return idStr.includes(query) || desc.includes(query) || model.includes(query);
            });
            
            filteredNodes.sort((a, b) => {
                let valA = getSortValue(a, currentSortColumn);
                let valB = getSortValue(b, currentSortColumn);
                
                if (typeof valA === 'string') {
                    return sortDirection === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
                } else {
                    return sortDirection === 'asc' ? valA - valB : valB - valA;
                }
            });
            
            filteredNodes.forEach(node => {
                const metrics = node.metrics || {};
                const profit = metrics.profit_percentage !== undefined ? metrics.profit_percentage : null;
                const dd = metrics.drawdown !== undefined ? metrics.drawdown : null;
                const sharpe = metrics.sharpe_ratio !== undefined ? metrics.sharpe_ratio : null;
                const expectancy = metrics.expectancy !== undefined ? metrics.expectancy : null;
                const pf = metrics.profit_factor !== undefined ? metrics.profit_factor : null;
                const trades = metrics.total_trades !== undefined ? metrics.total_trades : null;
                
                const tr = document.createElement('tr');
                tr.id = `row-${node.id}`;

                let scoreColor = 'var(--text-primary)';
                if (node.visits > 0) {
                    if (node.raw_score > 2.0) scoreColor = 'var(--accent-green)';
                    else if (node.raw_score >= 0.0) scoreColor = 'var(--accent-yellow)';
                    else scoreColor = 'var(--accent-red)';
                } else {
                    scoreColor = 'var(--accent-gray)';
                }
                
                let pfText = '-';
                if (pf !== null) {
                    if (pf === 999.0 || pf === Infinity) pfText = 'inf';
                    else pfText = pf.toFixed(4);
                }
                
                tr.innerHTML = `
                    <td onclick="toggleRowExpansion(${node.id}, event)" style="font-family: var(--header-font); font-weight: bold; cursor: pointer; user-select: none; white-space: nowrap;">
                        <span id="arrow-${node.id}" style="display: inline-block; width: 14px; transition: transform 0.2s; color: var(--accent-blue); transform-origin: center;">▶</span> Node ${node.id}
                    </td>
                    <td onclick="focusTree(${node.id})"><span class="detail-label">${node.model_used || 'baseline'}</span></td>
                    <td onclick="focusTree(${node.id})" style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${node.idea_description}">${node.idea_description}</td>
                    <td onclick="focusTree(${node.id})">${node.visits}</td>
                    <td><span class="score-badge" style="color: ${scoreColor}" onclick="focusTree(${node.id})">${node.raw_score.toFixed(4)}</span></td>
                    <td onclick="focusTree(${node.id})">${node.max_score.toFixed(4)}</td>
                    <td onclick="focusTree(${node.id})" style="color: ${profit > 0 ? 'var(--accent-green)' : profit < 0 ? 'var(--accent-red)' : 'inherit'}">${profit !== null ? profit.toFixed(4) + '%' : '-'}</td>
                    <td onclick="focusTree(${node.id})" style="color: ${dd > 10.0 ? 'var(--accent-red)' : 'inherit'}">${dd !== null ? dd.toFixed(4) + '%' : '-'}</td>
                    <td onclick="focusTree(${node.id})">${sharpe !== null ? sharpe.toFixed(4) : '-'}</td>
                    <td onclick="focusTree(${node.id})">${expectancy !== null ? expectancy.toFixed(4) : '-'}</td>
                    <td onclick="focusTree(${node.id})" style="color: ${pf > 2.0 ? 'var(--accent-green)' : pf < 1.0 ? 'var(--accent-red)' : 'inherit'}">${pfText}</td>
                    <td onclick="focusTree(${node.id})">${trades !== null ? trades : '-'}</td>
                    <td><button class="action-btn" onclick="focusTree(${node.id})">Inspect</button></td>
                `;
                tbody.appendChild(tr);

                // Build breakdown HTML
                let breakdownHtml = '';
                if (metrics.scenario_breakdown) {
                    const scenarios_list = [
                        { name: 'random_30_days', label: 'Random 30 Days', weight: '40%' },
                        { name: 'random_range', label: 'Random Range', weight: '30%' },
                        { name: 'random_days', label: 'Random Days', weight: '20%' },
                        { name: 'random_hours', label: 'Random Hours', weight: '10%' }
                    ];
                    
                    let rowsHtml = '';
                    scenarios_list.forEach(sc => {
                        const scData = metrics.scenario_breakdown[sc.name] || {};
                        const scMetrics = scData.metrics || {};
                        const scScore = scData.score !== undefined ? scData.score.toFixed(4) : '-';
                        const scProfit = scMetrics.profit_percentage !== undefined ? scMetrics.profit_percentage.toFixed(4) + '%' : '-';
                        const scDd = scMetrics.drawdown !== undefined ? scMetrics.drawdown.toFixed(4) + '%' : '-';
                        const scSharpe = scMetrics.sharpe_ratio !== undefined ? scMetrics.sharpe_ratio.toFixed(4) : '-';
                        const scExpectancy = scMetrics.expectancy !== undefined ? scMetrics.expectancy.toFixed(4) : '-';
                        
                        let scPfText = '-';
                        if (scMetrics.profit_factor !== undefined) {
                            if (scMetrics.profit_factor === 999.0 || scMetrics.profit_factor === Infinity) scPfText = 'inf';
                            else scPfText = scMetrics.profit_factor.toFixed(4);
                        }
                        
                        const scTrades = scMetrics.total_trades !== undefined ? scMetrics.total_trades : '-';
                        
                        rowsHtml += `
                            <tr style="background-color: transparent;">
                                <td style="padding: 6px 12px; font-weight: 500; border-bottom: 1px solid #232329;">${sc.label}</td>
                                <td style="padding: 6px 12px; color: var(--text-secondary); border-bottom: 1px solid #232329;">${sc.weight}</td>
                                <td style="padding: 6px 12px; font-weight: 600; border-bottom: 1px solid #232329;">${scScore}</td>
                                <td style="padding: 6px 12px; border-bottom: 1px solid #232329;">${scProfit}</td>
                                <td style="padding: 6px 12px; border-bottom: 1px solid #232329;">${scDd}</td>
                                <td style="padding: 6px 12px; border-bottom: 1px solid #232329;">${scSharpe}</td>
                                <td style="padding: 6px 12px; border-bottom: 1px solid #232329;">${scExpectancy}</td>
                                <td style="padding: 6px 12px; border-bottom: 1px solid #232329;">${scPfText}</td>
                                <td style="padding: 6px 12px; border-bottom: 1px solid #232329;">${scTrades}</td>
                            </tr>
                        `;
                    });
                    
                    breakdownHtml = `
                        <div style="display: flex; flex-direction: column; gap: 10px; padding: 4px 0;">
                            <span style="font-family: var(--header-font); font-size: 13px; font-weight: 600; color: var(--accent-blue);">Scenario Breakdown Metrics</span>
                            <table style="width: 100%; border-collapse: collapse; background-color: #121215; border-radius: 8px; border: 1px solid var(--border-color); overflow: hidden;">
                                <thead>
                                    <tr style="background-color: #1a1a22;">
                                        <th style="padding: 8px 12px; font-size: 11px; background-color: transparent; border-bottom: 1px solid var(--border-color); cursor: default; color: var(--text-secondary);">Scenario</th>
                                        <th style="padding: 8px 12px; font-size: 11px; background-color: transparent; border-bottom: 1px solid var(--border-color); cursor: default; color: var(--text-secondary);">Weight</th>
                                        <th style="padding: 8px 12px; font-size: 11px; background-color: transparent; border-bottom: 1px solid var(--border-color); cursor: default; color: var(--text-secondary);">Score</th>
                                        <th style="padding: 8px 12px; font-size: 11px; background-color: transparent; border-bottom: 1px solid var(--border-color); cursor: default; color: var(--text-secondary);">Profit %</th>
                                        <th style="padding: 8px 12px; font-size: 11px; background-color: transparent; border-bottom: 1px solid var(--border-color); cursor: default; color: var(--text-secondary);">Max DD</th>
                                        <th style="padding: 8px 12px; font-size: 11px; background-color: transparent; border-bottom: 1px solid var(--border-color); cursor: default; color: var(--text-secondary);">Sharpe</th>
                                        <th style="padding: 8px 12px; font-size: 11px; background-color: transparent; border-bottom: 1px solid var(--border-color); cursor: default; color: var(--text-secondary);">Expectancy</th>
                                        <th style="padding: 8px 12px; font-size: 11px; background-color: transparent; border-bottom: 1px solid var(--border-color); cursor: default; color: var(--text-secondary);">Profit Factor</th>
                                        <th style="padding: 8px 12px; font-size: 11px; background-color: transparent; border-bottom: 1px solid var(--border-color); cursor: default; color: var(--text-secondary);">Trades</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${rowsHtml}
                                </tbody>
                            </table>
                        </div>
                    `;
                } else {
                    breakdownHtml = `
                        <div style="color: var(--text-secondary); font-style: italic; font-size: 12px; padding: 8px 0;">
                            No scenario breakdown available (this node was evaluated using a single scenario model).
                        </div>
                    `;
                }

                const detailTr = document.createElement('tr');
                detailTr.id = `detail-${node.id}`;
                detailTr.style.display = 'none';
                detailTr.style.backgroundColor = '#0c0c0f';
                detailTr.innerHTML = `
                    <td colspan="12" style="padding: 16px 24px; border-bottom: 1px solid var(--border-color);">
                        ${breakdownHtml}
                    </td>
                `;
                tbody.appendChild(detailTr);
            });
            
            updateSortHeaders();
        }

        function getSortValue(node, col) {
            const metrics = node.metrics || {};
            switch(col) {
                case 'id': return node.id;
                case 'model': return (node.model_used || '').toLowerCase();
                case 'idea': return (node.idea_description || '').toLowerCase();
                case 'visits': return node.visits;
                case 'score': return node.raw_score;
                case 'max_score': return node.max_score;
                case 'profit': return metrics.profit_percentage !== undefined ? metrics.profit_percentage : -999999;
                case 'drawdown': return metrics.drawdown !== undefined ? metrics.drawdown : 999999;
                case 'sharpe': return metrics.sharpe_ratio !== undefined ? metrics.sharpe_ratio : -999999;
                case 'expectancy': return metrics.expectancy !== undefined ? metrics.expectancy : -999999;
                case 'pf': return metrics.profit_factor !== undefined ? metrics.profit_factor : -999999;
                case 'trades': return metrics.total_trades !== undefined ? metrics.total_trades : -999999;
                default: return 0;
            }
        }

        function handleSort(col) {
            if (currentSortColumn === col) {
                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                currentSortColumn = col;
                sortDirection = 'asc';
            }
            renderTable();
        }

        function updateSortHeaders() {
            const headers = document.querySelectorAll('th');
            headers.forEach(th => {
                const col = th.getAttribute('data-col');
                if (!col) return;
                
                let icon = '';
                if (col === currentSortColumn) {
                    icon = sortDirection === 'asc' ? ' ▲' : ' ▼';
                }
                
                const text = th.textContent.replace(' ▲', '').replace(' ▼', '');
                th.innerHTML = `${text}<span class="sort-icon">${icon}</span>`;
            });
        }

        document.getElementById('search-input').addEventListener('input', (e) => {
            searchQuery = e.target.value;
            renderTable();
        });

        // Screen Dimensions
        const width = Math.max(document.getElementById('visualisation-area').clientWidth || (window.innerWidth - 450), 600);
        const height = Math.max(document.getElementById('visualisation-area').clientHeight || (window.innerHeight - 56), 600);

        // Create SVG Canvas
        const svg = d3.select("#visualisation-area")
            .append("svg")
            .attr("width", "100%")
            .attr("height", "100%")
            .call(d3.zoom().on("zoom", function (event) {
                g.attr("transform", event.transform);
            }))
            .append("g");

        const g = svg.append("g")
            .attr("transform", "translate(60, 0)"); // Initial offset

        // Create the tree layout
        const tree = d3.tree()
            .size([height - 100, width - 450]);

        // Tooltip
        const tooltip = d3.select("#tooltip");

        // Parse tree hierarchy
        const root = d3.hierarchy(treeData, d => d.children);

        // Update Tree Rendering
        update(root);

        function update(source) {
            // Compute layout
            const treeData = tree(root);

            // Nodes & links
            const nodes = treeData.descendants();
            let links = treeData.links();

            // Find all DAG links and add them
            nodes.forEach(targetNode => {
                if (targetNode.data.dag_parent_ids) {
                    targetNode.data.dag_parent_ids.forEach(pid => {
                        // Skip the primary parent link (already in tree links)
                        if (targetNode.parent && targetNode.parent.data.id === pid) {
                            return;
                        }
                        // Find the source node in the layout
                        const sourceNode = nodes.find(n => n.data.id === pid);
                        if (sourceNode) {
                            links.push({
                                source: sourceNode,
                                target: targetNode,
                                is_dag_link: true
                            });
                        }
                    });
                }
            });

            // Set depth coordinate spacing
            nodes.forEach(d => d.y = d.depth * 220);

            // RENDER LINKS
            const link = g.selectAll(".link")
                .data(links, (d, i) => d.is_dag_link ? `dag-${d.source.data.id}-${d.target.data.id}` : d.target.id);

            link.enter()
                .insert("path", "g")
                .attr("class", d => d.is_dag_link ? "link dag-link" : "link")
                .attr("d", d3.linkHorizontal()
                    .x(d => d.y)
                    .y(d => d.x)
                );

            // RENDER NODES
            const node = g.selectAll("g.node")
                .data(nodes, d => d.data.id);

            const nodeEnter = node.enter()
                .append("g")
                .attr("class", "node")
                .attr("transform", d => `translate(${d.y}, ${d.x})`)
                .on("click", (event, d) => {
                    selectNode(d.data);
                })
                .on("mouseover", (event, d) => {
                    tooltip.style("opacity", 1)
                        .html(`<strong>Node ID:</strong> ${d.data.id}<br/><strong>Score:</strong> ${d.data.score.toFixed(4)}<br/><strong>Visits:</strong> ${d.data.visits}`)
                        .style("left", (event.pageX + 15) + "px")
                        .style("top", (event.pageY - 28) + "px");
                })
                .on("mousemove", (event) => {
                    tooltip.style("left", (event.pageX + 15) + "px")
                        .style("top", (event.pageY - 28) + "px");
                })
                .on("mouseout", () => {
                    tooltip.style("opacity", 0);
                });

            // Outer color circle mapping
            nodeEnter.append("circle")
                .attr("r", 7)
                .attr("fill", d => {
                    if (d.data.visits === 0) return "var(--accent-gray)";
                    if (d.data.score > 2.0) return "var(--accent-green)";
                    if (d.data.score >= 0.0) return "var(--accent-yellow)";
                    return "var(--accent-red)";
                })
                .attr("stroke", d => {
                    if (d.data.visits === 0) return "#374151";
                    if (d.data.score > 2.0) return "#047857";
                    if (d.data.score >= 0.0) return "#b45309";
                    return "#b91c1c";
                });

            nodeEnter.append("text")
                .attr("dy", ".31em")
                .attr("x", d => d.children ? -12 : 12)
                .attr("text-anchor", d => d.children ? "end" : "start")
                .text(d => `Node ${d.data.id}: ${d.data.name}`);

            // Highlight the root initially
            if (nodes.length > 0) {
                selectNode(nodes[0].data);
            }
        }

        function selectNode(data) {
            // Highlight links along path
            d3.selectAll(".link")
                .classed("active", d => {
                    let current = d.target;
                    while (current) {
                        if (current.data.id === data.id) return true;
                        current = current.parent;
                    }
                    return false;
                });

            // Fill details sidebar
            document.getElementById("prop-id").innerText = data.id;
            document.getElementById("prop-model").innerText = data.model_used || "Unknown";
            document.getElementById("prop-visits").innerText = data.visits;
            document.getElementById("prop-prior").innerText = data.prior_prob.toFixed(2);
            
            const scoreEl = document.getElementById("prop-score");
            scoreEl.innerText = data.score.toFixed(4);
            
            const dagRow = document.getElementById("prop-dag-row");
            const dagParents = document.getElementById("prop-dag-parents");
            if (data.dag_parent_ids && data.dag_parent_ids.length > 0) {
                dagParents.innerText = data.dag_parent_ids.join(", ");
                dagRow.style.display = "flex";
            } else {
                dagRow.style.display = "none";
            }

            if (data.visits === 0) {
                scoreEl.style.color = "var(--accent-gray)";
            } else if (data.score > 2.0) {
                scoreEl.style.color = "var(--accent-green)";
            } else if (data.score >= 0.0) {
                scoreEl.style.color = "var(--accent-yellow)";
            } else {
                scoreEl.style.color = "var(--accent-red)";
            }

            document.getElementById("prop-max-score").innerText = data.max_score.toFixed(4);
            document.getElementById("prop-desc").innerText = data.full_description;
            document.getElementById("prop-metrics").innerText = JSON.stringify(data.metrics, null, 2);

            
            const researchBox = document.getElementById("prop-research");
            if (data.research_context) {
                researchBox.innerText = data.research_context;
                researchBox.style.borderLeftColor = "var(--accent-blue)";
            } else {
                researchBox.innerText = "No research summary associated with this node.";
                researchBox.style.borderLeftColor = "var(--border-color)";
            }
        }
    </script>
</body>
</html>
"""
    return html_template.replace("__TREE_DATA__", json_data).replace("__FLAT_NODES__", flat_nodes_json)

def main():
    logger.info("Pathfinder Visualiser starting...")
    
    import sys
    # Paths
    project_dir = Path(__file__).resolve().parent.parent
    if len(sys.argv) > 1:
        state_file = Path(sys.argv[1]).resolve()
    else:
        state_file = project_dir / "results" / "tree_state.json"

    if len(sys.argv) > 2:
        output_html = Path(sys.argv[2]).resolve()
    else:
        output_html = project_dir / "results" / "tree_visualisation.html"

    if not state_file.exists():
        logger.error(f"Tree state JSON file not found at: {state_file}")
        print(f"Error: Could not find tree state file at {state_file}. Please run the Pathfinder search script first.")
        return

    # Load data
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read tree state JSON: {e}")
        return

    nodes = state.get("nodes", {})
    if not nodes:
        logger.error("No nodes found in tree state JSON.")
        return

    # Root node is key "0"
    logger.info("Building tree hierarchy...")
    hierarchy = build_hierarchy(nodes, "0")

    # Build flat list of nodes for tabular view
    flat_nodes_list = []
    for k, v in nodes.items():
        flat_nodes_list.append(v)
    flat_nodes_list.sort(key=lambda x: int(x.get("id", 0)))

    # Generate HTML content
    logger.info("Generating visualization HTML...")
    html_content = generate_html(hierarchy, flat_nodes_list)

    # Save to output file
    output_html.parent.mkdir(parents=True, exist_ok=True)
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"\nInteractive visualizer HTML generated successfully at:\n{output_html}\n")
    logger.info("Opening visualization in browser...")
    webbrowser.open(f"file://{output_html.resolve()}")

if __name__ == "__main__":
    main()
