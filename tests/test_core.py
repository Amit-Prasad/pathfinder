import unittest
import os
import sys
from pathlib import Path
from typing import Dict, Any, Tuple

# Add workspace to path
WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from pathfinder.tree import SearchTree, NodeState
from pathfinder.base_sandbox import BaseSandbox
from pathfinder.base_generator import BaseGenerator
from pathfinder.base_researcher import BaseResearcher
from pathfinder.visualise.visualise import build_hierarchy


# Mock concrete implementations of Abstract Base Classes to verify structure
class MockSandbox(BaseSandbox):
    def backup_strategy(self) -> None:
        pass

    def restore_strategy(self) -> None:
        pass

    def evaluate_candidate(self, code: str, worker_id: int) -> Tuple[bool, float, Dict[str, Any], str]:
        return True, 0.95, {"accuracy": 0.95}, ""



class MockGenerator(BaseGenerator):
    def generate_ideas(
        self,
        problem_description: str,
        design_history: list,
        current_code: str,
        research_context: str,
        num_ideas: int,
        provider: str,
        model: str,
        use_vertex: bool,
        is_dag: bool,
    ) -> list:
        return [{"description": "test idea"}]

    def generate_code(
        self,
        problem_description: str,
        design_history: list,
        selected_idea: str,
        research_context: str,
        parent_code: str,
        provider: str,
        model: str,
        use_vertex: bool,
        is_dag: bool,
    ) -> Tuple[str, str]:
        return "def test(): pass", "raw response"


class MockResearcher(BaseResearcher):
    def decide_and_run_research(
        self,
        problem_description: str,
        design_history: list,
        current_code: str,
    ) -> str:
        return "mock paper details"


class TestPathfinderCore(unittest.TestCase):
    def test_abc_implementations(self):
        """Verify that abstract base classes can be correctly subclassed and instantiated."""
        sandbox = MockSandbox()
        generator = MockGenerator()
        researcher = MockResearcher()

        success, score, metrics, err = sandbox.evaluate_candidate("code", 0)
        self.assertTrue(success)
        self.assertEqual(score, 0.95)
        self.assertEqual(metrics["accuracy"], 0.95)

        ideas = generator.generate_ideas("desc", [], "code", "context", 1, "provider", "model", False, False)
        self.assertEqual(len(ideas), 1)
        self.assertEqual(ideas[0]["description"], "test idea")
        
        code, raw_resp = generator.generate_code("desc", [], "idea", "context", "parent", "provider", "model", False, False)
        self.assertEqual(code, "def test(): pass")
        self.assertEqual(raw_resp, "raw response")

        research = researcher.decide_and_run_research("desc", [], "code")
        self.assertEqual(research, "mock paper details")

    def test_backpropagation_logic(self):
        """Test that scores and visit metrics propagate correctly up the tree."""
        tree = SearchTree(c_puct=1.4)
        
        # Root (Node 0) -> Child (Node 1) -> Leaf (Node 2)
        n0 = tree.create_node(parent_id=None, program_code="root", idea_description="Root")
        n1 = tree.create_node(parent_id=0, program_code="child", idea_description="Child")
        n2 = tree.create_node(parent_id=1, program_code="leaf", idea_description="Leaf")

        # Backpropagate a score of 0.8 from leaf
        tree.backpropagate(2, 0.8)

        # Assert Root (0), Child (1), and Leaf (2) visits and scores
        for nid in [0, 1, 2]:
            node = tree.get_node(nid)
            self.assertEqual(node.visits, 1)
            self.assertEqual(node.cumulative_score, 0.8)
            self.assertEqual(node.max_score, 0.8)

        # Backpropagate a lower score of 0.5 from child
        tree.backpropagate(1, 0.5)

        # Verify max_score remains 0.8 but cumulative_score/visits are updated
        root = tree.get_node(0)
        child = tree.get_node(1)
        self.assertEqual(root.visits, 2)
        self.assertEqual(root.cumulative_score, 1.3)
        self.assertEqual(root.max_score, 0.8)

        self.assertEqual(child.visits, 2)
        self.assertEqual(child.cumulative_score, 1.3)
        self.assertEqual(child.max_score, 0.8)

    def test_dag_multi_parent_registration(self):
        """Test that DAG nodes record multiple parents and backpropagate correctly."""
        tree = SearchTree(c_puct=1.4)
        
        # Create parent nodes
        n0 = tree.create_node(parent_id=None, program_code="root", idea_description="Root")
        n1 = tree.create_node(parent_id=0, program_code="p1", idea_description="Parent 1")
        n2 = tree.create_node(parent_id=0, program_code="p2", idea_description="Parent 2")

        # Create a child node with multiple DAG parents (Nodes 1 and 2)
        # Note: In standard tree layout, parent_id is set to the primary parent (Node 1)
        child = tree.create_node(
            parent_id=1,
            program_code="crossover",
            idea_description="Crossover Node",
            dag_parent_ids=[1, 2]
        )

        self.assertEqual(child.parent_id, 1)
        self.assertEqual(child.dag_parent_ids, [1, 2])

        # Backpropagate score from the DAG node
        # In our implementation, standard backpropagate traverses parent_id.
        # We verify that standard parent path backpropagation runs correctly.
        tree.backpropagate(child.id, 0.9)
        self.assertEqual(tree.get_node(1).cumulative_score, 0.9)
        self.assertEqual(tree.get_node(0).cumulative_score, 0.9)

    def test_visualiser_hierarchy_builder(self):
        """Test that the D3 visualizer hierarchy parser constructs clean nested trees."""
        nodes = {
            "0": {
                "id": 0,
                "parent_id": None,
                "children_ids": [1, 2],
                "visits": 10,
                "raw_score": 0.5,
                "cumulative_score": 5.0,
                "max_score": 0.7,
                "prior_prob": 0.5,
                "idea_description": "Root Node Idea",
                "metrics": {"accuracy": 0.8},
                "research_context": "grounding text"
            },
            "1": {
                "id": 1,
                "parent_id": 0,
                "children_ids": [],
                "visits": 5,
                "raw_score": 0.7,
                "cumulative_score": 3.5,
                "max_score": 0.7,
                "prior_prob": 0.3,
                "idea_description": "Child 1 Idea",
                "metrics": {"accuracy": 0.9},
                "research_context": ""
            },
            "2": {
                "id": 2,
                "parent_id": 0,
                "children_ids": [],
                "visits": 5,
                "raw_score": 0.3,
                "cumulative_score": 1.5,
                "max_score": 0.3,
                "prior_prob": 0.2,
                "idea_description": "Child 2 Idea",
                "metrics": {"accuracy": 0.6},
                "research_context": ""
            }
        }

        # Build hierarchy starting from root ID 0
        hierarchy = build_hierarchy(nodes, "0")

        self.assertEqual(hierarchy["id"], 0)
        self.assertEqual(hierarchy["name"], "Root Node Idea")
        self.assertEqual(hierarchy["score"], 0.5)
        self.assertEqual(hierarchy["metrics"]["accuracy"], 0.8)
        self.assertEqual(len(hierarchy["children"]), 2)

        # Check child node fields
        child1 = hierarchy["children"][0]
        self.assertEqual(child1["id"], 1)
        self.assertEqual(child1["name"], "Child 1 Idea")
        self.assertEqual(child1["score"], 0.7)


if __name__ == "__main__":
    unittest.main()
