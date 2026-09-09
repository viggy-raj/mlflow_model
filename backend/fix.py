import re

def fix_file(filename):
    with open(filename, 'r') as f:
        c = f.read()
    
    # regex to remove the first duplicated kwargs block
    c = re.sub(r'\s*active_model_name=\"[^\"]+\",\s*canary_model_name=\"[^\"]+\",\s*active_model_name=', '\n            active_model_name=', c)
    
    with open(filename, 'w') as f:
        f.write(c)

fix_file('tests/test_rollout_manager.py')
fix_file('tests/test_lifecycle_manager.py')
