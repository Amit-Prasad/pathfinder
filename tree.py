import json
import math
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class NodeState(BaseModel):
    id: int
    parent_id: Optional[int]
    children_ids: List[int]
    visits: int
    raw_score: float
    cumulative_score: float
    max_score: float
    prior_prob: float
    program_code: str
    idea_description: str
    metrics: Dict[str, Any]
    research_context: str
    is_expanded: bool
    model_used: Optional[str] = None
    raw_response: Optional[str] = None
    dag_parent_ids: Optional[List[int]] = None

class SearchTree:
    def __init__(self, c_puct: float = 1.4, search_mode: str = "puct"):
        self.nodes: Dict[int, NodeState] = {}
        self.c_puct = c_puct
        self.search_mode = search_mode.lower()
        self.next_id = 0
        self.metadata: Dict[str, Any] = {}

    @property
    def test_strategy(self) -> str:
        return self.metadata.get("test_strategy", "fixed")

    @test_strategy.setter
    def test_strategy(self, val: str):
        self.metadata["test_strategy"] = val

    @property
    def scenarios(self) -> Dict[str, Any]:
        return self.metadata.get("scenarios", {})

    @scenarios.setter
    def scenarios(self, val: Dict[str, Any]):
        self.metadata["scenarios"] = val

    def create_node(
        self,
        parent_id: Optional[int],
        program_code: str,
        idea_description: str,
        prior_prob: float = 0.5,
        research_context: str = "",
        model_used: Optional[str] = None,
        raw_response: Optional[str] = None,
        dag_parent_ids: Optional[List[int]] = None,
    ) -> NodeState:
        node_id = self.next_id
        self.next_id += 1

        node = NodeState(
            id=node_id,
            parent_id=parent_id,
            children_ids=[],
            visits=0,
            raw_score=0.0,
            cumulative_score=0.0,
            max_score=-999999.0,
            prior_prob=prior_prob,
            program_code=program_code,
            idea_description=idea_description,
            metrics={},
            research_context=research_context,
            is_expanded=False,
            model_used=model_used,
            raw_response=raw_response,
            dag_parent_ids=dag_parent_ids,
        )
        self.nodes[node_id] = node

        if parent_id is not None and parent_id in self.nodes:
            self.nodes[parent_id].children_ids.append(node_id)

        return node

    def get_node(self, node_id: int) -> Optional[NodeState]:
        return self.nodes.get(node_id)

    def get_best_node(self) -> NodeState:
        """Returns the node with the highest raw evaluation score in the tree."""
        if not self.nodes:
            raise ValueError("Tree is empty")
        return max(self.nodes.values(), key=lambda n: n.raw_score)

    def backpropagate(self, node_id: int, score: float):
        """Backpropagates the evaluation score from a node up to the root."""
        curr_id = node_id
        while curr_id is not None:
            node = self.nodes[curr_id]
            node.visits += 1
            node.cumulative_score += score
            if score > node.max_score:
                node.max_score = score
            curr_id = node.parent_id

    def _select_leaf_mcts(self) -> int:
        """
        Classic MCTS Root-to-Leaf Traversal:
        Starts at the root node (id=0) and recursively descends the tree by selecting 
        the child with the highest UCT score until a leaf node (with no children) is reached.
        """
        if not self.nodes:
            return 0
            
        curr_id = 0
        while curr_id in self.nodes:
            curr_node = self.nodes[curr_id]
            if not curr_node.children_ids:
                # Reached a leaf node
                return curr_id
                
            children = [self.nodes[cid] for cid in curr_node.children_ids if cid in self.nodes]
            if not children:
                return curr_id
                
            sorted_children = sorted(children, key=lambda n: n.max_score)
            num_children = len(children)
            ranks = {n.id: idx for idx, n in enumerate(sorted_children)}
            
            parent_visits = curr_node.visits
            log_p_visits = math.log(parent_visits) if parent_visits > 0 else 0.0
            
            best_uct = -float("inf")
            best_child_id = children[0].id
            
            for child in children:
                q = ranks[child.id] / (num_children - 1) if num_children > 1 else 0.0
                u = self.c_puct * math.sqrt(max(0.0, log_p_visits) / (1 + child.visits))
                uct_score = q + u
                
                if uct_score > best_uct:
                    best_uct = uct_score
                    best_child_id = child.id
                    
            curr_id = best_child_id
            
        return curr_id

    def select(self) -> int:
        """
        Calculates the score and returns the node ID to expand.
        In 'mcts' mode, performs classic Root-to-Leaf traversal to strictly select leaf nodes.
        In 'puct' mode, calculates PUCT score globally across all tree nodes.
        """
        if not self.nodes:
            return 0
            
        if self.search_mode == "mcts":
            return self._select_leaf_mcts()
            
        # PUCT Global Selection across all nodes
        sorted_nodes = sorted(self.nodes.values(), key=lambda n: n.max_score)
        num_nodes = len(self.nodes)
        ranks = {n.id: idx for idx, n in enumerate(sorted_nodes)}

        total_visits = sum(n.visits for n in self.nodes.values())

        best_score = -float("inf")
        best_node_id = 0

        for node in self.nodes.values():
            if num_nodes > 1:
                q = ranks[node.id] / (num_nodes - 1)
            else:
                q = 0.0
            
            node.prior_prob = 1 / num_nodes
            u = self.c_puct * node.prior_prob * (math.sqrt(total_visits) / (1 + node.visits))
            score = q + u

            if score > best_score:
                best_score = score
                best_node_id = node.id

        return best_node_id

    def select_multiple(self, num_nodes: int) -> List[int]:
        """
        Calculates score and returns top node IDs for parallel expansion.
        In 'mcts' mode, performs classic Root-to-Leaf traversal strictly returning leaf nodes.
        In 'puct' mode, calculates PUCT score globally across all tree nodes.
        """
        if not self.nodes:
            return [0]
            
        if self.search_mode == "mcts":
            selected_ids = []
            virtual_visits = {}
            for _ in range(num_nodes):
                leaf_id = self._select_leaf_mcts()
                selected_ids.append(leaf_id)
                # Virtual visit to diversify multi-worker selection
                leaf_node = self.nodes[leaf_id]
                leaf_node.visits += 1
                virtual_visits[leaf_id] = virtual_visits.get(leaf_id, 0) + 1
                
            for lid, count in virtual_visits.items():
                self.nodes[lid].visits -= count
                
            return selected_ids
            
        # PUCT Global Selection across all nodes
        sorted_nodes = sorted(self.nodes.values(), key=lambda n: n.max_score)
        num_nodes_total = len(self.nodes)
        ranks = {n.id: idx for idx, n in enumerate(sorted_nodes)}

        total_visits = sum(n.visits for n in self.nodes.values())

        candidate_scores = []

        for node in self.nodes.values():
            if num_nodes_total > 1:
                q = ranks[node.id] / (num_nodes_total - 1)
            else:
                q = 0.0
            
            node.prior_prob = 1 / num_nodes_total
            u = self.c_puct * node.prior_prob * (math.sqrt(total_visits) / (1 + node.visits))
            score = q + u
            candidate_scores.append((node.id, score))

        candidate_scores.sort(key=lambda x: x[1], reverse=True)
        selected_ids = [cid for cid, score in candidate_scores[:num_nodes]]
        return selected_ids

    def save_state(self, file_path: str):
        """Serializes the tree state to a JSON file."""
        state = {
            "next_id": self.next_id,
            "c_puct": self.c_puct,
            "search_mode": self.search_mode,
            "metadata": self.metadata,
            "nodes": {str(k): v.model_dump() for k, v in self.nodes.items()},
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def load_state(self, file_path: str):
        """Deserializes the tree state from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        
        self.next_id = state["next_id"]
        self.c_puct = state["c_puct"]
        self.search_mode = state.get("search_mode", state.get("algorithm", "puct"))
        
        # Load legacy fields into metadata for compatibility
        self.metadata = state.get("metadata", {})
        if "test_strategy" in state:
            self.metadata["test_strategy"] = state["test_strategy"]
        if "scenarios" in state:
            self.metadata["scenarios"] = state["scenarios"]

        self.nodes = {int(k): NodeState(**v) for k, v in state["nodes"].items()}
