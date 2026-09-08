from typing import Type
from ..interfaces.base_model import IModelBackend
from ..implementations.dummy_model import DummyModel
from ..implementations.dummy_model_bad import DummyModelBad

class ModelRegistry:
    """Factory for resolving IModelBackend implementations."""

    _registry = {
        'dummy_model': DummyModel,
        'dummy_model_bad': DummyModelBad,
    }

    @classmethod
    def get_model(cls, model_type: str) -> IModelBackend:
        model_class = cls._registry.get(model_type)
        if not model_class:
            raise ValueError(f"Unknown model type: {model_type}")
        return model_class()

    @classmethod
    def list_available_models(cls) -> list:
        return list(cls._registry.keys())
