import pickle
from typing import Any, Dict, List
from ..interfaces.base_model import IModelBackend

class DummyModel(IModelBackend):
    def __init__(self):
        self.weights = []

    def train(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulates training. Just uses the first parameter value to create some weights.
        Returns dummy metrics.
        """
        epochs = params.get("epochs", 10)
        learning_rate = params.get("learning_rate", 0.01)
        
        self.weights = [learning_rate * i for i in range(5)]
        
        return {
            "loss": 0.1 / epochs,
            "accuracy": min(0.99, 0.5 + (epochs * 0.01))
        }

    def predict(self, input_data: List[Any]) -> float:
        """
        Calculates a weighted sum of the input and normalizes it to [0, 1].
        """
        if not input_data:
            return 0.5
            
        try:
            val = sum(float(x) for x in input_data) / len(input_data)
            # Ensure it's in [0, 1] for valid prediction
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.5

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "DummyModel",
            "version": "1.0",
            "type": "valid"
        }

    def serialize(self) -> bytes:
        return pickle.dumps(self)
