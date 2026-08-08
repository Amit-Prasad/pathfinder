from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseResearcher(ABC):
    @abstractmethod
    def decide_and_run_research(
        self,
        problem_description: str,
        design_history: List[Dict[str, Any]],
        current_code: str,
    ) -> str:
        """
        Decides if research is needed, runs the research search queries,
        and returns a synthesized research summary.
        """
        pass
