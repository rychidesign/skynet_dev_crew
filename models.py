"""
Central LLM model registry.

Usage in agents:
    from models import get_llm
    llm = get_llm("architect")

Switching a model = changing one string in AGENT_MODELS.
"""

import os
from crewai import LLM


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------

PROVIDERS = {
    "vercel": {
        "api_key_env": "VERCEL_AI_GATEWAY_API_KEY",
        "prefix": "vercel_ai_gateway",
    },
    "opencode_go": {
        "api_key_env": "OPENCODE_API_KEY",
        "base_url": "https://opencode.ai/zen/v1",
        "prefix": "openai",  # OpenAI-compatible API
    },
}


# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------

MODELS = {
    # === Vercel AI Gateway ===
    "gemini-3.1-pro": {
        "provider": "vercel",
        "model_id": "google/gemini-3.1-pro-preview",
        "input_price": 2.0,
        "output_price": 12.0,
        "ctx": 1_000_000,
        "note": "3-tier thinking, 1M ctx, best for architecture",
    },
    "gpt-5.1-codex-mini": {
        "provider": "vercel",
        "model_id": "openai/gpt-5.1-codex-mini",
        "input_price": 0.25,
        "output_price": 2.0,
        "ctx": 400_000,
        "note": "Codex-optimized, 83.6% LiveCodeBench",
    },
    "claude-sonnet-4.6": {
        "provider": "vercel",
        "model_id": "anthropic/claude-sonnet-4.6",
        "input_price": 3.0,
        "output_price": 15.0,
        "ctx": 200_000,
        "note": "Extended thinking, cross-vendor review",
    },

    "gemini-2.5-flash": {
        "provider": "vercel",
        "model_id": "google/gemini-2.5-flash",
        "input_price": 0.15,
        "output_price": 0.60,
        "ctx": 1_000_000,
        "note": "Fast and cheap, good for simple tasks",
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
        "provider": "opencode_go",
        "model_id": "minimax-m2.5",
        "input_price": 0.0,
        "output_price": 0.0,
        "ctx": 256_000,
        "note": "MiniMax, low-cost coding, Go subscription",
    },
}


# ---------------------------------------------------------------------------
# Agent → Model assignment  ← CHANGE MODELS HERE
# ---------------------------------------------------------------------------

AGENT_MODELS = {
    "architect":   "gemini-3.1-pro",
    "coder":       "gpt-5.1-codex-mini",
    "reviewer":    "claude-sonnet-4.6",
    "integrator":  "kimi-k2.5",
    "junior":      "gemini-2.5-flash",
}

AGENT_MAX_TOKENS = {
    "architect":   4096,
    "coder":       8192,
    "reviewer":    16000,   # extended thinking needs more
    "integrator":  16384,
    "junior":      4096,
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
        raise ValueError(
            f"Missing API key: set {provider_cfg['api_key_env']} in .env"
        )

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
        bare_id = cfg["model_id"].split("/")[-1] if "/" in cfg["model_id"] else cfg["model_id"]
        price = {"input": cfg["input_price"], "output": cfg["output_price"]}
        pricing[full_id] = price
        pricing[bare_id] = price
        pricing[key] = price
    return pricing


def print_catalog():
    """Print overview of all available models."""
    print("\n📋 Available models:")
    print("-" * 90)
    print(f"{'Name':<22} {'Provider':<14} {'Model ID':<35} {'Price (in/out)':<16} {'Ctx'}")
    print("-" * 90)
    for key, cfg in MODELS.items():
        price = (
            f"${cfg['input_price']}/{cfg['output_price']}"
            if cfg["input_price"] > 0
            else "Go subscription"
        )
        ctx = f"{cfg['ctx']:,}"
        print(f"{key:<22} {cfg['provider']:<14} {cfg['model_id']:<35} {price:<16} {ctx}")
    print(f"\n🤖 Current agent assignments:")
    print("-" * 50)
    for agent, model_key in AGENT_MODELS.items():
        print(f"  {agent:<14} → {model_key}")
    print()


if __name__ == "__main__":
    print_catalog()
