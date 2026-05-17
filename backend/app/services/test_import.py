
import sys
import os
from pathlib import Path

# Add DeepTutor to sys.path
project_root = Path(__file__).resolve().parent.parent.parent.parent
deeptutor_root = project_root / "apps" / "DeepTutor"
if str(deeptutor_root) not in sys.path:
    sys.path.insert(0, str(deeptutor_root))

try:
    from src.services.rag.service import RAGService
    print("Successfully imported RAGService from DeepTutor")
    service = RAGService()
    print(f"Provider: {service.provider}")
except Exception as e:
    print(f"Failed to import RAGService: {e}")
    import traceback
    traceback.print_exc()
