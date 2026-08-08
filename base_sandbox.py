from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional

class BaseSandbox(ABC):
    @abstractmethod
    def backup_strategy(self) -> None:
        """Backs up the current strategy/code file."""
        pass

    @abstractmethod
    def restore_strategy(self) -> None:
        """Restores the strategy/code file from backup."""
        pass

    @abstractmethod
    def evaluate_candidate(
        self,
        code: str,
        worker_id: int,
    ) -> Tuple[bool, float, Dict[str, Any], str]:
        """
        Evaluates a candidate code.
        Returns:
            (success, score, metrics_dict, error_message)
        """
        pass
