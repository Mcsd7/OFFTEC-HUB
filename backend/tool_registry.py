"""Allowlisted AI operations. This registry never interprets shell commands."""
import re
from pathlib import Path

from fastapi import HTTPException

TOOLS = {
    "system.snapshot": {
        "name": "Resumo do dispositivo", "description": "Retorna métricas que o Termux consegue ler.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "permission": "read_system", "confirmation_required": False,
    },
    "modules.list": {
        "name": "Listar ferramentas", "description": "Retorna o estado real dos módulos integrados.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "permission": "read_modules", "confirmation_required": False,
    },
    "project.analyze": {
        "name": "Analisar projeto", "description": "Lê a estrutura de um projeto existente via OffTec PortAI.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string", "maxLength": 2048}}, "required": ["path"], "additionalProperties": False},
        "permission": "read_project", "confirmation_required": False,
    },
    "apk.inspect": {
        "name": "Inspecionar APK", "description": "Inspeciona o APK enviado nesta sessão via ReaDroid.",
        "parameters": {"type": "object", "properties": {"upload_id": {"type": "string", "pattern": "^[a-f0-9]{32}$"}}, "required": ["upload_id"], "additionalProperties": False},
        "permission": "read_uploaded_apk", "confirmation_required": False,
    },
    "apk.analyze_manifest": {
        "name": "Analisar Manifest", "description": "Executa análise ReaDroid de Manifest no APK enviado.",
        "parameters": {"type": "object", "properties": {"upload_id": {"type": "string", "pattern": "^[a-f0-9]{32}$"}}, "required": ["upload_id"], "additionalProperties": False},
        "permission": "analyze_uploaded_apk", "confirmation_required": True,
    },
    "security.dns_lookup": {
        "name": "Consultar DNS", "description": "Consulta o resolvedor DNS do dispositivo para um nome de host.",
        "parameters": {"type": "object", "properties": {"hostname": {"type": "string", "maxLength": 253, "pattern": "[A-Za-z0-9.-]+"}}, "required": ["hostname"], "additionalProperties": False},
        "permission": "network_dns_read", "confirmation_required": False,
    },
    "security.network_status": {
        "name": "Ler estado de rede", "description": "Consulta NetScope local quando instalado; pode ser limitado pelo Android.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "permission": "local_network_read", "confirmation_required": False,
    },
    "project.test": {
        "name": "Testar projeto", "description": "Executa testes reconhecidos dentro do projeto selecionado.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string", "maxLength": 2048}}, "required": ["path"], "additionalProperties": False},
        "permission": "execute_project_tests", "confirmation_required": True,
    },
    "project.create": {
        "name": "Criar projeto vazio", "description": "Cria uma nova pasta vazia em ~/Projects.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._ -]{0,79}$"}}, "required": ["name"], "additionalProperties": False},
        "permission": "create_project", "confirmation_required": True,
    },
    "project.edit": {
        "name": "Alterar arquivos de projeto", "description": "Solicita alterações via provedor em arquivos do projeto selecionado; grava somente após confirmação.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string", "maxLength": 2048}, "request": {"type": "string", "maxLength": 8000}}, "required": ["path", "request"], "additionalProperties": False},
        "permission": "write_project", "confirmation_required": True,
    },
}


def describe_tools():
    return [{"id": key, **value} for key, value in TOOLS.items()]


def _validate(tool_id, args):
    if tool_id not in TOOLS:
        raise HTTPException(404, "Operação não registrada.")
    if not isinstance(args, dict):
        raise HTTPException(422, "Os parâmetros devem ser um objeto JSON.")
    schema = TOOLS[tool_id]["parameters"]
    props = schema["properties"]
    if set(args) - set(props):
        raise HTTPException(422, "Parâmetro não permitido para esta operação.")
    if set(schema["required"]) - set(args):
        raise HTTPException(422, "Faltam parâmetros obrigatórios.")
    for key, value in args.items():
        spec = props[key]
        if not isinstance(value, str) or len(value) > spec.get("maxLength", 4096):
            raise HTTPException(422, f"Parâmetro inválido: {key}.")
        if "pattern" in spec and not re.fullmatch(spec["pattern"], value):
            raise HTTPException(422, f"Formato inválido: {key}.")


async def execute(tool_id, args, confirmed=False):
    _validate(tool_id, args)
    spec = TOOLS[tool_id]
    if spec["confirmation_required"] and not confirmed:
        raise HTTPException(409, "Esta operação exige confirmação explícita do usuário.")
    from .services.tasks import run_blocking
    if tool_id == "system.snapshot":
        from .core.system import snapshot
        result = await run_blocking(snapshot)
    elif tool_id == "modules.list":
        from .modules.manager import modules
        result = {"modules": await run_blocking(modules)}
    elif tool_id == "project.analyze":
        from .main import _project_path
        from .modules.manager import load_portai
        path = _project_path(args["path"])
        result = await run_blocking(load_portai().analyze_project, path)
    elif tool_id == "apk.inspect":
        from .config import UPLOAD_DIR
        from .modules.manager import load_readroid
        apk = UPLOAD_DIR / f"{args['upload_id']}.apk"
        if not apk.is_file():
            raise HTTPException(404, "APK enviado não encontrado.")
        result = await run_blocking(load_readroid().inspect_apk, apk)
    elif tool_id == "apk.analyze_manifest":
        from .config import UPLOAD_DIR
        from .modules.manager import load_readroid
        apk = UPLOAD_DIR / f"{args['upload_id']}.apk"
        if not apk.is_file():
            raise HTTPException(404, "APK enviado não encontrado.")
        report = UPLOAD_DIR / "reports" / args["upload_id"]
        report.mkdir(parents=True, exist_ok=True)
        result = await run_blocking(load_readroid().analyze_manifest, apk, report)
    elif tool_id == "security.dns_lookup":
        import socket
        hostname = args["hostname"].rstrip(".")
        if not hostname or ".." in hostname:
            raise HTTPException(422, "Nome de host inválido.")
        records = await run_blocking(socket.getaddrinfo, hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        result = {"hostname": hostname, "addresses": sorted({item[4][0] for item in records})}
    elif tool_id == "security.network_status":
        from .modules.manager import load_netscope
        adapter = load_netscope()
        connections, denied = await run_blocking(adapter.read_connections)
        counters = await run_blocking(adapter.net_bytes)
        result = {"available": True, "connections": connections[:100], "access_restricted": denied,
                  "interface_bytes": {"received": counters[0], "transmitted": counters[1]} if counters else None}
    elif tool_id == "project.test":
        from .main import ai_test
        from .models import ProjectTestRequest
        result = await ai_test(ProjectTestRequest(path=args["path"]))
    elif tool_id == "project.create":
        from .main import create_project
        from .models import ProjectCreate
        result = await run_blocking(create_project, ProjectCreate(name=args["name"]))
    elif tool_id == "project.edit":
        from .main import _project_path
        from . import ai_coding
        if not ai_coding.get_config().get("configured"):
            raise HTTPException(409, "Configure um provedor de IA antes de alterar arquivos.")
        path = _project_path(args["path"])
        result = await run_blocking(ai_coding.build_project, path, args["request"])
    else:
        raise HTTPException(404, "Operação não registrada.")
    return {"tool_id": tool_id, "permission": spec["permission"], "result": result}
