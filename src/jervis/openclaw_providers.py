from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OpenClawProvider:
    auth_choice: str
    label: str
    credential_env: str | None = None
    plugin: str | None = None
    interactive: bool = False
    requires_base_url: bool = False
    local: bool = False
    credential_optional: bool = False


# Current documented OpenClaw provider/auth routes. The installer also exposes a
# universal pass-through option so newly added OpenClaw providers remain usable
# without waiting for a Jervis release.
PROVIDERS: tuple[OpenClawProvider, ...] = (
    OpenClawProvider("openai", "ChatGPT / Codex subscription", interactive=True),
    OpenClawProvider("openai-api-key", "OpenAI API key", "OPENAI_API_KEY"),
    OpenClawProvider("apiKey", "Anthropic API key", "ANTHROPIC_API_KEY"),
    OpenClawProvider("gemini-api-key", "Google Gemini API key", "GEMINI_API_KEY"),
    OpenClawProvider("openrouter-api-key", "OpenRouter API key", "OPENROUTER_API_KEY"),
    OpenClawProvider("mistral-api-key", "Mistral API key", "MISTRAL_API_KEY"),
    OpenClawProvider("zai-api-key", "Z.AI API key · auto endpoint", "ZAI_API_KEY"),
    OpenClawProvider("zai-coding-global", "Z.AI Coding Plan · Global", "ZAI_API_KEY"),
    OpenClawProvider("zai-coding-cn", "Z.AI Coding Plan · China", "ZAI_API_KEY"),
    OpenClawProvider("zai-global", "Z.AI general API · Global", "ZAI_API_KEY"),
    OpenClawProvider("zai-cn", "Z.AI general API · China", "ZAI_API_KEY"),
    OpenClawProvider("xai-oauth", "xAI / Grok OAuth", interactive=True),
    OpenClawProvider("github-copilot", "GitHub Copilot token", "COPILOT_GITHUB_TOKEN"),
    OpenClawProvider("ai-gateway-api-key", "Vercel AI Gateway", "AI_GATEWAY_API_KEY"),
    OpenClawProvider(
        "arceeai-api-key",
        "Arcee AI · direct",
        "ARCEEAI_API_KEY",
        "@openclaw/arcee-provider",
    ),
    OpenClawProvider(
        "arceeai-openrouter",
        "Arcee AI · via OpenRouter",
        "OPENROUTER_API_KEY",
        "@openclaw/arcee-provider",
    ),
    OpenClawProvider(
        "cerebras-api-key",
        "Cerebras",
        "CEREBRAS_API_KEY",
        "@openclaw/cerebras-provider",
    ),
    OpenClawProvider("huggingface-api-key", "Hugging Face Inference", "HF_TOKEN"),
    OpenClawProvider("fireworks-api-key", "Fireworks AI", "FIREWORKS_API_KEY"),
    OpenClawProvider("together-api-key", "Together AI", "TOGETHER_API_KEY"),
    OpenClawProvider("deepseek-api-key", "DeepSeek", "DEEPSEEK_API_KEY"),
    OpenClawProvider(
        "groq-api-key",
        "Groq",
        "GROQ_API_KEY",
        "@openclaw/groq-provider",
    ),
    OpenClawProvider(
        "deepinfra-api-key",
        "DeepInfra",
        "DEEPINFRA_API_KEY",
        "@openclaw/deepinfra-provider",
    ),
    OpenClawProvider(
        "cohere-api-key",
        "Cohere",
        "COHERE_API_KEY",
        "@openclaw/cohere-provider",
    ),
    OpenClawProvider("clawrouter-api-key", "ClawRouter", "CLAWROUTER_API_KEY"),
    OpenClawProvider("tokenhub-api-key", "Tencent TokenHub", "TOKENHUB_API_KEY"),
    OpenClawProvider("tokenplan-api-key", "Tencent TokenPlan", "TOKENPLAN_API_KEY"),
    OpenClawProvider("nvidia-api-key", "NVIDIA API", "NVIDIA_API_KEY"),
    OpenClawProvider(
        "featherless-api-key",
        "Featherless AI",
        "FEATHERLESS_API_KEY",
        "@openclaw/featherless-provider",
    ),
    OpenClawProvider(
        "litellm-api-key",
        "LiteLLM Gateway",
        "LITELLM_API_KEY",
        requires_base_url=True,
    ),
    OpenClawProvider(
        "meta-api-key",
        "Meta API",
        "MODEL_API_KEY",
        "@openclaw/meta-provider",
    ),
    OpenClawProvider(
        "qwen-api-key",
        "Qwen · Global",
        "QWEN_API_KEY",
        "@openclaw/qwen-provider",
    ),
    OpenClawProvider(
        "qwen-api-key-cn",
        "Qwen · China",
        "QWEN_API_KEY",
        "@openclaw/qwen-provider",
    ),
    OpenClawProvider(
        "gmi-api-key",
        "GMI Cloud",
        "GMI_API_KEY",
        "@openclaw/gmi-provider",
    ),
    OpenClawProvider(
        "baseten-api-key",
        "Baseten",
        "BASETEN_API_KEY",
        "@openclaw/baseten-provider",
    ),
    OpenClawProvider(
        "kilocode-api-key",
        "Kilo Gateway",
        "KILOCODE_API_KEY",
        "@openclaw/kilocode-provider",
    ),
    OpenClawProvider(
        "moonshot-api-key",
        "Moonshot / Kimi · Global",
        "MOONSHOT_API_KEY",
        "@openclaw/moonshot-provider",
    ),
    OpenClawProvider(
        "moonshot-api-key-cn",
        "Moonshot / Kimi · China",
        "MOONSHOT_API_KEY",
        "@openclaw/moonshot-provider",
    ),
    OpenClawProvider("minimax-global-api", "MiniMax API · Global", "MINIMAX_API_KEY"),
    OpenClawProvider("minimax-cn-api", "MiniMax API · China", "MINIMAX_API_KEY"),
    OpenClawProvider("synthetic-api-key", "Synthetic", "SYNTHETIC_API_KEY"),
    OpenClawProvider("runway-api-key", "Runway video API", "RUNWAYML_API_SECRET"),
    OpenClawProvider(
        "alibaba-model-studio-api-key",
        "Alibaba Model Studio",
        "MODELSTUDIO_API_KEY",
    ),
    OpenClawProvider(
        "ollama",
        "Ollama",
        local=True,
        requires_base_url=True,
    ),
    OpenClawProvider(
        "lmstudio",
        "LM Studio",
        "LM_API_TOKEN",
        local=True,
        requires_base_url=True,
        credential_optional=True,
    ),
    OpenClawProvider(
        "vllm",
        "vLLM",
        "VLLM_API_KEY",
        local=True,
        requires_base_url=True,
        credential_optional=True,
    ),
    OpenClawProvider(
        "llama-cpp-existing-server",
        "llama.cpp · existing server",
        "LLAMA_SERVER_API_KEY",
        local=True,
        requires_base_url=True,
        credential_optional=True,
    ),
    OpenClawProvider("llama-cpp", "llama.cpp · managed local runtime", local=True),
)


PROVIDER_BY_AUTH_CHOICE = {provider.auth_choice: provider for provider in PROVIDERS}


def provider(auth_choice: str) -> OpenClawProvider | None:
    return PROVIDER_BY_AUTH_CHOICE.get(auth_choice)


def select_options() -> list[tuple[str, str]]:
    options = [(item.label, item.auth_choice) for item in PROVIDERS]
    options += [
        ("Custom OpenAI / Responses / Anthropic-compatible API", "custom-api-key"),
        ("Any OpenClaw provider · advanced pass-through", "universal-provider"),
        ("Configure OpenClaw later", "later"),
    ]
    return options
