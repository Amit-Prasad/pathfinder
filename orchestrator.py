import logging
import shutil
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple, Callable
import json
import random

from pathfinder.tree import SearchTree, NodeState
from pathfinder.base_sandbox import BaseSandbox
from pathfinder.base_generator import BaseGenerator
from pathfinder.base_researcher import BaseResearcher

logger = logging.getLogger("pathfinder.orchestrator")

def get_design_history(tree: SearchTree, node_id: int) -> list:
    """Walks up from node to root and returns the list of steps in chronological order."""
    history = []
    curr_id = node_id
    while curr_id is not None:
        node = tree.get_node(curr_id)
        if node is None:
            break
        history.append({
            "node_id": node.id,
            "idea_description": node.idea_description,
            "score": node.raw_score,
            "metrics": node.metrics,
            "code": node.program_code
        })
        curr_id = node.parent_id
    return list(reversed(history))

def generic_worker_expand_node(
    worker_id: int,
    selected_id: int,
    root_prompt: str,
    design_history: list,
    selected_node_code: str,
    selected_node_research: str,
    current_num_children: int,
    code_provider: str,
    code_model: str,
    ideas_provider: str,
    ideas_model: str,
    use_vertex_for_step: bool,
    sandbox: BaseSandbox,
    generator: BaseGenerator,
    research_agent: BaseResearcher,
    is_dag: bool = False,
    dag_parent_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Worker function to expand a single selected node in parallel.
    """
    logger.info(f"[Worker {worker_id}] Starting expansion of node ID: {selected_id}")

    # 1. Research step (if needed)
    research_context = selected_node_research
    if not research_context:
        logger.info(f"[Worker {worker_id}] Evaluating research needs for node {selected_id}...")
        try:
            research_context = research_agent.decide_and_run_research(
                problem_description=root_prompt,
                design_history=design_history,
                current_code=selected_node_code,
            )
        except Exception as e:
            logger.error(f"[Worker {worker_id}] Research failed: {e}")
            research_context = ""

    # 2. Generate new ideas
    logger.info(f"[Worker {worker_id}] Generating {current_num_children} optimization ideas...")
    try:
        ideas = generator.generate_ideas(
            problem_description=root_prompt,
            design_history=design_history,
            current_code=selected_node_code,
            research_context=research_context,
            num_ideas=current_num_children,
            use_vertex=use_vertex_for_step,
            provider=ideas_provider,
            model=ideas_model,
            is_dag=is_dag,
        )
    except Exception as e:
        logger.error(f"[Worker {worker_id}] Failed to generate ideas: {e}")
        ideas = [
            {
                "idea_description": "Default optimization fallback: Adjust indicators",
                "prior_prob": 0.5,
                "expected_improvement": "Fallback to minor improvements",
            }
        ]

    # 3. Expand node
    expanded_children = []
    
    for idx, idea in enumerate(ideas, 1):
        desc = idea.get("idea_description", f"Optimized idea {idx}")
        prob = idea.get("prior_prob", 0.5)
        logger.info(f"[Worker {worker_id}] Expanding branch {idx}/{len(ideas)}: '{desc}' (prior prob: {prob})")

        # Generate code for this idea
        try:
            candidate_code, raw_response = generator.generate_code(
                problem_description=root_prompt,
                design_history=design_history,
                selected_idea=desc,
                research_context=research_context,
                parent_code=selected_node_code,
                use_vertex=use_vertex_for_step,
                provider=code_provider,
                model=code_model,
                is_dag=is_dag,
            )

            # Evaluate in isolated sandbox
            success, score, metrics, err = sandbox.evaluate_candidate(candidate_code, worker_id)
            if not success:
                logger.warning(f"[Worker {worker_id}] Branch '{desc}' evaluation failed: {err}")
                score = -100.0
                metrics = {}
            else:
                logger.info(f"[Worker {worker_id}] Branch '{desc}' evaluated successfully. Score: {score:.4f} | Metrics: {metrics}")

            expanded_children.append({
                "program_code": candidate_code,
                "raw_response": raw_response,
                "idea_description": desc,
                "prior_prob": prob,
                "raw_score": score,
                "metrics": metrics,
                "model_used": code_model,
                "research_context": research_context,
            })

        except Exception as e:
            logger.error(f"[Worker {worker_id}] Error executing branch '{desc}': {e}")
            expanded_children.append({
                "program_code": selected_node_code,
                "raw_response": str(e),
                "idea_description": f"FAILED: {desc}",
                "prior_prob": prob,
                "raw_score": -100.0,
                "metrics": {},
                "model_used": code_model,
                "research_context": research_context,
            })

    return {
        "selected_id": selected_id,
        "research_context": research_context,
        "children": expanded_children,
        "dag_parent_ids": dag_parent_ids,
    }


class MCTSEngine:
    def __init__(
        self,
        tree: SearchTree,
        sandbox: BaseSandbox,
        generator: BaseGenerator,
        researcher: BaseResearcher,
        root_prompt: str,
        state_file: Path,
        model_selector_fn: Callable[[], Tuple[str, str]],
        use_vertex_ai: bool = False,
    ):
        self.tree = tree
        self.sandbox = sandbox
        self.generator = generator
        self.researcher = researcher
        self.root_prompt = root_prompt
        self.state_file = state_file
        self.model_selector_fn = model_selector_fn
        self.use_vertex_ai = use_vertex_ai

    def run_search(
        self,
        iterations: int,
        workers: int,
        root_children: int,
        children: int,
        enable_dag: bool = False,
        dag_interval: int = 5,
        dag_num_parents: int = 3,
        baseline_code: Optional[str] = None,
    ):
        logger.info(f"Starting tree search for {iterations} iterations...")
        
        # Check if root node already exists (e.g. from resume)
        if not self.tree.nodes:
            if not baseline_code:
                raise ValueError("Baseline code must be provided for a fresh tree search.")
            
            logger.info("Starting fresh search. Setting up root node from baseline...")
            self.sandbox.backup_strategy()
            
            # Create root node
            root_node = self.tree.create_node(
                parent_id=None,
                program_code=baseline_code,
                idea_description="Baseline strategy from workspace",
                prior_prob=1.0,
                model_used="baseline"
            )

            # Evaluate root node
            logger.info("Evaluating baseline strategy for root node...")
            success, score, metrics, err = self.sandbox.evaluate_candidate(baseline_code, worker_id=0)
            if not success:
                logger.error(f"Failed to run baseline evaluation: {err}")
                score = -100.0
                metrics = {}
            else:
                logger.info(f"Baseline Score: {score:.4f} | Metrics: {metrics}")

            root_node.raw_score = score
            root_node.metrics = metrics
            self.tree.backpropagate(root_node.id, score)
            self.tree.save_state(str(self.state_file))

        try:
            for iteration in range(1, iterations + 1):
                logger.info(f"--- Iteration {iteration}/{iterations} ---")
                
                # Check if this iteration should run the DAG option
                is_dag_iteration = False
                if enable_dag:
                    root_node = self.tree.get_node(0)
                    if iteration == 1:
                        if root_node and len(root_node.children_ids) > 1:
                            is_dag_iteration = True
                            logger.info("DAG iteration triggered at Iteration 1 (resume mode with multiple root children).")
                    elif iteration % dag_interval == 0:
                        is_dag_iteration = True
                        logger.info(f"DAG iteration triggered at Iteration {iteration} (interval = {dag_interval}).")

                if is_dag_iteration:
                    selected_ids = []
                    dag_worker_parent_ids = []
                    dag_worker_histories = []
                    dag_worker_parent_lists = []
                    all_node_ids = list(self.tree.nodes.keys())
                    
                    for w_idx in range(workers):
                        t_val = min(dag_num_parents, len(all_node_ids))
                        selected_node_ids = random.sample(all_node_ids, t_val)
                        primary_parent_id = max(selected_node_ids, key=lambda nid: self.tree.get_node(nid).raw_score)
                        
                        dag_worker_parent_ids.append(primary_parent_id)
                        selected_ids.append(primary_parent_id)
                        dag_worker_parent_lists.append(selected_node_ids)
                        
                        unique_ids = set()
                        for nid in selected_node_ids:
                            curr = nid
                            while curr is not None:
                                unique_ids.add(curr)
                                curr = self.tree.get_node(curr).parent_id
                        sorted_ids = sorted(list(unique_ids))
                        
                        dag_history = []
                        for nid in sorted_ids:
                            node = self.tree.get_node(nid)
                            dag_history.append({
                                "node_id": node.id,
                                "idea_description": node.idea_description,
                                "score": node.raw_score,
                                "metrics": node.metrics,
                                "code": node.program_code
                            })
                        dag_worker_histories.append(dag_history)
                        
                    logger.info(f"DAG Iteration: Parent IDs selected per worker: {dag_worker_parent_ids}")
                else:
                    selected_ids = self.tree.select_multiple(workers)
                    logger.info(f"Selected node IDs: {selected_ids} for parallel expansion.")

                futures = []
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    for idx, selected_id in enumerate(selected_ids):
                        selected_node = self.tree.get_node(selected_id)
                        
                        if is_dag_iteration:
                            design_history = dag_worker_histories[idx]
                            current_num_children = 1
                            worker_dag_parents = dag_worker_parent_lists[idx]
                        else:
                            design_history = get_design_history(self.tree, selected_id)
                            current_num_children = root_children if selected_id == 0 else children
                            worker_dag_parents = None
                        
                        if selected_id == 0:
                            code_provider, code_model = "gemini", "gemini-2.5-flash"
                            ideas_provider, ideas_model = "gemini", "gemini-2.5-flash"
                            use_vertex_for_step = True if self.use_vertex_ai else False
                        else:
                            ideas_provider, ideas_model = self.model_selector_fn()
                            code_provider, code_model = self.model_selector_fn()
                            use_vertex_for_step = True if (ideas_provider == "gemini" and self.use_vertex_ai) else False

                        futures.append(
                            executor.submit(
                                generic_worker_expand_node,
                                worker_id=idx,
                                selected_id=selected_id,
                                root_prompt=self.root_prompt,
                                design_history=design_history,
                                selected_node_code=selected_node.program_code,
                                selected_node_research=selected_node.research_context,
                                current_num_children=current_num_children,
                                code_provider=code_provider,
                                code_model=code_model,
                                ideas_provider=ideas_provider,
                                ideas_model=ideas_model,
                                use_vertex_for_step=use_vertex_for_step,
                                sandbox=self.sandbox,
                                generator=self.generator,
                                research_agent=self.researcher,
                                is_dag=is_dag_iteration,
                                dag_parent_ids=worker_dag_parents,
                            )
                        )

                    for future in as_completed(futures):
                        try:
                            res = future.result()
                            node_id = res["selected_id"]
                            research_context = res["research_context"]
                            children_results = res["children"]
                            dag_pids = res.get("dag_parent_ids", None)
                            
                            parent_node = self.tree.get_node(node_id)
                            parent_node.research_context = research_context
                            parent_node.is_expanded = True
                            
                            # Add children to search tree
                            for child_res in children_results:
                                child = self.tree.create_node(
                                    parent_id=node_id,
                                    program_code=child_res["program_code"],
                                    idea_description=child_res["idea_description"],
                                    prior_prob=child_res["prior_prob"],
                                    research_context=child_res["research_context"],
                                    model_used=child_res["model_used"],
                                    raw_response=child_res["raw_response"],
                                    dag_parent_ids=dag_pids,
                                )
                                child.raw_score = child_res["raw_score"]
                                child.metrics = child_res["metrics"]
                                self.tree.backpropagate(child.id, child_res["raw_score"])
                                
                        except Exception as e:
                            logger.error(f"Worker failed with exception: {e}", exc_info=True)

                # Save tree state
                self.tree.save_state(str(self.state_file))
                logger.info(f"Iteration {iteration} complete. Tree state saved to {self.state_file}")

        except KeyboardInterrupt:
            logger.info("Search interrupted by user. Cleaning up and finalizing...")
        except Exception as e:
            logger.error(f"Critical error during tree search: {e}", exc_info=True)
        finally:
            self.sandbox.restore_strategy()
