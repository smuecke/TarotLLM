from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ROOT, app_language


@dataclass(frozen=True)
class SpreadSlot:
    key: str
    name: str
    x: float
    y: float
    role: str
    rotation: str | None = None

    def to_public(self) -> dict[str, object]:
        data: dict[str, object] = {
            "key": self.key,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "role": self.role,
        }
        if self.rotation:
            data["rot"] = self.rotation
        return data


@dataclass(frozen=True)
class Spread:
    key: str
    name: str
    description: str
    order: int
    slots: list[SpreadSlot]

    @classmethod
    def from_toml(cls, path: Path) -> "Spread":
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        spread_data = data.get("spread", {})
        slots_data = data.get("slots", {})
        slots = [
            build_slot(key=key, item=item)
            for key, item in slots_data.items()
        ]
        return cls(
            key=str(spread_data.get("id", path.stem)),
            name=str(spread_data.get("name", path.stem)),
            description=str(spread_data.get("description", "")),
            order=int(spread_data.get("order", 0)),
            slots=slots,
        )

    def to_public(self) -> dict[str, object]:
        return {
            "id": self.key,
            "name": self.name,
            "description": self.description,
            "positions": [slot.to_public() for slot in self.slots],
        }


def build_slot(key: str, item: dict[str, Any]) -> SpreadSlot:
    rotation = item.get("rot", item.get("rotation"))
    if isinstance(rotation, int | float):
        rotation = f"{rotation}deg"
    return SpreadSlot(
        key=key,
        name=str(item.get("name", key)),
        x=float(item.get("x", 50)),
        y=float(item.get("y", 50)),
        role=str(item.get("role", "")),
        rotation=str(rotation) if rotation is not None else None,
    )


def load_spreads() -> list[Spread]:
    spreads_dir = spreads_dir_for_language()
    spreads = [
        Spread.from_toml(path)
        for path in sorted(spreads_dir.glob("*.toml"))
    ]
    return sorted(spreads, key=lambda spread: (spread.order, spread.name))


def spreads_dir_for_language() -> Path:
    return ROOT / "data" / "spreads" / app_language()


SPREADS = load_spreads()
