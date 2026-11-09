from pydantic import BaseModel, Field

class ProjectRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2048)

class ApkOperation(BaseModel):
    upload_id: str = Field(regex=r"^[a-f0-9]{32}$")
    action: str = Field(regex="^(inspect|manifest|jadx|apktool)$")

class ProjectOperation(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
    action: str = Field(regex="^analyze_project$")

class DnsRequest(BaseModel):
    hostname: str = Field(min_length=1, max_length=253, regex=r"^[A-Za-z0-9.-]+$")

class TranslationPreview(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
    source_language: str = Field(default="en", min_length=2, max_length=12)
    targets: list[str] = Field(default_factory=lambda: ["pt-BR"])

class TranslationApply(BaseModel):
    session_id: str = Field(regex=r"^[a-f0-9]{32}$")
    selected_entries: list[str] = Field(max_items=1000)
    targets: list[str] = Field(min_items=1, max_items=5)
    output_dir: str | None = Field(default=None, min_length=1, max_length=2048)

class PackageInstall(BaseModel):
    packages: list[str] = Field(min_items=1, max_items=10)

class AiProviderConfig(BaseModel):
    provider: str = Field(regex="^(gemini|groq|openai|openrouter|compatible)$")
    model: str = Field(min_length=1, max_length=160)
    api_key: str = Field(min_length=1, max_length=512)
    base_url: str = Field(default="", max_length=500)

class AiProviderUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    provider: str = Field(regex="^(gemini|groq|openai|openrouter|compatible)$")
    model: str = Field(min_length=1, max_length=160)
    api_key: str = Field(default="", max_length=512)
    base_url: str = Field(default="", max_length=500)

class AiProviderTest(BaseModel):
    provider_id: str | None = Field(default=None, regex=r"^[a-f0-9]{32}$")
    provider: str | None = Field(default=None, regex="^(gemini|groq|openai|openrouter|compatible)$")
    model: str | None = Field(default=None, max_length=160)
    api_key: str | None = Field(default=None, max_length=512)
    base_url: str = Field(default="", max_length=500)

class AiProviderModelsRequest(BaseModel):
    provider: str = Field(regex="^(gemini|groq|openai|openrouter|compatible)$")
    api_key: str = Field(min_length=1, max_length=512)
    base_url: str = Field(default="", max_length=500)

class ToolExecution(BaseModel):
    tool_id: str = Field(min_length=1, max_length=80)
    arguments: dict = Field(default_factory=dict)
    confirmed: bool = False

class ApkRebuildPlan(BaseModel):
    operation_id: int = Field(gt=0)
    request: str = Field(min_length=1, max_length=8000)

class ApkRebuildApply(BaseModel):
    plan_id: str = Field(regex=r"^[a-f0-9]{32}$")
    request: str = Field(min_length=1, max_length=8000)
    confirmed: bool = False
    allow_build: bool = False

class ConversationCreate(BaseModel):
    title: str = Field(default="Nova conversa", min_length=1, max_length=100)

class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=100)

class ChatMessageRequest(BaseModel):
    conversation_id: str | None = Field(default=None, regex=r"^[a-f0-9]{32}$")
    message: str = Field(min_length=1, max_length=12000)

class ToolApproval(BaseModel):
    message_id: str = Field(regex=r"^[a-f0-9]{32}$")
    confirmed: bool = False

class ConversationDelete(BaseModel):
    confirmed: bool = False

class CodexRunRequest(BaseModel):
    path: str | None = Field(default=None, min_length=1, max_length=2048)
    prompt: str = Field(min_length=1, max_length=12000)
    confirmed: bool = False
    method: str = Field(default="auto", regex=r"^(auto|main|fallback)$")

class CodexConversationCreate(BaseModel):
    title: str = Field(default="Nova conversa Codex", min_length=1, max_length=100)
    path: str | None = Field(default=None, min_length=1, max_length=2048)
    method: str = Field(default="auto", regex=r"^(auto|main|fallback)$")

class CodexChatMessage(BaseModel):
    conversation_id: str = Field(regex=r"^[a-f0-9]{32}$")
    message: str = Field(min_length=1, max_length=12000)
    confirmed: bool = False
    retry: bool = False
    method: str | None = Field(default=None, regex=r"^(auto|main|fallback)$")

class CodexApplyRequest(BaseModel):
    confirmed: bool = False

class AiProgramRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
    prompt: str = Field(min_length=1, max_length=12000)
    confirmed: bool = False

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80, regex=r"^[A-Za-z0-9][A-Za-z0-9._ -]*$")

class ProjectTestRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
    confirmed: bool = False
