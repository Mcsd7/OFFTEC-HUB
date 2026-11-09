import importlib.util
import shutil
from pathlib import Path
from ..config import READROID_PATH, PORTAI_PATH
from ..ai_coding import get_config as ai_config
NETSCOPE_PATH = Path.home() / "ferramentas" / "Netscop" / "netscope.py"


def _tool(name):
    return shutil.which(name) is not None


def modules():
    readroid = (READROID_PATH / "readroid" / "analyzer.py").is_file()
    portai = (PORTAI_PATH / "portai.py").is_file()
    ai_ready = ai_config().get("configured", False)
    return [
        {"id": "apk_lab", "name": "APK Lab · ReaDroid", "version": "local checkout", "installed": readroid, "state": "ready" if readroid else "unavailable", "description": "Inspeção estática e análise do Manifest; JADX e Apktool dependem dos binários locais.", "actions": ["inspect", "manifest", "jadx", "apktool"] if readroid else []},
        {"id": "dev_studio", "name": "Dev Studio · PortAI", "version": "local checkout", "installed": portai, "state": "ready" if portai else "unavailable", "description": "Análise heurística de projetos e tradução revisável do PortAI.", "actions": ["analyze_project", "translate"] if portai else []},
        {"id": "ai_center", "name": "Programar com IA", "version": "1.0", "installed": ai_ready, "state": "ready" if ai_ready else "not_configured", "description": "Programação assistida com Gemini, Groq e APIs compatíveis; grava alterações somente no projeto selecionado.", "actions": ["configure", "program", "test"]},
        {"id": "terminal", "name": "Terminal Center", "version": "Termux", "installed": Path("/data/data/com.termux/files/usr").exists(), "state": "ready" if Path("/data/data/com.termux/files/usr").exists() else "unavailable", "description": "Inventário de pacotes; nenhuma execução de shell arbitrária é exposta.", "actions": ["packages"]},
        {"id": "netscope", "name": "Security Lab · NetScope", "version": "1.0", "installed": NETSCOPE_PATH.is_file(), "state": "available_read_only" if NETSCOPE_PATH.is_file() else "unavailable", "description": "NetScope monitora conexões locais; Android pode bloquear /proc/net.", "actions": ["network_status"] if NETSCOPE_PATH.is_file() else []},
        {"id": "sysguard", "name": "Sysguard-ASM", "version": "source unavailable", "installed": False, "state": "unavailable", "description": "Há somente um binário ARM64 no ambiente de desenvolvimento; integração desabilitada.", "actions": []},
    ]


def load_readroid():
    if not (READROID_PATH / "readroid" / "analyzer.py").is_file():
        raise RuntimeError("ReaDroid não encontrado. Configure OFFTEC_READROID_PATH para um checkout válido.")
    import sys
    sys.path.insert(0, str(READROID_PATH))
    from readroid import analyzer
    return analyzer


def load_portai():
    if not (PORTAI_PATH / "portai.py").is_file():
        raise RuntimeError("PortAI não encontrado. Configure OFFTEC_PORTAI_PATH para um checkout válido.")
    spec = importlib.util.spec_from_file_location("offtec_portai_adapter", PORTAI_PATH / "portai.py")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.path.insert(0, str(PORTAI_PATH))
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_netscope():
    if not NETSCOPE_PATH.is_file():
        raise RuntimeError("NetScope não encontrado no caminho esperado: ~/ferramentas/Netscop/netscope.py")
    spec = importlib.util.spec_from_file_location("offtec_hub_netscope", NETSCOPE_PATH)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
