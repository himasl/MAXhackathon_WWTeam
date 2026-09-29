import json
from pathlib import Path

source_dir = Path('./knowledge_base')
output_file = Path('knowledge_base_all.json')

combined_data = []

for file_path in source_dir.rglob('*.json'):
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            combined_data.extend(data)
        except json.JSONDecodeError:
            print(f"Ошибка: Файл {file_path.name} поврежден или имеет неверный формат JSON.")

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(combined_data, f, ensure_ascii=False, indent=4)