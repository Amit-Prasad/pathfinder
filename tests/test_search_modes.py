import unittest
import math
import os
import sys
from pathlib import Path

# Add workspace to path
WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from pathfinder.tree import SearchTree

class TestSearchModes(unittest.TestCase):
    def test_mcts_strictly_selects_leaf_nodes(self):
        tree = SearchTree(c_puct=1.4, search_mode="mcts")
        # Build tree structure:
        # Node 0 (Root) -> Node 1, Node 2
        # Node 1 -> Node 3, Node 4
        # Leaves are Node 2, Node 3, Node 4
        n0 = tree.create_node(parent_id=None, program_code="", idea_description="Root")
        n1 = tree.create_node(parent_id=0, program_code="", idea_description="Node 1")
        n2 = tree.create_node(parent_id=0, program_code="", idea_description="Node 2 (Leaf)")
        n3 = tree.create_node(parent_id=1, program_code="", idea_description="Node 3 (Leaf)")
        n4 = tree.create_node(parent_id=1, program_code="", idea_description="Node 4 (Leaf)")

        n0.visits, n0.max_score = 10, 10.0
        n1.visits, n1.max_score = 6, 12.0
        n2.visits, n2.max_score = 4, 8.0
        n3.visits, n3.max_score = 3, 15.0
        n4.visits, n4.max_score = 3, 11.0

        # MCTS selection must land strictly on a leaf (Nodes 2, 3, or 4), NEVER internal nodes (0 or 1)
        selected_id = tree.select()
        self.assertIn(selected_id, [2, 3, 4])
        selected_node = tree.get_node(selected_id)
        self.assertEqual(len(selected_node.children_ids), 0)

        # Multi-worker selection must also land strictly on leaf nodes
        selected_ids = tree.select_multiple(num_nodes=2)
        for sid in selected_ids:
            snode = tree.get_node(sid)
            self.assertEqual(len(snode.children_ids), 0)

    def test_puct_vs_mcts_selection(self):
        tree_puct = SearchTree(c_puct=1.4, search_mode="puct")
        n0 = tree_puct.create_node(parent_id=None, program_code="", idea_description="Root")
        n1 = tree_puct.create_node(parent_id=0, program_code="", idea_description="Child 1")
        
        n0.max_score, n0.visits = 10.0, 5
        n1.max_score, n1.visits = 15.0, 2
        
        sel_puct = tree_puct.select()
        self.assertIn(sel_puct, [0, 1])

    def test_save_load_state_search_mode(self):
        tree = SearchTree(c_puct=1.4, search_mode="mcts")
        tree.create_node(parent_id=None, program_code="", idea_description="Root")
        tmp_path = "/tmp/test_tree_state.json"
        try:
            tree.save_state(tmp_path)
            loaded_tree = SearchTree()
            loaded_tree.load_state(tmp_path)
            self.assertEqual(loaded_tree.search_mode, "mcts")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == "__main__":
    unittest.main()
