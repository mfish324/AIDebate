"""Configuration loading and management"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ProviderConfig:
    """Configuration for a single AI provider"""

    name: str
    enabled: bool = True
    model: str = ""
    max_tokens: int = 1000
    temperature: float = 0.7

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> ProviderConfig:
        return cls(
            name=name,
            enabled=data.get("enabled", True),
            model=data.get("model", ""),
            max_tokens=data.get("max_tokens", 1000),
            temperature=data.get("temperature", 0.7),
        )


@dataclass
class DebateConfig:
    """Configuration for debate settings"""

    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DebateConfig:
        return cls(
            timeout=data.get("timeout", 30),
            max_retries=data.get("max_retries", 3),
            retry_delay=data.get("retry_delay", 1.0),
        )


@dataclass
class OutputConfig:
    """Configuration for output settings"""

    directory: str = "debates"
    formats: list[str] = field(default_factory=lambda: ["md"])
    verbose: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutputConfig:
        return cls(
            directory=data.get("directory", "debates"),
            formats=data.get("formats", ["md"]),
            verbose=data.get("verbose", False),
        )


@dataclass
class CostConfig:
    """Configuration for cost tracking"""

    provider_costs: dict[str, dict[str, float]] = field(default_factory=dict)
    warning_threshold: float = 1.00

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CostConfig:
        provider_costs = {}
        warning_threshold = data.get("warning_threshold", 1.00)

        for provider in ["claude", "openai", "gemini", "groq"]:
            if provider in data:
                provider_costs[provider] = {
                    "input": data[provider].get("input", 0.0),
                    "output": data[provider].get("output", 0.0),
                }

        return cls(
            provider_costs=provider_costs,
            warning_threshold=warning_threshold,
        )


@dataclass
class Config:
    """Main configuration class"""

    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    debate: DebateConfig = field(default_factory=DebateConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    costs: CostConfig = field(default_factory=CostConfig)

    def get_enabled_providers(self) -> list[ProviderConfig]:
        """Return list of enabled providers"""
        return [p for p in self.providers.values() if p.enabled]

    def get_provider(self, name: str) -> ProviderConfig | None:
        """Get provider config by name"""
        return self.providers.get(name)

    def enable_only(self, provider_names: list[str]) -> None:
        """Enable only specified providers, disable others"""
        for name, provider in self.providers.items():
            provider.enabled = name in provider_names

    def exclude_providers(self, provider_names: list[str]) -> None:
        """Disable specified providers"""
        for name in provider_names:
            if name in self.providers:
                self.providers[name].enabled = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        """Create config from dictionary"""
        providers = {}
        providers_data = data.get("providers", {})

        for name, pdata in providers_data.items():
            providers[name] = ProviderConfig.from_dict(name, pdata)

        return cls(
            providers=providers,
            debate=DebateConfig.from_dict(data.get("debate", {})),
            output=OutputConfig.from_dict(data.get("output", {})),
            costs=CostConfig.from_dict(data.get("costs", {})),
        )


def get_default_config() -> Config:
    """Return default configuration"""
    return Config.from_dict(
        {
            "providers": {
                "claude": {
                    "enabled": True,
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1000,
                    "temperature": 0.7,
                },
                "openai": {
                    "enabled": True,
                    "model": "gpt-4.1",
                    "max_tokens": 1000,
                    "temperature": 0.7,
                },
                "gemini": {
                    "enabled": True,
                    "model": "gemini-2.5-flash",
                    "max_tokens": 1000,
                    "temperature": 0.7,
                },
                "groq": {
                    "enabled": True,
                    "model": "llama-4-scout-17b-16e-instruct",
                    "max_tokens": 1000,
                    "temperature": 0.7,
                },
            },
            "debate": {
                "timeout": 30,
                "max_retries": 3,
                "retry_delay": 1.0,
            },
            "output": {
                "directory": "debates",
                "formats": ["md"],
                "verbose": False,
            },
            "costs": {
                "claude": {"input": 0.003, "output": 0.015},
                "openai": {"input": 0.002, "output": 0.008},
                "gemini": {"input": 0.00015, "output": 0.0006},
                "groq": {"input": 0.00059, "output": 0.00079},
                "warning_threshold": 1.00,
            },
        }
    )


def load_config(config_path: str | Path | None = None) -> Config:
    """Load configuration from YAML file or return defaults"""
    if config_path is None:
        # Try to find config.yaml in current directory or parent
        for path in [Path("config.yaml"), Path(__file__).parent.parent.parent / "config.yaml"]:
            if path.exists():
                config_path = path
                break

    if config_path and Path(config_path).exists():
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        return Config.from_dict(data)

    return get_default_config()


def get_api_key(provider: str) -> str | None:
    """Get API key for provider from environment"""
    key_mapping = {
        "claude": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
    }
    env_var = key_mapping.get(provider)
    return os.environ.get(env_var) if env_var else None
