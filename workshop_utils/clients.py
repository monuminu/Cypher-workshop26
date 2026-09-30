"""Workshop helpers: a single, provider-agnostic way to get a chat client.

The whole workshop is built so that *one* environment variable — ``MODEL_PROVIDER`` —
chooses which model backend every notebook runs against. The notebook bodies never
change: they all call :func:`get_chat_client`, wrap it in an ``Agent``, and run.

This is the heart of "provider-agnostic": every client returned here implements the
same Agent Framework chat-client interface, so the agent code on top is identical
whether you are on Azure AI Foundry, OpenAI, Azure OpenAI, Anthropic, Bedrock,
Ollama, or a Gemini OpenAI-compatible endpoint.

Usage (in every notebook)::

    from workshop_utils import get_chat_client
    from agent_framework import Agent

    client = get_chat_client()
    agent = Agent(client=client, name="HelloAgent", instructions="You are helpful.")
    print(await agent.run("Hi!"))

Pick your backend by setting ``MODEL_PROVIDER`` in your ``.env`` (see ``.env.example``)::

    MODEL_PROVIDER=foundry      # default — Azure AI Foundry, run `az login`
    MODEL_PROVIDER=openai       # OpenAI (OPENAI_API_KEY, OPENAI_CHAT_MODEL)
    MODEL_PROVIDER=azure-openai # Azure OpenAI (AZURE_OPENAI_* vars)
    MODEL_PROVIDER=anthropic    # pip install -e ".[anthropic]"
    MODEL_PROVIDER=ollama       # pip install -e ".[ollama]" — local, no key
    MODEL_PROVIDER=bedrock      # pip install -e ".[bedrock]"
    MODEL_PROVIDER=gemini       # Gemini via its OpenAI-compatible endpoint

Behind a TLS-inspecting corporate proxy, set ``SSL_VERIFY=false`` to stop
certificate verification from rejecting the proxy's re-signed certificates.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

# Load variables from a local .env if present. Harmless in CI / when absent.
load_dotenv()

__all__ = ["get_chat_client", "current_provider", "SUPPORTED_PROVIDERS"]


def _ssl_verification_disabled() -> bool:
    return os.getenv("SSL_VERIFY", "true").strip().lower() in {"false", "0", "no", "off"}


def _disable_ssl_verification() -> None:
    """Make Python's default TLS contexts accept any certificate.

    Corporate proxies that inspect TLS re-sign every response with their own root
    CA, which Python does not trust, so requests fail with SSLCertVerificationError.
    httpx (and therefore the OpenAI, Anthropic and Ollama clients) builds its
    default context through ``ssl.create_default_context``, so overriding that one
    factory covers every outbound call. This removes certificate authentication
    entirely — only opt in via SSL_VERIFY=false on a network you trust.
    """
    import ssl

    original = ssl.create_default_context

    def unverified(*args: Any, **kwargs: Any) -> ssl.SSLContext:
        context = original(*args, **kwargs)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    ssl.create_default_context = unverified  # type: ignore[assignment]
    ssl._create_default_https_context = unverified  # type: ignore[attr-defined]

    try:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except ModuleNotFoundError:
        pass


if _ssl_verification_disabled():
    _disable_ssl_verification()

SUPPORTED_PROVIDERS = (
    "foundry",
    "openai",
    "azure-openai",
    "anthropic",
    "ollama",
    "bedrock",
    "gemini",
)


def current_provider() -> str:
    """Return the configured provider id (lowercased), defaulting to ``foundry``."""
    return os.getenv("MODEL_PROVIDER", "foundry").strip().lower()


def get_chat_client(**overrides: Any):
    """Return an Agent Framework chat client for the configured ``MODEL_PROVIDER``.

    Each branch constructs the provider's native client. Clients read their own
    settings from environment variables when arguments are omitted, so the only
    thing a participant changes to swap backends is ``MODEL_PROVIDER``.

    Args:
        **overrides: Optional keyword args forwarded to the underlying client
            constructor (e.g. ``model="gpt-4o"``). Useful in a notebook cell to
            try a specific deployment without editing your ``.env``.

    Raises:
        ValueError: if ``MODEL_PROVIDER`` is not one of :data:`SUPPORTED_PROVIDERS`.
        ModuleNotFoundError: if the provider's optional package is not installed
            (with a hint on which extra to install).
    """
    provider = current_provider()

    # --- Azure AI Foundry (default) -------------------------------------------
    # Auth via Azure CLI: run `az login` first. Reads FOUNDRY_PROJECT_ENDPOINT
    # and FOUNDRY_MODEL from the environment.
    if provider == "foundry":
        try:
            from agent_framework.foundry import FoundryChatClient
            from azure.identity import AzureCliCredential
        except ModuleNotFoundError as exc:  # pragma: no cover - install hint
            raise ModuleNotFoundError(
                "Foundry provider needs 'agent-framework-foundry' and 'azure-identity'. "
                "Install with: uv pip install -e '.'"
            ) from exc
        # azure-core transports use requests, which passes its own cert settings
        # to urllib3 and so ignores the ssl module override above.
        if _ssl_verification_disabled():
            overrides.setdefault("connection_verify", False)
        return FoundryChatClient(credential=AzureCliCredential(), **overrides)

    # --- OpenAI ---------------------------------------------------------------
    # Reads OPENAI_API_KEY and OPENAI_CHAT_MODEL (or OPENAI_MODEL).
    if provider == "openai":
        from agent_framework.openai import OpenAIChatClient

        return OpenAIChatClient(**overrides)

    # --- Azure OpenAI ---------------------------------------------------------
    # The same OpenAI client routes to Azure when AZURE_OPENAI_* vars are set
    # (endpoint, api key or AzureCliCredential, api version, deployment name).
    if provider == "azure-openai":
        from agent_framework.openai import OpenAIChatClient

        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        params: dict[str, Any] = {}
        if endpoint:
            params["azure_endpoint"] = endpoint
        if os.getenv("AZURE_OPENAI_API_VERSION"):
            params["api_version"] = os.environ["AZURE_OPENAI_API_VERSION"]
        if os.getenv("AZURE_OPENAI_MODEL"):
            params["model"] = os.environ["AZURE_OPENAI_MODEL"]
        # If no API key is provided, fall back to Azure AD via the CLI credential.
        if not os.getenv("AZURE_OPENAI_API_KEY"):
            from azure.identity import AzureCliCredential

            params["credential"] = AzureCliCredential()
        params.update(overrides)
        return OpenAIChatClient(**params)

    # --- Anthropic ------------------------------------------------------------
    # Reads ANTHROPIC_API_KEY and ANTHROPIC_CHAT_MODEL.
    if provider == "anthropic":
        try:
            from agent_framework.anthropic import AnthropicClient
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "Anthropic provider not installed. Install with: "
                "uv pip install -e '.[anthropic]'"
            ) from exc
        return AnthropicClient(**overrides)

    # --- Ollama (local, no API key) -------------------------------------------
    # Reads OLLAMA_HOST and OLLAMA_MODEL. Great for offline / no-cloud labs.
    if provider == "ollama":
        try:
            from agent_framework.ollama import OllamaChatClient
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "Ollama provider not installed. Install with: "
                "uv pip install -e '.[ollama]'"
            ) from exc
        return OllamaChatClient(**overrides)

    # --- AWS Bedrock ----------------------------------------------------------
    # Reads BEDROCK_REGION, BEDROCK_CHAT_MODEL and standard AWS_* credentials.
    if provider == "bedrock":
        try:
            from agent_framework.bedrock import BedrockChatClient
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "Bedrock provider not installed. Install with: "
                "uv pip install -e '.[bedrock]'"
            ) from exc
        return BedrockChatClient(**overrides)

    # --- Google Gemini (via OpenAI-compatible endpoint) -----------------------
    # Agent Framework has no first-class Gemini client. Gemini exposes an
    # OpenAI-compatible API, so we point the OpenAI client at it. Set:
    #   GEMINI_API_KEY, GEMINI_MODEL (e.g. gemini-2.0-flash),
    #   GEMINI_BASE_URL (default below).
    if provider == "gemini":
        from agent_framework.openai import OpenAIChatClient

        base_url = os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        params = {
            "base_url": base_url,
            "api_key": os.getenv("GEMINI_API_KEY", ""),
            "model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        }
        params.update(overrides)
        return OpenAIChatClient(**params)

    raise ValueError(
        f"Unknown MODEL_PROVIDER={provider!r}. "
        f"Supported: {', '.join(SUPPORTED_PROVIDERS)}."
    )
