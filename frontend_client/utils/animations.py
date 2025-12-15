import random
import sys
import re
from time import sleep

RED = '\033[31m'
GREEN = '\033[32m'
CYAN = '\033[36m'
RESET = '\033[0m'
CLEAR_LINE = '\033[2K'
HIDE_CURSOR = '\033[?25l'
SHOW_CURSOR = '\033[?25h'

ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

def visible_len(s):
    return len(ansi_escape.sub('', s))

def visible_slice(s, start, length):
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

def multi_spinner(spinners: list[dict], terminal_width=50, base_delay=0.01, max_delay=0.15):
    spinner_data = []
    max_frames = 0
    
    for spinner in spinners:
        data = prepare_spinner_data(spinner['cards'], spinner['chosen'], terminal_width)
        spinner_data.append(data)
        max_frames = max(max_frames, data['stop_pos'])
    
    num_lines = len(spinners)
    total_lines = num_lines * 2  # ticker + content for each
    
    print(HIDE_CURSOR, end='')
    
    try:
        for frame in range(max_frames):
            progress = frame / max_frames
            current_delay = base_delay + (max_delay - base_delay) * progress
            
            # Build all lines for this frame
            output_lines = []
            for data in spinner_data:
                spinner_frame = min(frame, data['stop_pos'] - 1)
                display = visible_slice(data['cyclic_text'], spinner_frame, terminal_width)
                output_lines.append(ticker_line(terminal_width))
                output_lines.append(display)
            
            # Move to start and redraw everything
            if frame > 0:
                # Move cursor up to overwrite previous frame
                sys.stdout.write(f'\033[{total_lines}A')
            
            # Print all lines
            for line in output_lines:
                sys.stdout.write(f'{CLEAR_LINE}{line}\n')
            
            sys.stdout.flush()
            sleep(current_delay)
        
        print()
        
    finally:
        print(SHOW_CURSOR, end='')

def weighted_card_selection(card_distribution: dict[str, float], count=30) -> list[str]:
    selected_cards = []
    card_names = list(card_distribution.keys())
    probabilities = [info['prob'] if isinstance(info, dict) else info for info in card_distribution.values()]

    for _ in range(count):
        chosen = random.choices(card_names, weights=probabilities)[0]
        rarity = card_distribution[chosen].get('rarity', 'common')
        match rarity:
            case 'common':
                chosen = RESET + chosen + RESET
            case 'rare':
                chosen = CYAN + chosen + RESET
            case 'epic':
                chosen = GREEN + chosen + RESET
            case 'legendary':
                chosen = RED + chosen + RESET
            case _:
                chosen = RESET + chosen + RESET
        selected_cards.append(chosen)

    return selected_cards


if __name__ == "__main__":
    # Enable ANSI on Windows
    import os
    os.system('')
    
    sample_dist = {
        'Dragon': {'prob': 0.5, 'rarity': 'legendary'},
        'Knight': {'prob': 0.3, 'rarity': 'epic'},
        'Goblin': {'prob': 0.15, 'rarity': 'rare'},
        'Slime': {'prob': 0.05, 'rarity': 'common'}
    }
    
    num_cards = 3
    spinners = []
    chosen_cards = []
    
    for _ in range(num_cards):
        chosen = random.choice(list(sample_dist.keys()))
        chosen_cards.append(chosen)
        cards = weighted_card_selection(sample_dist)
        spinners.append({'cards': cards, 'chosen': chosen})
    
    print(f"Opening {num_cards} cards...\n")
    
    multi_spinner(spinners, terminal_width=50, base_delay=0.01, max_delay=0.12)
    
    print(f"\n{RESET}★ You got: {', '.join(chosen_cards)}! ★")