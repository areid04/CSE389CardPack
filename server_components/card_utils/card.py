# card data class.
# Lightweight value object for a collectible card. Fields are intentionally
# simple: `card_name` is the display/lookup name and `rarity` is used by
# pack generation, marketplace and auction logic.
class Card:
    def __init__(self, name: str, rarity: str):
        self.card_name = name
        self.rarity = rarity
