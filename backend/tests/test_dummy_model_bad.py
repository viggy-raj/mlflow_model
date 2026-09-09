from model_management.implementations.dummy_model_bad import DummyModelBad
from model_management.services.rollout_manager import _is_valid_prediction

def test_dummy_model_bad_produces_errors():
    model = DummyModelBad()
    
    invalid_count = 0
    total = 100
    
    for _ in range(total):
        res = model.predict([1.0, 2.0])
        if not _is_valid_prediction(res):
            invalid_count += 1
            
    # Should be around 40
    assert 30 <= invalid_count <= 55
