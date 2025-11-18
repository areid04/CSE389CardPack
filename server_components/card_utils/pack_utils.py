from pack import CardPack
import json

def pack_from_path(path: str) -> CardPack:
    """Load a CardPack from a JSON file at the given path.

    :param path: Path to the JSON file.
    :return: An instance of `CardPack`.
    """
    with open(path, 'r') as f:
        data = json.load(f)

    pack_name = data.get('pack_name', 'Unnamed Pack')
    card_distribution = data.get('card_distribution', {})
    total_cards = data.get('total_cards', 5)

    return CardPack(pack_name, card_distribution, total_cards)