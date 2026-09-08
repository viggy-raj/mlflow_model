from abc import ABC, abstractmethod
from typing import Any, Dict, List

class IModelBackend(ABC):
    @abstractmethod
    def train(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trains the model with the given parameters.
        Returns a dictionary of metrics.
        """
        pass

    @abstractmethod
    def predict(self, input_data: List[Any]) -> float:
        """
        Generates a prediction based on the input data.
        """
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Returns metadata about the model implementation.
        """
        pass

    @abstractmethod
    def serialize(self) -> bytes:
        """
        Serializes the model into a byte string for storage.
        """
        pass
