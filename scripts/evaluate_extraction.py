"""Precisión y exhaustividad de la extracción sobre los CV etiquetados (tests/fixtures/gold.json).

Uso:  python -m scripts.evaluate_extraction
"""
import json

from app.modules.governance.benchmark import extraction_benchmark

if __name__ == "__main__":
    print(json.dumps(extraction_benchmark(), ensure_ascii=False, indent=2))
