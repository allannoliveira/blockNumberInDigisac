# tests/conftest.py
import sys
from pathlib import Path
import importlib.util

# garante que a raiz do projeto esteja no sys.path
ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

# registra o seu arquivo blocknumber.py como módulo 'digisac' (para compatibilidade com os testes existentes)
module_name = "digisac"
if module_name not in sys.modules:
    candidate = ROOT / "blocknumber.py"
    if candidate.exists():
        spec = importlib.util.spec_from_file_location(module_name, str(candidate))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[module_name] = module
