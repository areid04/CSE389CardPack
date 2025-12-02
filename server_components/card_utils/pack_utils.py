import json
from pathlib import Path
from .pack import CardPack

def pack_from_path(path: str) -> CardPack:
    """
    Load a Pack from a JSON file using a path relative to the pack_json directory.
    
    :param path: Path string like "/music/music_pack_vol_1.json"
    """
    current_dir = Path(__file__).parent.resolve()
    pack_json_dir = current_dir.parent / "pack_json"
    #    "/music/..." becomes "music/..."
    clean_path = path.lstrip("/\\")
    full_path = pack_json_dir / clean_path

    # Debug print to help you verify the path if it fails
    # print(f"DEBUG: Attempting to open -> {full_path}")

    with open(full_path, 'r') as f:
        data = json.load(f)

    pack_name = data.get('pack_name', 'Unnamed Pack')
    card_distribution = data.get('card_distribution', {})
    total_cards = data.get('total_cards', 5)

    return CardPack(pack_name, card_distribution, total_cards)