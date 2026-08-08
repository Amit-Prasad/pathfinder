from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional

class BaseGenerator(ABC):
    @abstractmethod
    def generate_ideas(
        self,
        problem_description: str,
        design_history: List[Dict[str, Any]],
        current_code: str,
        research_context: str,
        num_ideas: int,
        provider: str,
        model: str,
        use_vertex: bool,
        is_dag: bool,
    ) -> List[Dict[str, Any]]:
        """
        Generates K optimization ideas to expand the current node.
        """
        pass

    @abstractmethod
    def generate_code(
        self,
        problem_description: str,
        design_history: List[Dict[str, Any]],
        selected_idea: str,
        research_context: str,
        parent_code: str,
        provider: str,
        model: str,
        use_vertex: bool,
        is_dag: bool,
    ) -> Tuple[str, str]:
        """
        Writes the complete strategy/code implementing the selected idea.
        Returns:
            (extracted_code, raw_response)
        """
        pass
