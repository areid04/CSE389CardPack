import requests
import json
import threading
import time
import asyncio
import websocket
from utils.pretty_display import print_info, print_border, print_startup_message

class SignInClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def create_user(self, username: str, email: str, password: str):
        url = f"{self.base_url}/signup"
        payload = {
            "username": username,
            "email": email,
            "password": password
        }
        response = requests.post(url, json=payload)
        return response.json()

    def login_user(self, email: str, password: str):
        url = f"{self.base_url}/login"
        payload = {
            "email": email,
            "password": password
        }
        response = requests.post(url, json=payload)
        return response.json()

class MainClient:
    def __init__(self, base_url: str, logged_email: str):
        self.base_url = base_url
        self.email = logged_email
        self.session = requests.Session()
        self.is_in_waiting_room = False
        self.is_in_auction_room = False  
        self._ws_app = None
        self._ws_thread = None
        self._auction_ws_app = None
        self._auction_ws_thread = None
        self.current_auction_room_id = None
        self.user_uuid = None  # You'll need to get this from login response

    def debug_create_pack(self):
        url = f"{self.base_url}/gen_default_pack"
        payload = {"email": self.email}
        response = self.session.post(url, json=payload)
        return response.json()

    def debug_open_pack(self):
        url = f"{self.base_url}/open_pack"
        payload = {"email": self.email}
        response = self.session.post(url, json=payload)
        return response.json()

    def get_my_cards(self):
        """Get all cards owned by the user."""
        url = f"{self.base_url}/my_cards"
        payload = {"email": self.email}
        response = self.session.post(url, json=payload)
        return response.json()

    def get_my_packs(self):
        """Get all packs owned by the user."""
        url = f"{self.base_url}/my_packs"
        payload = {"email": self.email}
        response = self.session.post(url, json=payload)
        return response.json()

    def create_pack(self, card_name:str, max_cards:int):
        url = f"{self.base_url}/create_pack"
        response = self.session.post(url)
        return response.json()

    def _to_ws_url(self, http_url: str) -> str:
        if http_url.startswith('https://'):
            return 'wss://' + http_url[len('https://'):]
        if http_url.startswith('http://'):
            return 'ws://' + http_url[len('http://'):]
        return http_url

    def join_trade_waiting_room(self, on_message=None, timeout: float = 5.0):
        """Connect to the trade waiting room websocket.

        - `on_message` (optional): callable that receives a (message_str) when the server sends data.
        - `timeout`: seconds to wait for the connection to open before returning.

        This starts a background thread that listens for incoming messages.
        """
        ws_path = f"{self.base_url}/ws/trade_waiting_room"
        ws_url = self._to_ws_url(ws_path)

        def _on_open(ws):
            self.is_in_waiting_room = True
            print_info('Connected to trade waiting room websocket.')

        def _on_message(ws, message):
            if on_message:
                try:
                    on_message(message)
                except Exception:
                    print_info('Error in on_message handler')
            else:
                print_info(f'WS message: {message}')

        def _on_close(ws, close_status_code, close_msg):
            self.is_in_waiting_room = False
            print_info(f'Websocket closed: {close_status_code} {close_msg}')

        def _on_error(ws, error):
            print_info(f'Websocket error: {error}')

        self._ws_app = websocket.WebSocketApp(
            ws_url,
            on_open=_on_open,
            on_message=_on_message,
            on_close=_on_close,
            on_error=_on_error,
        )

        def _run():
            # run_forever blocks; run in background thread
            try:
                self._ws_app.run_forever()
            except Exception as e:
                print_info(f'Websocket run_forever exited: {e}')

        self._ws_thread = threading.Thread(target=_run, daemon=True)
        self._ws_thread.start()

        # wait for open or timeout
        start = time.time()
        while not self.is_in_waiting_room and (time.time() - start) < timeout:
            time.sleep(0.05)

        return {'connected': self.is_in_waiting_room}

    def send_trade_message(self, message: str):
        if not self.is_in_waiting_room or not self._ws_app:
            print_info("You are not in the trade waiting room.")
            return {'error': 'not_connected'}

        payload = {"message": message}
        try:
            # send JSON text over the websocket
            self._ws_app.send(json.dumps(payload))
            return {'sent': True}
        except Exception as e:
            print_info(f'Error sending websocket message: {e}')
            return {'error': str(e)}

    def get_auction_rooms(self):
        """Get status of all auction rooms."""
        url = f"{self.base_url}/auction/rooms"
        response = self.session.get(url)
        return response.json()

    def list_item_for_auction(self, card_name: str, starting_bid: int, buyout_price: int, time_limit: int = 300):
        """List an item in the auction house."""
        url = f"{self.base_url}/auction/list-item"
        payload = {
            "card_name": card_name,
            "seller_uuid": self.user_uuid,  
            "buyout_price": buyout_price,
            "time_limit": time_limit
        }
        response = self.session.post(url, json=payload)
        return response.json()

    def join_auction_room(self, room_id: int, on_message=None, timeout: float = 5.0):
        """Connect to an auction room websocket."""
        ws_path = f"{self.base_url}/auction/room/{room_id}?user_uuid={self.user_uuid}"
        ws_url = self._to_ws_url(ws_path)
        
        self.current_auction_room_id = room_id

        def _on_open(ws):
            self.is_in_auction_room = True
            print_info(f'Connected to auction room {room_id}')

        def _on_message(ws, message):
            try:
                data = json.loads(message)
                if on_message:
                    on_message(data)
                else:
                    # Default message handling
                    self._handle_auction_message(data)
            except json.JSONDecodeError:
                print_info(f'Raw WS message: {message}')
            except Exception as e:
                print_info(f'Error handling message: {e}')

        def _on_close(ws, close_status_code, close_msg):
            self.is_in_auction_room = False
            self.current_auction_room_id = None
            print_info(f'Left auction room: {close_status_code} {close_msg}')

        def _on_error(ws, error):
            print_info(f'Auction websocket error: {error}')

        self._auction_ws_app = websocket.WebSocketApp(
            ws_url,
            on_open=_on_open,
            on_message=_on_message,
            on_close=_on_close,
            on_error=_on_error,
        )

        def _run():
            try:
                self._auction_ws_app.run_forever()
            except Exception as e:
                print_info(f'Auction websocket run_forever exited: {e}')

        self._auction_ws_thread = threading.Thread(target=_run, daemon=True)
        self._auction_ws_thread.start()

        # Wait for connection
        start = time.time()
        while not self.is_in_auction_room and (time.time() - start) < timeout:
            time.sleep(0.05)

        return {'connected': self.is_in_auction_room, 'room_id': room_id}

    def _handle_auction_message(self, data):
        """Default handler for auction messages."""
        msg_type = data.get('type')
        
        if msg_type == 'auction_state':
            print_border()
            print("AUCTION ROOM STATUS")
            if data.get('current_item'):
                item = data['current_item']
                print(f"Current Item: {item.get('card_name', 'Unknown')}")
                print(f"Seller: {item.get('seller_uuid', 'Unknown')}")
                print(f"Starting Bid: ${item.get('starting', 0)}")
                print(f"Buyout Price: ${item.get('buyout', 0)}")
            print(f"Current Bid: ${data.get('current_bid', 0)}")
            print(f"Current Winner: {data.get('current_winner', 'None')}")
            print(f"Time Remaining: {data.get('time_remaining', 0)}s")
            print(f"Queue Length: {data.get('queue_length', 0)}")
            print_border()
            
        elif msg_type == 'auction_started':
            item = data.get('item', {})
            print_border()
            print(" NEW AUCTION STARTED!")
            print(f"Item: {item.get('card_name', 'Unknown')}")
            print(f"Starting Bid: ${item.get('starting_bid', 0)}")
            print(f"Buyout: ${item.get('buyout_price', 0)}")
            print(f"Time Limit: {item.get('time_limit', 0)}s")
            print_border()
            
        elif msg_type == 'new_bid':
            print(f" New bid: ${data.get('amount', 0)} by {data.get('bidder', 'Unknown')}")
            
        elif msg_type == 'timer_update':
            remaining = data.get('time_remaining', 0)
            if remaining <= 10:
                print(f" WARNING: {remaining} seconds remaining!")
            
        elif msg_type == 'buyout':
            print_border()
            print(f" BUYOUT! {data.get('bidder', 'Unknown')} bought for ${data.get('amount', 0)}")
            print_border()
            
        elif msg_type == 'auction_won':
            print_border()
            print(f" AUCTION WON by {data.get('winner', 'Unknown')} for ${data.get('final_bid', 0)}")
            print(f"Item: {data.get('item', 'Unknown')}")
            print_border()
            
        elif msg_type == 'auction_failed':
            print(f" Auction ended with no bids: {data.get('reason', '')}")
            
        elif msg_type == 'bid_error':
            print(f" Bid failed: {data.get('error', 'Unknown error')}")
            
        elif msg_type == 'timer_extended':
            print(f" Timer extended to {data.get('new_time', 10)} seconds!")

    def place_bid(self, amount: int):
        """Place a bid in the current auction room."""
        if not self.is_in_auction_room or not self._auction_ws_app:
            print_info("You are not in an auction room.")
            return {'error': 'not_connected'}

        payload = {
            "type": "bid",
            "amount": amount
        }
        try:
            self._auction_ws_app.send(json.dumps(payload))
            return {'sent': True}
        except Exception as e:
            print_info(f'Error sending bid: {e}')
            return {'error': str(e)}

    def leave_auction_room(self):
        """Leave the current auction room."""
        if self._auction_ws_app:
            self._auction_ws_app.close()
            self.is_in_auction_room = False
            self.current_auction_room_id = None
            return {'left': True}
        return {'error': 'not_in_room'}

def parse_twr_command(command: str):
    # parse commands
    #returns command, args
    command = command.strip().split()
    if not command:
        return None, None
    if command[0].lower() == 'chat':
        return 'chat', ' '.join(command[1:])
    if command[0].lower() == 'exit':
        return 'exit', None


def parse_auction_command(command: str):
    """Parse auction room commands."""
    command = command.strip().split()
    if not command:
        return None, None
    
    cmd = command[0].lower()
    
    if cmd == 'bid':
        if len(command) >= 2:
            try:
                amount = int(command[1])
                return 'bid', amount
            except ValueError:
                return 'invalid', "Bid amount must be a number"
        return 'invalid', "Usage: bid <amount>"
    
    elif cmd == 'status':
        return 'status', None
    
    elif cmd == 'exit':
        return 'exit', None
    
    elif cmd == 'help':
        return 'help', None
    
    return 'invalid', f"Unknown command: {cmd}"

def auction_room_interface(main_client: MainClient):
    """Interactive interface for auction room."""
    print_info(f"Entered auction room {main_client.current_auction_room_id}")
    print_info("Commands:")
    print_info("  bid <amount> - Place a bid")
    print_info("  status - Request current auction status")
    print_info("  help - Show commands")
    print_info("  exit - Leave auction room")
    print_border()
    
    while main_client.is_in_auction_room:
        try:
            user_input = input("Auction> ")
            command, args = parse_auction_command(user_input)
            
            if command == 'bid':
                response = main_client.place_bid(args)
                if "error" in response:
                    print(f"Error placing bid: {response['error']}")
                    
            elif command == 'status':
                # Request status update (you could send a status request message)
                print("Requesting auction status...")
                
            elif command == 'help':
                print("Commands: bid <amount>, status, help, exit")
                
            elif command == 'exit':
                main_client.leave_auction_room()
                print("Left auction room.")
                break
                
            elif command == 'invalid':
                print(f"Error: {args}")
                
        except KeyboardInterrupt:
            print("\nLeaving auction room...")
            main_client.leave_auction_room()
            break
        except Exception as e:
            print(f"Error: {e}")


def auction_house_menu(main_client: MainClient):
    """Auction house sub-menu."""
    while True:
        print_border()
        print("AUCTION HOUSE")
        print_border()
        print("1. View All Auction Rooms")
        print("2. List Item for Auction")
        print("3. Join Auction Room")
        print("4. Back to Main Menu")
        
        choice = input("Enter choice (1-4): ")
        
        if choice == '1':
            response = main_client.get_auction_rooms()
            if "rooms" in response:
                print_border()
                print("AUCTION ROOMS STATUS")
                print_border()
                for room in response['rooms']:
                    status = "🔴" if room['active'] else "🟢"
                    print(f"{status} Room {room['room_id']}: {room['listing_name']}")
                    print(f"   Participants: {room['participants']}")
                    print(f"   Queue: {room['queue_length']} items")
                    if room['active']:
                        print(f"   Current Bid: ${room.get('current_bid', 0)}")
                        print(f"   Time Left: {room.get('time_remaining', 0)}s")
                    print()
                print_border()
            else:
                print(f"Error: {response}")
                
        elif choice == '2':
            # First show user's cards
            cards_response = main_client.get_my_cards()
            if "cards" not in cards_response or not cards_response['cards']:
                print("You don't have any cards to auction!")
                continue
                
            print("\nYour Cards:")
            for i, card in enumerate(cards_response['cards']):
                print(f"{i+1}. [{card['rarity'].upper()}] {card['card_name']} x{card['qty']}")
            
            try:
                card_idx = int(input("Select card number to auction: ")) - 1
                if card_idx < 0 or card_idx >= len(cards_response['cards']):
                    print("Invalid selection")
                    continue
                    
                selected_card = cards_response['cards'][card_idx]
                card_name = selected_card.get('card_name')  
                print(card_name)
                
                starting_bid = int(input("Starting bid: $"))
                buyout_price = int(input("Buyout price: $"))
                time_limit = int(input("Time limit (seconds, default 300): ") or 300)
                
                response = main_client.list_item_for_auction(
                    card_name=card_name,
                    starting_bid=starting_bid,
                    buyout_price=buyout_price,
                    time_limit=time_limit
                )
                
                if response.get('success'):
                    print(f"Item listed in Room {response['room_id']}")
                    print(f"Queue position: {response['queue_position']}")
                else:
                    print(f"Error: {response}")
                    
            except ValueError:
                print("Invalid input")
                
        elif choice == '3':
            try:
                room_id = int(input("Enter room ID (0-9): "))
                if room_id < 0 or room_id > 9:
                    print("Invalid room ID")
                    continue
                    
                print(f"Connecting to auction room {room_id}...")
                response = main_client.join_auction_room(room_id)
                
                if response.get('connected'):
                    auction_room_interface(main_client)
                else:
                    print("Failed to connect to auction room")
                    
            except ValueError:
                print("Invalid room ID")
                
        elif choice == '4':
            break
        else:
            print("Invalid choice")

def trade_wait_main(main_client_instance: MainClient):
    print_info("Entered trade waiting room. You can send your commands now!")
    print_info("Type 'exit' to leave the trade waiting room.")
    print_info("Type chat, followed by your message to chat.")
    while True:
        # stall on input:
        message = None
        message = input("Enter message to send in trade waiting room (or 'exit' to quit): ")
        command, args = parse_twr_command(message)
        if command == 'exit':
            main_client_instance._ws_app.close()
            break
        elif command == 'chat':
            send_response = main_client_instance.send_trade_message(args)
            if "error" in send_response:
                print(f"Error sending message: {send_response['error']}")
        else:
            print_info("Unknown command. Please use 'chat <message>' or 'exit'.")

def main():
    client = SignInClient(base_url="http://localhost:8000")
    # get user input for new user;
    # ask users to create a new account or sign in
    print_border()
    print("Client v 1.0.0")
    print_border()

    # choose a sign in option
    print_startup_message()
    while True:
        try:
            choice = input("Enter choice (1 or 2): ")
            choice_int = int(choice)
            if choice_int in [1, 2]:
                break
            else:
                print("Invalid choice. Please enter 1 or 2.")
        
        except ValueError:
            print("Invalid input. Please enter a valid integer.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    if choice_int == 1:
        username = input("Enter username: ")
        email = input("Enter email: ")
        password = input("Enter password: ")
        response = client.create_user(username, email, password)
        if "error" in response:
            print(f"Error creating user: {response['error']}")
            exit(1)
        if "message" in response:
            print(f"Success: {response['message']}")
            print("Please restart and log-in with your credentials.")
            exit(0)

    elif choice_int == 2:
        email = input("Enter email: ")
        password = input("Enter password: ")
        response = client.login_user(email, password)
        if "error" in response:
            print(f"Error logging in: {response['error']}")
            exit(1)
        if "message" in response:
            print(f"Success: {response['message']}")
            print("You are now logged in.")



    # loop on for the main client

    main_client = MainClient(
        base_url="http://localhost:8000", 
        logged_email=response['email']
    )
    # Set the UUID from the login response
    main_client.user_uuid = response['uuid']
    while True:
        # give us selection of options
        switch_case = {
            '1': 'Generate Card Pack (debug simple)',
            '2': 'Join Trade Waiting Room',
            '3': 'Open Card Pack',
            '4': 'View My Cards',
            '5': 'View My Packs',
            '6': 'Exit',
            '7': 'Auction House'
        }
        print("\nOptions:")
        for key, value in switch_case.items():
            print(f"{key}. {value}")
        choice = input("Enter choice (1-6): ")

        match choice:
            case '1':
                response = main_client.debug_create_pack()
                if "message" in response:
                    print(f"Success: {response['message']}")
            case '2':
                join_response = main_client.join_trade_waiting_room()
                if join_response.get("connected"):
                    print("Joined trade waiting room successfully.")
                    # goto trade wait main
                    trade_wait_main(main_client)
                else:
                    print("Failed to join trade waiting room.")
            case '3':
                response = main_client.debug_open_pack()
                if "error" in response:
                    print(f"Error: {response.get('message', response.get('error'))}")
                elif "cards" in response:
                    print_border()
                    print("You opened the following cards:")
                    print_border()
                    for card in response['cards']:
                        rarity_tag = f"[{card['rarity'].upper()}]"
                        print(f"  {rarity_tag} {card['name']}")
                    print_border()
                else:
                    print(f"Response: {response}")
            case '4':
                response = main_client.get_my_cards()
                if "error" in response:
                    print(f"Error: {response['error']}")
                elif "cards" in response:
                    total_cards = response.get('total_cards', 0)
                    total_unique = response.get('total_unique', 0)
                    print_border()
                    print(f"Your Card Collection ({total_cards} total, {total_unique} unique)")
                    print_border()
                    if response['cards']:
                        for card in response['cards']:
                            rarity_tag = f"[{card['rarity'].upper()}]"
                            print(f"  {rarity_tag} {card['card_name']} x{card['qty']}")
                    else:
                        print("  You don't have any cards yet. Open some packs!")
                    print_border()
                else:
                    print(f"Unexpected response: {response}")
            case '5':
                response = main_client.get_my_packs()
                if "error" in response:
                    print(f"Error: {response['error']}")
                elif "packs" in response:
                    total_packs = response.get('total_packs', 0)
                    print_border()
                    print(f"Your Pack Inventory ({total_packs} total)")
                    print_border()
                    if response['packs']:
                        for pack in response['packs']:
                            print(f"  [PACK] {pack['pack_name']} x{pack['qty']}")
                    else:
                        print("  You don't have any packs. Buy some!")
                    print_border()
                else:
                    print(f"Unexpected response: {response}")
            case '6':
                print("Goodbye!")
                exit(0)
            case '7':
                auction_house_menu(main_client)
if __name__ == "__main__":
    main()