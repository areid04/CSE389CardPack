# CSE 389 Card Pack Trading Game

A multiplayer card collecting and trading platform with pack opening, marketplace, and auction features.

## Prerequisites

This project uses **uv** as the Python package manager. Install uv before proceeding:

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After installation, restart your terminal or run `source ~/.bashrc` (Linux) / `source ~/.zshrc` (macOS) to ensure `uv` is available in your PATH.

## Installation

Clone the repository and install dependencies:

```bash
git clone <repository-url>
cd <project-directory>
uv sync
```

This will create a virtual environment and install all dependencies from `pyproject.toml`.

## Server Configuration

### Using the Deployed Server (Default)

The client is configured to connect to our deployed server by default. If the server appears offline or unreachable, please contact **areid04** for assistance.

### Running a Local Server

If the deployed server is unavailable, you can run everything locally:

1. **Update the client configuration** in `frontend_components/client.py`:

   Comment out the deployed URL and uncomment the localhost URL in both locations:

   ```python
   # In SignInClient initialization (around line 378):
   # client = SignInClient(base_url="https://cse389cardpack-shy-thunder-4126.fly.dev/")
   client = SignInClient(base_url="http://localhost:8000")

   # In MainClient initialization (around line 405):
   # main_client = MainClient(base_url="https://cse389cardpack-shy-thunder-4126.fly.dev", ...)
   main_client = MainClient(base_url="http://localhost:8000", ...)
   ```

2. **Start the local server:**

   ```bash
   uv run uvicorn server_components.server:app --reload
   ```

   The server will start at `http://localhost:8000`. The `--reload` flag enables auto-reload during development.

3. **Database Note:** When running locally, the application uses the SQLite database file already present in the repository. Any changes (new users, cards, transactions) will persist in this local database.

## Running the Client

With the server running (either deployed or local), start the CLI client:

```bash
uv run python frontend_components/client.py
```

## Client Features

Upon launching the client, you will be prompted to either create a new account or log in with existing credentials. New accounts receive a starting balance of $100 and one random starter pack.

### Main Menu Options

| Option | Feature | Description |
|--------|---------|-------------|
| **1** | Generate Card Pack (Debug) | Select from available pack types to add directly to your inventory. This is a debug feature left in for testing purposes. |
| **2** | Banking | View your current account balance. |
| **3** | Open Card Pack | Browse your pack inventory with pagination support. Select a pack to open and receive cards with an animated reveal. |
| **4** | View My Cards | Display your complete card collection showing card names, rarities, and quantities owned. |
| **5** | View My Packs | View all unopened packs in your inventory with quantities. |
| **6** | Auction House | Access the real-time auction system (see details below). |
| **7** | Marketplace | Buy and sell cards at fixed prices (see details below). |
| **8** | Exit | Close the application. |

### Auction House

The auction house provides real-time bidding via WebSocket connections:

- **View All Auction Rooms** - See status of all 10 auction rooms including active auctions, current bids, and queue lengths.
- **List Item for Auction** - Select a card from your collection and set starting bid, buyout price, and time limit.
- **Join Auction Room** - Connect to a room to participate in live auctions.

When in an auction room, use these commands:
- `bid <amount>` - Place a bid on the current item
- `status` - Request current auction state
- `help` - Show available commands
- `exit` - Leave the auction room

Auction mechanics include automatic timer extension when bids are placed in the final 10 seconds, and instant buyout functionality.

### Marketplace

The marketplace allows fixed-price trading:

- **Search Market** - Filter listings by price range, rarities, and card names.
- **List Item for Sale** - Select a card from your inventory and set a price.
- **Buy Item** - Browse available listings and purchase cards directly.

### Daily Login Bonus

Users receive a $100 bonus once per day upon logging in.

## API Documentation

When running the server locally, interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Troubleshooting

**"Connection refused" errors:**
- Ensure the server is running before starting the client
- Verify you're using the correct base URL (deployed vs localhost)

**"User not found" on login:**
- Create a new account first using option 1 at startup

**Deployed server unreachable:**
- Contact areid04 for server status
- Switch to local server configuration as described above

## Project Structure

```
├── frontend_components/
│   └── client.py          # CLI client application
├── server_components/
│   ├── server.py          # FastAPI server
│   ├── card_utils/        # Card and pack logic
│   └── utils/             # Database access utilities
├── pack_json/             # Pack definition files
├── server_logs/           # Logging configuration
└── pyproject.toml         # Project dependencies
```
