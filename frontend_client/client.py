import requests
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



    # loop on true as a kind of like

if __name__ == "__main__":
    main()