"""Configuration loading helpers with typed classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, Mapping, Optional

import yaml


@dataclass
class RolesConfig:
    booster: int
    invite: int
    dsme: int
    avatar_bot: int


@dataclass
class WebhookChannelsConfig:
    discadia: int
    dcservers: int


@dataclass
class Config(Mapping[str, Any]):
    """Typed bot configuration."""

    prefix: str
    description: str
    guild_id: int
    donate_url: str
    owner_id: int
    channels: Dict[str, int] = field(default_factory=dict)
    channels_voice: Dict[str, int] = field(default_factory=dict)
    roles: RolesConfig | None = None
    webhook_channels: WebhookChannelsConfig | None = None
    allowed_channels: list[int] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.raw)

    def __len__(self) -> int:
        return len(self.raw)

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self.raw.get(key, default)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Config":
        roles_data = data.get("roles") or {}
        webhook_data = data.get("webhook_channels") or {}
        cfg = Config(
            prefix=data.get("prefix", ","),
            description=data.get("description", ""),
            guild_id=data.get("guild_id", 0),
            donate_url=data.get("donate_url", ""),
            owner_id=data.get("owner_id", 0),
            channels=data.get("channels", {}),
            channels_voice=data.get("channels_voice", {}),
            roles=RolesConfig(**roles_data) if roles_data else None,
            webhook_channels=(
                WebhookChannelsConfig(**webhook_data) if webhook_data else None
            ),
            allowed_channels=data.get("allowed_channels", []),
            raw=data,
        )
        return cfg


def load_config(path: str = "config.yml") -> Config:
    """Load configuration from YAML file."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Config.from_dict(data)
