from model_management.implementations.dummy_model import DummyModel

def test_dummy_model_predict_valid():
    model = DummyModel()
    
    # Empty input
    assert model.predict([]) == 0.5
    
    # Valid avg
    assert model.predict([0.2, 0.8]) == 0.5
    
    # Clamped upper
    assert model.predict([10.0, 20.0]) == 1.0
    
    # Clamped lower
    assert model.predict([-10.0, -20.0]) == 0.0

def test_dummy_model_train():
    model = DummyModel()
    metrics = model.train({"epochs": 5, "learning_rate": 0.1})
    assert "loss" in metrics
    assert "accuracy" in metrics
    assert len(model.weights) == 5
