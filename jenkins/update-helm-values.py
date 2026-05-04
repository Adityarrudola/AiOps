import sys
import yaml
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python3 update-helm-values.py <tag>")
    sys.exit(1)

tag = sys.argv[1]
root = Path(__file__).resolve().parents[1]
apps = [
    ('charts/backend/values.yaml', 'backend', 'backend'),
    ('charts/frontend/values.yaml', 'frontend', 'frontend'),
    ('charts/aiops/values.yaml', 'aiops', 'aiops'),
    ('charts/load-generator/values.yaml', 'load-generator', 'load-generator'),
]

for path, key, image_name in apps:
    target = root / path
    data = yaml.safe_load(target.read_text())
    data['image']['repository'] = f'localhost:5000/{image_name}'
    data['image']['tag'] = tag
    target.write_text(yaml.safe_dump(data, sort_keys=False))
    print(f'Updated {target} -> {data["image"]["repository"]}:{data["image"]["tag"]}')
