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
    output_dir: str = Field(min_length=1, max_length=2048)

class PackageInstall(BaseModel):
    packages: list[str] = Field(min_items=1, max_items=10)

class AiProviderConfig(BaseModel):
    provider: str = Field(regex="^(gemini|groq|openai|compatible)$")
    model: str = Field(min_length=1, max_length=160)
    api_key: str = Field(min_length=1, max_length=512)
    base_url: str = Field(default="", max_length=500)

class AiProgramRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
    prompt: str = Field(min_length=1, max_length=12000)

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80, regex=r"^[A-Za-z0-9][A-Za-z0-9._ -]*$")

class ProjectTestRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
