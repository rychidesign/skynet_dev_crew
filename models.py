"""
Central LLM model registry.

Usage in agents:
    from models import get_llm
    llm = get_llm("architect")

Switching a model = changing one string in AGENT_MODELS.

PROVIDER NOTES:
- Gemini/Anthropic: use direct providers (gemini/, anthropic/) because
  Vercel AI Gateway does not handle provider-specific message formatting
  (system message ordering for Gemini, assistant prefill for Anthropic).
- OpenAI/Moonshot: work fine through Vercel AI Gateway.
- OpenCode Go: separate endpoint from Zen! Go = /zen/go/v1, Zen = /zen/v1.
  GLM-5 and Kimi K2.5 use OpenAI-compatible API (/chat/completions).
  MiniMax M2.5 uses Anthropic-compatible API (/messages).
- OpenCode Zen: pay-as-you-go endpoint at /zen/v1.
  Gemini 3 Flash, GPT-5.2-Codex, Claude Haiku 4.5 available here.
"""

import os

from crewai import LLM

# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------

PROVIDERS = {
    # Direct providers — LiteLLM handles message formatting natively
    "google_direct": {
        "api_key_env": "GOOGLE_API_KEY",
        "prefix": "gemini",
    },
    "anthropic_direct": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "prefix": "anthropic",
    },
    # Vercel AI Gateway — works for OpenAI and Moonshot only
    "vercel": {
        "api_key_env": "VERCEL_AI_GATEWAY_API_KEY",
        "prefix": "vercel_ai_gateway",
    },
    # OpenCode Go — $10/mo subscription, OpenAI-compatible models
    # IMPORTANT: endpoint is /zen/go/v1, NOT /zen/v1 (that's Zen pay-as-you-go)
    "opencode_go": {
        "api_key_env": "OPENCODE_API_KEY",
        "base_url": "https://opencode.ai/zen/go/v1",
        "prefix": "openai",
    },
    # OpenCode Go — MiniMax M2.5 uses Anthropic Messages API
    "opencode_go_anthropic": {
        "api_key_env": "OPENCODE_API_KEY",
        "base_url": "https://opencode.ai/zen/go/v1",
        "prefix": "anthropic",
    },
    # OpenCode Zen — pay-as-you-go, more models available
    # Gemini 3 Flash, GPT-5.2-Codex, Claude Haiku 4.5
    "opencode_zen": {
        "api_key_env": "OPENCODE_API_KEY",
        "base_url": "https://opencode.ai/zen/v1",
        "prefix": "openai",
    },
    # OpenCode Zen — Anthropic-compatible models
    "opencode_zen_anthropic": {
        "api_key_env": "OPENCODE_API_KEY",
        "base_url": "https://opencode.ai/zen/v1",
        "prefix": "anthropic",
    },
}


# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------

MODELS = {
    # === Google (direct) ===
    "gemini-3.1-pro": {
        "provider": "google_direct",
        "model_id": "gemini-3.1-pro-preview",
        "input_price": 2.0,
        "output_price": 12.0,
        "ctx": 1_000_000,
        "note": "3-tier thinking, 1M ctx, best for architecture",
    },
    "gemini-3-flash": {
        "provider": "google_direct",
        "model_id": "gemini-3-flash-preview",
        "input_price": 0.10,
        "output_price": 0.40,
        "ctx": 1_000_000,
        "note": "Gemini 3 Flash via Google direct, fast and capable",
    },
    "gemini-2.5-flash": {
        "provider": "google_direct",
        "model_id": "gemini-2.5-flash",
        "input_price": 0.15,
        "output_price": 0.60,
        "ctx": 1_000_000,
        "note": "Fast and cheap, good for simple tasks",
    },
    # === Anthropic (direct) ===
    "claude-sonnet-4.6": {
        "provider": "anthropic_direct",
        "model_id": "claude-sonnet-4-6",
        "input_price": 3.0,
        "output_price": 15.0,
        "ctx": 200_000,
        "note": "Extended thinking, cross-vendor review",
    },
    # === OpenAI via Vercel ===
    "gpt-5.1-codex-mini": {
        "provider": "vercel",
        "model_id": "openai/gpt-5.1-codex-mini",
        "input_price": 0.25,
        "output_price": 2.0,
        "ctx": 400_000,
        "note": "Codex-optimized, 83.6% LiveCodeBench",
    },
    # === OpenCode Go ($10/mo subscription) ===
    "glm-5": {
        "provider": "opencode_go",
        "model_id": "glm-5",
        "input_price": 0.0,
        "output_price": 0.0,
        "ctx": 128_000,
        "note": "Z.AI reasoning model, Go subscription",
    },
    "kimi-k2.5": {
        "provider": "opencode_go",
        "model_id": "kimi-k2.5",
        "input_price": 0.0,
        "output_price": 0.0,
        "ctx": 256_000,
        "note": "Moonshot, long-context, Go subscription",
    },
    "minimax-m2.5": {
        "provider": "opencode_go_anthropic",
        "model_id": "minimax-m2.5",
        "input_price": 0.0,
        "output_price": 0.0,
        "ctx": 256_000,
        "note": "MiniMax, Anthropic API, Go subscription",
    },
    # === OpenCode Zen (pay-as-you-go) ===
    "gpt-5.2-codex": {
        "provider": "opencode_zen",
        "model_id": "gpt-5.2-codex",
        "input_price": 0.50,
        "output_price": 4.0,
        "ctx": 400_000,
        "note": "GPT-5.2 Codex via OpenCode Zen, advanced coding",
    },
    "claude-haiku-4.5": {
        "provider": "opencode_zen_anthropic",
        "model_id": "claude-haiku-4-5",
        "input_price": 0.80,
        "output_price": 4.0,
        "ctx": 200_000,
        "note": "Claude Haiku 4.5 via OpenCode Zen, fast and smart",
    },
}


# ---------------------------------------------------------------------------
# Agent → Model assignment  ← CHANGE MODELS HERE
# ---------------------------------------------------------------------------

AGENT_MODELS = {
    "architect": "claude-sonnet-4.6",
    "coder": "gemini-3-flash",
    "reviewer": "claude-sonnet-4.6",
    "integrator": "gemini-3-flash",
    "junior": "gemini-2.5-flash",
}

AGENT_MAX_TOKENS = {
    "architect": 4096,
    "coder": 8192,
    "reviewer": 16000,  # extended thinking needs more
    "integrator": 16384,
    "junior": 4096,
}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_llm(agent_name: str) -> LLM:
    """Return a configured LLM object for the given agent."""
    model_key = AGENT_MODELS[agent_name]
    model_cfg = MODELS[model_key]
    provider_cfg = PROVIDERS[model_cfg["provider"]]

    api_key = os.getenv(provider_cfg["api_key_env"])
    if not api_key:
        raise ValueError(f"Missing API key: set {provider_cfg['api_key_env']} in .env")

    model_string = f"{provider_cfg['prefix']}/{model_cfg['model_id']}"
    max_tokens = AGENT_MAX_TOKENS.get(agent_name, 4096)

    kwargs = {
        "model": model_string,
        "api_key": api_key,
        "max_tokens": max_tokens,
    }
    if "base_url" in provider_cfg:
        kwargs["base_url"] = provider_cfg["base_url"]

    return LLM(**kwargs)


def get_model_pricing() -> dict:
    """Return pricing dict compatible with supervisor.py MODEL_PRICING."""
    pricing = {}
    for key, cfg in MODELS.items():
        provider_cfg = PROVIDERS[cfg["provider"]]
        full_id = f"{provider_cfg['prefix']}/{cfg['model_id']}"
        bare_id = (
            cfg["model_id"].split("/")[-1]
            if "/" in cfg["model_id"]
            else cfg["model_id"]
        )
        price = {"input": cfg["input_price"], "output": cfg["output_price"]}
        pricing[full_id] = price
        pricing[bare_id] = price
        pricing[key] = price
    return pricing


def print_catalog():
    """Print overview of all available models."""
    print("\n📋 Available models:")
    print("-" * 100)
    print(f"{'Name':<22} {'Provider':<24} {'Model string':<40} {'Price':<16} {'Ctx'}")
    print("-" * 100)
    for key, cfg in MODELS.items():
        provider_cfg = PROVIDERS[cfg["provider"]]
        full_id = f"{provider_cfg['prefix']}/{cfg['model_id']}"
        price = (
            f"${cfg['input_price']}/${cfg['output_price']}"
            if cfg["input_price"] > 0
            else "Go subscription"
        )
        ctx = f"{cfg['ctx']:,}"
        print(f"{key:<22} {cfg['provider']:<24} {full_id:<40} {price:<16} {ctx}")
    print(f"\n🤖 Current agent assignments:")
    print("-" * 50)
    for agent, model_key in AGENT_MODELS.items():
        print(f"  {agent:<14} → {model_key}")
    print()


if __name__ == "__main__":
    print_catalog()
