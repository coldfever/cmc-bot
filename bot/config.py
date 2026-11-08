"""Încarcă config/server.yaml și oferă acces comod la jocuri, canale, roluri."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "server.yaml"


@dataclass
class ChannelSpec:
    name: str
    type: str = "text"  # text | forum | voce
    readonly: bool = False
    topic: str | None = None


@dataclass
class CategorySpec:
    name: str
    access: str = "public"  # public | staff | game
    channels: list[ChannelSpec] = field(default_factory=list)
    game_role: str | None = None


@dataclass
class Game:
    key: str
    name: str
    emoji: str
    category: str
    role: str
    competitive_role: str | None
    color: str | None
    card_lookup: str | None
    channels: list[ChannelSpec]

    @property
    def announce_channel(self) -> str | None:
        ro = [c.name for c in self.channels if c.readonly and c.type == "text"]
        return ro[0] if ro else None

    @property
    def trade_channel(self) -> str | None:
        for c in self.channels:
            if "schimb" in c.name:
                return c.name
        return None


def _channels(raw: list[dict]) -> list[ChannelSpec]:
    return [
        ChannelSpec(
            name=c["nume"],
            type=c.get("tip", "text"),
            readonly=bool(c.get("doar_citire", False)),
            topic=c.get("subiect"),
        )
        for c in raw
    ]


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self.reload()

    def reload(self) -> None:
        with open(self.path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        self.raw = raw
        self.tz = ZoneInfo(raw.get("fus_orar", "Europe/Bucharest"))
        self.hide_games = bool(raw.get("ascunde_jocuri_fara_rol", False))
        self.bot_channels: dict[str, str] = raw.get("canale_bot", {})
        roles = raw.get("roluri", {})
        self.staff_role = roles.get("staff", {}).get("nume", "Staff")
        self.staff_role_raw = roles.get("staff", {"nume": "Staff"})
        self.extra_roles = roles.get("extra", [])
        self.forum_tags: list[str] = raw.get("etichete_forum", [])
        self.trade_expiry_days = int(raw.get("expirare_anunturi_zile", 30))

        default_game_channels = _channels(raw.get("canale_joc_standard", []))
        self.games: list[Game] = []
        for g in raw.get("jocuri", []):
            self.games.append(
                Game(
                    key=g["cheie"],
                    name=g["nume"],
                    emoji=g.get("emoji", ""),
                    category=g["categorie"],
                    role=g["rol"],
                    competitive_role=g.get("rol_competitiv"),
                    color=g.get("culoare"),
                    card_lookup=g.get("cautare_carti"),
                    channels=_channels(g["canale"]) if "canale" in g else list(default_game_channels),
                )
            )

        # Ordinea finală: categoriile publice până la Comunitate, apoi jocurile, apoi restul.
        base = [
            CategorySpec(name=c["nume"], access=c.get("acces", "public"), channels=_channels(c.get("canale", [])))
            for c in raw.get("categorii", [])
        ]
        game_cats = [CategorySpec(name=g.category, access="game", channels=g.channels, game_role=g.role) for g in self.games]
        idx = next((i for i, c in enumerate(base) if "comunitate" in c.name.lower()), len(base) - 1)
        self.categories: list[CategorySpec] = base[: idx + 1] + game_cats + base[idx + 1 :]

    def game(self, key: str) -> Game | None:
        return next((g for g in self.games if g.key == key), None)

    def channel_name(self, purpose: str) -> str | None:
        return self.bot_channels.get(purpose)


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)
