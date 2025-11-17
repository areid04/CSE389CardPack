# pretty print display stuff

# get creative w/ stuff like this
def print_info(message: str):
    print(f"[INFO]: {message}")

def print_border():
    print("=" * 40)
    print()

def print_startup_message():
    print_border()
    print("Welcome to the Client Application!")
    print("Please select an option to continue:")
    print("1. Create a new account")
    print("2. Sign in to existing account")
    print_border()