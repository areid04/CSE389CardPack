# pack of cards dataclass. 
# each pack contains a distribution of cards, as a kewargs dict.
# create the cards
import random
from card import Card
from typing import Dict, Any


class CardPack:
    """A pack that yields Card objects according to a probability distribution.

    Each entry in `card_distribution` can be either a float probability or a dict
    with keys `prob` and optional `rarity`, for example:
      {'Drake': 0.5, 'Alex': {'prob': 0.3, 'rarity': 'rare'}}

    The constructor normalizes probabilities so they sum to 1.
    """

    def __init__(self, pack_name: str, card_distribution: Dict[str, Any], total_cards: int):
        self.pack_name = pack_name
        self.total_cards = total_cards

        # Normalize and store distribution in a uniform internal format:
        # {name: {'prob': float, 'rarity': str}}
        flat: Dict[str, Dict[str, Any]] = {}
        raw_probs = []
        for name, val in card_distribution.items():
            if isinstance(val, dict):
                prob = float(val.get('prob', 0.0))
                rarity = val.get('rarity')
            else:
                prob = float(val)
                rarity = None
            flat[name] = {'prob': prob, 'rarity': rarity}
            raw_probs.append(prob)

        total_prob = sum(raw_probs)
        if total_prob <= 0:
            raise ValueError('Card distribution must contain at least one positive probability.')

        # Normalize probabilities to sum to 1. This makes pack design forgiving.
        for info in flat.values():
            info['prob'] = info['prob'] / total_prob

        self._distribution = flat

    def __prob_helper(self) -> str:
        """Choose a card name according to the normalized distribution.

        :return: The selected card name (string).
        """
        # Use a uniform random float and walk the cumulative distribution.
        # This is simple and deterministic enough for quick prototyping.
        rand_value = random.random()
        cumulative = 0.0
        for card_name, info in self._distribution.items():
            cumulative += info['prob']
            if rand_value < cumulative:
                return card_name
        # Fallback in case of rounding errors
        return list(self._distribution.keys())[-1]

    def open_pack(self) -> list:
        """Open the pack and return a list of `Card` objects.

        Each opened card is constructed as `Card(name, rarity)`. If the distribution
        entry provided a `rarity` it will be used; otherwise the rarity will be
        set to `'common'` by default.
        """
        # Returns a list of `Card` instances. Caller can persist these via DB helpers.
        opened_cards = []
        for _ in range(self.total_cards):
            card_name = self.__prob_helper()
            info = self._distribution.get(card_name, {})
            rarity = info.get('rarity') or 'common'
            opened_cards.append(Card(card_name, rarity))

        return opened_cards




    