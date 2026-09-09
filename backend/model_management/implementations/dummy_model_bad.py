import pickle
import random
from typing import Any, Dict, List
from ..interfaces.base_model import IModelBackend

class DummyModelBad(IModelBackend):
    def __init__(self):
        self.weights = []
        # Use unseeded random to prevent pickle from resetting state on every request

    def train(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulates training. Returns dummy metrics.
        """
        epochs = params.get("epochs", 10)
        
        return {
            "loss": 0.5 / epochs,
            "accuracy": min(0.99, 0.4 + (epochs * 0.01))
        }

    def predict(self, input_data: List[Any]) -> float:
        """
        Intentionally produces values outside [0, 1] about 40% of the time.
        """
        if random.random() < 0.40:
            # Produce an invalid prediction
            return random.choice([-1.5, -0.5, 1.5, 2.0])

        # Produce a valid prediction
        return random.uniform(0.0, 1.0)

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "DummyModel",
            "version": "bad-variant",
            "type": "invalid"
        }

    def serialize(self) -> bytes:
        return pickle.dumps(self)
