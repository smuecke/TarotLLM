from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DECK_PATH = ROOT / "data" / "decks" / "tarot.toml"


@dataclass(frozen=True)
class TagInfo:
    key: str
    label: str
    context: str


@dataclass(frozen=True)
class DivinationCard:
    key: str
    name: str
    image: str
    tags: list[str]
    visual: str
    meaning: str
    deck: "DivinationDeck"

    @property
    def image_url(self) -> str:
        if self.image.startswith(("/", "http://", "https://")):
            return self.image
        return f"{self.deck.image_base.rstrip('/')}/{self.image}"

    @property
    def tag_labels(self) -> list[str]:
        return [self.deck.tags[tag].label for tag in self.tags if tag in self.deck.tags]

    def to_public(self) -> dict[str, object]:
        return {
            "key": self.key,
            "name": self.name,
            "tags": self.tags,
            "tagLabels": self.tag_labels,
            "image": self.image_url,
        }


@dataclass(frozen=True)
class DivinationDeck:
    key: str
    name: str
    language: str
    description: str
    image_base: str
    back_image: str | None
    tags: dict[str, TagInfo]
    cards: list[DivinationCard]

    @classmethod
    def from_toml(cls, path: Path) -> "DivinationDeck":
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        deck_data = data.get("deck", {})
        tag_data = data.get("tags", {})
        card_data = data.get("cards", {})

        tags = {
            key: TagInfo(
                key=key,
                label=str(item.get("label", key)),
                context=str(item.get("context", "")),
            )
            for key, item in tag_data.items()
        }
        deck = cls(
            key=str(deck_data.get("id", path.stem)),
            name=str(deck_data.get("name", path.stem)),
            language=str(deck_data.get("language", "")),
            description=str(deck_data.get("description", "")),
            image_base=str(deck_data.get("image_base", "/img")),
            back_image=deck_data.get("back_image"),
            tags=tags,
            cards=[],
        )
        cards = [
            build_card(deck=deck, key=key, item=item)
            for key, item in card_data.items()
        ]
        return replace_cards(deck, cards)

    def to_public(self) -> dict[str, object]:
        return {
            "key": self.key,
            "name": self.name,
            "language": self.language,
            "description": self.description,
            "backImage": self.back_image,
        }

def build_card(deck: DivinationDeck, key: str, item: dict[str, Any]) -> DivinationCard:
    tags = list(item.get("tags", []))
    return DivinationCard(
        key=key,
        name=str(item.get("name", key)),
        image=str(item.get("image", f"{key}.jpg")),
        tags=tags,
        visual=str(item.get("visual", "")),
        meaning=str(item.get("meaning", "")),
        deck=deck,
    )


def replace_cards(deck: DivinationDeck, cards: list[DivinationCard]) -> DivinationDeck:
    return DivinationDeck(
        key=deck.key,
        name=deck.name,
        language=deck.language,
        description=deck.description,
        image_base=deck.image_base,
        back_image=deck.back_image,
        tags=deck.tags,
        cards=cards,
    )


def deck_path() -> Path:
    configured = os.getenv("DECK_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_DECK_PATH


DECK = DivinationDeck.from_toml(deck_path())
CARDS = DECK.cards
CARD_BY_KEY = {card.key: card for card in CARDS}
