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

    # basic init like above

    def __init__(self, base_url: str, logged_email:str):
        self.base_url = base_url
        self.email = logged_email
        self.session = requests.Session()
        self.is_in_waiting_room = False
        self._ws_app = None
        self._ws_thread = None

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

    main_client = MainClient(base_url="http://localhost:8000", logged_email=response['email'])
    while True:
        # give us selection of options
        switch_case = {
            '1': 'Generate Card Pack (debug simple)',
            '2': 'Join Trade Waiting Room',
            '3': 'Open Card (debug simple)',
            '4': 'Exit'
        }
        print("Options:")
        for key, value in switch_case.items():
            print(f"{key}. {value}")
        choice = input("Enter choice (1-4): ")

        match choice:
            case '1':
                response = main_client.debug_create_pack()
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

        #
if __name__ == "__main__":
    main()