"""General category, colour, material, and condition terms. Not item-specific."""

from __future__ import annotations

CATEGORIES: dict[str, str] = {
    "sneaker": "footwear",
    "sneakers": "footwear",
    "trainer": "footwear",
    "trainers": "footwear",
    "shoe": "footwear",
    "shoes": "footwear",
    "boot": "footwear",
    "boots": "footwear",
    "loafer": "footwear",
    "sandal": "footwear",
    "footwear": "footwear",
    "jacket": "outerwear",
    "coat": "outerwear",
    "parka": "outerwear",
    "shirt": "top",
    "tee": "top",
    "hoodie": "top",
    "sweater": "top",
    "trousers": "bottom",
    "pants": "bottom",
    "jeans": "bottom",
    "shorts": "bottom",
    "bag": "bag",
    "tote": "bag",
    "backpack": "bag",
    "belt": "accessory",
    "hat": "accessory",
    "cap": "accessory",
    "sunglasses": "accessory",
    "watch": "accessory",
    "scarf": "accessory",
}

COLOURS = frozenset(
    {
        "black",
        "white",
        "navy",
        "grey",
        "gray",
        "brown",
        "olive",
        "khaki",
        "red",
        "blue",
        "green",
        "beige",
        "cream",
        "tan",
        "ivory",
        "silver",
        "gold",
        "burgundy",
        "orange",
        "yellow",
        "pink",
        "purple",
        "camo",
        "multicolor",
    }
)

MATERIALS = frozenset(
    {
        "leather",
        "suede",
        "canvas",
        "rubber",
        "mesh",
        "nylon",
        "cotton",
        "wool",
        "denim",
        "patent",
        "sueded",
        "nubuck",
        "textile",
        "calf",
        "pony",
        "shearling",
    }
)

CONDITIONS = frozenset(
    {
        "used",
        "pre-owned",
        "preowned",
        "secondhand",
        "vintage",
        "archive",
        "archival",
        "deadstock",
        "ds",
        "nwt",
        "nwot",
        "new",
        "sold",
        "ended",
    }
)

SIZE_HINTS = frozenset({"size", "eu", "us", "uk", "cm", "mm", "taille", "サイズ"})


def category_of(token: str) -> str | None:
    return CATEGORIES.get(token.lower())


def is_colour(token: str) -> bool:
    return token.lower() in COLOURS


def is_material(token: str) -> bool:
    return token.lower() in MATERIALS
