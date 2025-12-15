import random
import sys
import re
from time import sleep

RED = '\033[31m'
GREEN = '\033[32m'
CYAN = '\033[36m'
MAGENTA = '\033[35m'
YELLOW = '\033[33m'
WHITE = '\033[37m'
BOLD = '\033[1m'
RESET = '\033[0m'
CLEAR_LINE = '\033[2K'
HIDE_CURSOR = '\033[?25l'
SHOW_CURSOR = '\033[?25h'

RARITY_COLORS = {
    'common': WHITE,
    'uncommon': GREEN,
    'rare': CYAN,
    'epic': MAGENTA,
    'legendary': YELLOW,
}

ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

def visible_slice(s, start, length):
    """Slice string by visible character positions, preserving ANSI codes."""
    result = []
    visible_pos = 0
    i = 0
    
    while i < len(s) and (visible_pos < start + length):
        if s[i] == '\033':
            j = i + 1
            while j < len(s) and not s[j].isalpha():
                j += 1
            j += 1
            escape_seq = s[i:j]
            if visible_pos >= start:
                result.append(escape_seq)
            i = j
        else:
            if start <= visible_pos < start + length:
                result.append(s[i])
            visible_pos += 1
            i += 1
    
    return ''.join(result)

def ticker_line(terminal_width=50):
    return RESET + "=" * (terminal_width//2 - 1) + RED + "|" + RESET + "=" * (terminal_width//2 - 1)

def generate_spinner_cards(card_pool: list[dict], count=30) -> list[str]:
    """Generate a list of colored card names for the spinner display."""
    result = []
    for _ in range(count):
        card = random.choice(card_pool)
        name = card['card_name']
        rarity = card.get('rarity', 'common')
        color = RARITY_COLORS.get(rarity, WHITE)
        result.append(f"{color}{name}{RESET}")
    return result

def prepare_spinner_data(text: list[str], chosen_card: str, terminal_width=50):
    text_str = " ".join(text) + " "
    plain_text = ansi_escape.sub('', text_str)
    chosen_pos = plain_text.find(chosen_card)
    
    if chosen_pos == -1:
        chosen_pos = len(plain_text) // 2
    
    ticker_pos = int(terminal_width * 0.5)
    stop_pos = chosen_pos - ticker_pos + len(chosen_card) // 2
    
    min_scroll = terminal_width * 2
    if stop_pos < min_scroll:
        text_str = text_str * 5
        plain_text = ansi_escape.sub('', text_str)
        chosen_pos = plain_text.find(chosen_card, min_scroll)
        stop_pos = chosen_pos - ticker_pos + len(chosen_card) // 2
    
    cyclic_text = text_str * 5
    return {
        'cyclic_text': cyclic_text,
        'stop_pos': stop_pos,
        'chosen_card': chosen_card
    }

def multi_spinner(spinner_data: list[dict], terminal_width=50, base_delay=0.01, max_delay=0.15):
    """Run multiple spinners simultaneously."""
    max_frames = max(data['stop_pos'] for data in spinner_data)
    num_lines = len(spinner_data)
    total_lines = num_lines * 2
    
    print(HIDE_CURSOR, end='')
    
    try:
        for frame in range(max_frames):
            progress = frame / max_frames
            current_delay = base_delay + (max_delay - base_delay) * progress
            
            output_lines = []
            for data in spinner_data:
                spinner_frame = min(frame, data['stop_pos'] - 1)
                display = visible_slice(data['cyclic_text'], spinner_frame, terminal_width)
                output_lines.append(ticker_line(terminal_width))
                output_lines.append(display)
            
            if frame > 0:
                sys.stdout.write(f'\033[{total_lines}A')
            
            for line in output_lines:
                sys.stdout.write(f'{CLEAR_LINE}{line}\n')
            
            sys.stdout.flush()
            sleep(current_delay)
        
        print()
        
    finally:
        print(SHOW_CURSOR, end='')

def animate_pack_opening(cards: list[dict], terminal_width=50, base_delay=0.01, max_delay=0.12):
    """
    Animate pack opening.
    
    Args:
        cards: List of dicts with 'card_name' and 'rarity' keys (from API response)
        terminal_width: Width of the terminal display
        base_delay: Starting delay (fast)
        max_delay: Ending delay (slow)
    """
    if not cards:
        print("No cards to display!")
        return
    
    # Build spinner data for each card
    spinner_data = []
    
    for card in cards:
        chosen_name = card['card_name']
        # Generate random cards for the spinner (using all cards as pool)
        spinner_cards = generate_spinner_cards(cards, count=30)
        data = prepare_spinner_data(spinner_cards, chosen_name, terminal_width)
        spinner_data.append(data)
    
    # Run the animation
    multi_spinner(spinner_data, terminal_width, base_delay, max_delay)
    
    # Display results
    print(f"\n{BOLD}★ You got: {RESET}")
    for card in cards:
        color = RARITY_COLORS.get(card.get('rarity', 'common'), WHITE)
        rarity_tag = f"[{card['rarity'].upper()}]"
        print(f"  {color}{rarity_tag} {card['card_name']}{RESET}")
    print()