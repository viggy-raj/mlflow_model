import pickle
import random
from typing import Any, Dict, List
from ..interfaces.base_model import IModelBackend

class DummyModelBad(IModelBackend):
    def __init__(self):
        self.weights = []
        # Seeded random so the failure rate is deterministic for tests
        self._rng = random.Random(42)

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
        if self._rng.random() < 0.40:
            # Produce an invalid prediction
            return self._rng.choice([-1.5, -0.5, 1.5, 2.0])
        
        # Produce a valid prediction
        return self._rng.uniform(0.0, 1.0)

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "DummyModelBad",
            "version": "2.0-bad",
            "type": "invalid"
        }

    def serialize(self) -> bytes:
        return pickle.dumps(self)
