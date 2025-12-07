from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
from datetime import datetime
from server_components.card_utils.card import Card
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from dataclasses import dataclass, field
from collections import deque
from typing import Dict, Optional, Set
import asyncio
import json
import uuid
from datetime import datetime

from pydantic import BaseModel

# import dataclasses
from server_components.server_classes import CreateUser, LoginUser, Email, OpenPackRequest, AddPackRequest

# import our DB access functions
from server_components.utils.db_access import (
    init_db, 
    get_user_by_email, 
    get_user_by_username, 
    create_user_entry,
    add_cards_to_collection,
    get_user_cards,
    get_user_inventory,
    open_pack_for_user,
    add_pack_to_inventory,
    get_available_packs,
    scan_and_register_packs,
    change_money,
    exchange_money,
    create_bank_account
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (unsafe for big production, perfect for this)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# startup functions
@app.on_event("startup")
async def startup_event():
    # Initialize the SQLite DB defined in the schema
    init_db()
    
    # Auto-register any new packs from pack_json directory
    from pathlib import Path
    pack_json_dir = Path(__file__).parent / "pack_json"
    if pack_json_dir.exists():
        results = scan_and_register_packs(pack_json_dir)
        if results["added"]:
            print(f"Auto-registered {len(results['added'])} new pack(s): {', '.join(results['added'])}")
        elif results["errors"]:
            print(f"Pack registration errors: {results['errors']}")

@app.get("/")
async def read_root():
    return {"Hello": "World"}

@app.post("/login")
async def login_user(user: LoginUser):
    # check that there is an email and password otherwise fail
    if not user.email or not user.password:
        return JSONResponse(status_code=400, content={"error": "Missing email or password"})
    
    # Query the SQLite DB
    existing_user = get_user_by_email(user.email)
    
    if not existing_user:
        return JSONResponse(status_code=404, content={"error": "User not found"})
    else:
        # In production, compare hashes, not plain text
        if existing_user['password'] != user.password:
            return JSONResponse(status_code=401, content={"error": "Incorrect password"})
        else:
            return JSONResponse(status_code=200, content={
                "message": "Login successful", 
                "uuid": existing_user['uuid'],
                "username": existing_user['username'],
                "email": existing_user['email']
            })

# Add this near the top of server.py with other imports/constants
STARTING_BALANCE = 100

@app.post("/signup")
async def signup_user(user: CreateUser):
    # check that there is a username, email, and password otherwise fail
    if not user.username or not user.email or not user.password:
        return JSONResponse(status_code=400, content={"error": "Missing username, email, or password"})

    # Check if username exists in DB
    if get_user_by_username(user.username):
        return JSONResponse(status_code=400, content={"error": "Username already exists"})
    
    # Check if email exists in DB
    if get_user_by_email(user.email):
        return JSONResponse(status_code=400, content={"error": "Email already registered"})

    # Prepare data for Users table
    # Schema: username, uuid, email, password, is_admin (defaults to 0 in DB)
    new_uuid = str(uuid.uuid4())
    
    user_data = {
        'username': user.username,
        'uuid': new_uuid,
        'email': user.email,
        'password': user.password, # TODO: hash password before storing
        'is_admin': 0
    }
    
    success = create_user_entry(user_data)

    if not success:
        return JSONResponse(status_code=500, content={"error": "Failed to create user"})

    # Create bank account for new user
    create_bank_account(new_uuid, STARTING_BALANCE)

    # Give new user a random starter pack
    import random
    available = get_available_packs()
    if available:
        pack_name = random.choice(list(available.keys()))
        pack_path = available[pack_name]
        add_pack_to_inventory(new_uuid, pack_name, pack_path)

    return JSONResponse(status_code=201, content={
        "message": "User created successfully", 
        "uuid": new_uuid,
    })


# debug example endpoint - will be replaced with marketplace
@app.post("/gen_default_pack")
async def debug_gen(email: Email):
    import random
    row = get_user_by_email(email.email)
    if not row:
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    # Randomly pick from available packs
    available = get_available_packs()
    if not available:
        return JSONResponse(status_code=500, content={"error": "No packs available"})
    
    pack_name = random.choice(list(available.keys()))
    pack_path = available[pack_name]
    
    add_pack_to_inventory(row['uuid'], pack_name, pack_path)
    return JSONResponse(status_code=201, content={
        "message": f"Pack added successfully",
        "pack_name": pack_name
    })


@app.post("/add_pack")
async def add_pack(req: AddPackRequest):
    """Add a specific pack type to user's inventory."""
    row = get_user_by_email(req.email)
    if not row:
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    available = get_available_packs()
    if req.pack_name not in available:
        return JSONResponse(status_code=400, content={
            "error": f"Invalid pack name. Available packs: {list(available.keys())}"
        })
    
    pack_path = available[req.pack_name]
    success = add_pack_to_inventory(row['uuid'], req.pack_name, pack_path)
    
    if success:
        return JSONResponse(status_code=201, content={
            "message": f"{req.pack_name} added to inventory"
        })
    else:
        return JSONResponse(status_code=500, content={"error": "Failed to add pack"})


@app.get("/available_packs")
async def list_available_packs():
    """List all pack types available for purchase."""
    return JSONResponse(status_code=200, content={
        "packs": list(get_available_packs().keys())
    })


@app.post("/admin/register_packs")
async def register_packs_from_directory():
    """
    Admin endpoint: Scan pack_json directory and register any new packs.
    Returns stats about packs added, skipped, and errors.
    """
    from pathlib import Path
    
    # Get the pack_json directory path
    pack_json_dir = Path(__file__).parent / "pack_json"
    
    if not pack_json_dir.exists():
        return JSONResponse(status_code=500, content={
            "error": "pack_json directory not found"
        })
    
    results = scan_and_register_packs(pack_json_dir)
    
    return JSONResponse(status_code=200, content={
        "message": "Pack registration complete",
        "added": results["added"],
        "skipped": results["skipped"],
        "errors": results["errors"],
        "summary": {
            "added_count": len(results["added"]),
            "skipped_count": len(results["skipped"]),
            "error_count": len(results["errors"])
        }
    })


@app.post("/open_pack")
async def open_pack(req: OpenPackRequest):
    """Open a pack. If pack_name provided, opens that type. Otherwise opens most recent."""
    row = get_user_by_email(req.email)
    if not row:
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    pack_result = open_pack_for_user(row['uuid'], req.pack_name)
    
    if not pack_result:
        if req.pack_name:
            return JSONResponse(status_code=400, content={
                "error": f"You don't have any '{req.pack_name}' packs"
            })
        else:
            return JSONResponse(status_code=400, content={
                "error": "You don't have any packs to open"
            })
    
    from server_components.card_utils.pack_utils import pack_from_path
    pack = pack_from_path(pack_result['pack_path'])
    cards = pack.open_pack()
    
    # Save opened cards to user's collection
    add_cards_to_collection(row['uuid'], cards)
    
    # Convert cards to JSON-serializable format
    cards_data = [{"card_name": card.card_name, "rarity": card.rarity} for card in cards]
    
    return JSONResponse(status_code=201, content={
        "message": "Opened Pack Successfully",
        "pack_name": pack_result['pack_name'],
        "cards": cards_data
    })


@app.post("/my_cards")
async def get_my_cards(email: Email):
    """Get all cards owned by a user."""
    row = get_user_by_email(email.email)
    if not row:
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    cards = get_user_cards(row['uuid'])
    return JSONResponse(status_code=200, content={
        "cards": cards,
        "total_unique": len(cards),
        "total_cards": sum(card['qty'] for card in cards)
    })


@app.post("/my_packs")
async def get_my_packs(email: Email):
    """Get all packs owned by a user."""
    row = get_user_by_email(email.email)
    if not row:
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    packs = get_user_inventory(row['uuid'])
    return JSONResponse(status_code=200, content={
        "packs": packs,
        "total_packs": sum(pack['qty'] for pack in packs)
    })



class ChangeMoneyRequest(BaseModel):
    email: str
    amount: int

class ExchangeMoneyRequest(BaseModel):
    giver_email: str
    taker_email: str
    amount: int

class GetBalanceRequest(BaseModel):
    email: str


# Debug endpoints for banking functions

@app.post("/debug/get_balance")
async def debug_get_balance(req: GetBalanceRequest):
    """Get a user's current balance."""
    row = get_user_by_email(req.email)
    if not row:
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    from server_components.utils.db_access import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT money FROM Bank WHERE uuid = ?", (row['uuid'],))
        bank_row = cursor.fetchone()
        if not bank_row:
            return JSONResponse(status_code=404, content={"error": "Bank account not found"})
        return JSONResponse(status_code=200, content={
            "email": req.email,
            "uuid": row['uuid'],
            "money": bank_row['money']
        })
    finally:
        conn.close()


@app.post("/debug/change_money")
async def debug_change_money(req: ChangeMoneyRequest):
    """Add or remove money from a user's account. Use negative amounts to subtract."""
    row = get_user_by_email(req.email)
    if not row:
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    from server_components.utils.db_access import change_money
    success = change_money(req.amount, row['uuid'])
    
    if success:
        return JSONResponse(status_code=200, content={
            "message": f"Balance changed by {req.amount}",
            "uuid": row['uuid']
        })
    else:
        return JSONResponse(status_code=400, content={
            "error": "Transaction failed (insufficient balance or account not found)"
        })


@app.post("/debug/exchange_money")
async def debug_exchange_money(req: ExchangeMoneyRequest):
    """Transfer money from one user to another."""
    giver = get_user_by_email(req.giver_email)
    taker = get_user_by_email(req.taker_email)
    
    if not giver:
        return JSONResponse(status_code=404, content={"error": "Giver not found"})
    if not taker:
        return JSONResponse(status_code=404, content={"error": "Taker not found"})
    if req.amount <= 0:
        return JSONResponse(status_code=400, content={"error": "Amount must be positive"})
    
    from server_components.utils.db_access import exchange_money
    success = exchange_money(giver['uuid'], taker['uuid'], req.amount)
    
    if success:
        return JSONResponse(status_code=200, content={
            "message": f"Transferred {req.amount} from {req.giver_email} to {req.taker_email}",
            "giver_uuid": giver['uuid'],
            "taker_uuid": taker['uuid']
        })
    else:
        return JSONResponse(status_code=400, content={
            "error": "Transfer failed (insufficient balance or account not found)"
        })


@app.post("/debug/set_balance")
async def debug_set_balance(req: ChangeMoneyRequest):
    """Directly set a user's balance (bypasses checks - debug only)."""
    row = get_user_by_email(req.email)
    if not row:
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    from server_components.utils.db_access import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE Bank SET balance = ? WHERE uuid = ?
        """, (req.amount, row['uuid']))
        conn.commit()
        return JSONResponse(status_code=200, content={
            "message": f"Balance set to {req.amount}",
            "uuid": row['uuid']
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        conn.close()

@dataclass
class AuctionItem:
    card: Card
    seller_uuid: str
    ttl: int  # seconds
    buyout: int
    starting: int

@dataclass
class BidMessage:
    bidder_uuid: str
    amount: int
    timestamp: datetime

class AuctionRoom:
    def __init__(self, assigned_id: int):
        self.auc_list = deque([])
        self.id = assigned_id
        
        self.current_item: Optional[AuctionItem] = None
        self.time_remaining: int = 0
        self.timer_task: Optional[asyncio.Task] = None
        
        self.current_bid = 0
        self.current_winning_bidder: Optional[str] = None
        self.bid_history: list[BidMessage] = []
        
        # WebSocket connections mapped by user_uuid
        self.active_connections: Dict[str, WebSocket] = {}
        
        self.room_active = False
        self.listing_name = self._update_listing_name()
    
    def _update_listing_name(self) -> str:
        if self.current_item:
            return f"Auction Room {self.id} | Selling {self.current_item.card.name}"
        return f"Auction Room {self.id} | Open"
    
    async def connect(self, websocket: WebSocket, user_uuid: str):
        """Add a new WebSocket connection to the room"""
        await websocket.accept()
        self.active_connections[user_uuid] = websocket
        
        # Send current auction state to new connection
        await self.send_current_state(user_uuid)
        
        # Notify others of new participant
        await self.broadcast({
            "type": "user_joined",
            "user_uuid": user_uuid,
            "total_participants": len(self.active_connections)
        }, exclude=user_uuid)
    
    async def disconnect(self, user_uuid: str):
        """Remove a WebSocket connection"""
        if user_uuid in self.active_connections:
            del self.active_connections[user_uuid]
            
        await self.broadcast({
            "type": "user_left",
            "user_uuid": user_uuid,
            "total_participants": len(self.active_connections)
        })
    
    async def send_current_state(self, user_uuid: str):
        """Send current auction state to a specific user"""
        if user_uuid not in self.active_connections:
            return
            
        state = {
            "type": "auction_state",
            "room_id": self.id,
            "current_item": {
                "card_name": self.current_item.card.name if self.current_item else None,
                #"card_id": self.current_item.card.id if self.current_item else None,
                "seller_uuid": self.current_item.seller_uuid if self.current_item else None,
                "buyout": self.current_item.buyout if self.current_item else None,
                "starting": self.current_item.starting if self.current_item else None,
            } if self.current_item else None,
            "current_bid": self.current_bid,
            "current_winner": self.current_winning_bidder,
            "time_remaining": self.time_remaining,
            "room_active": self.room_active,
            "queue_length": len(self.auc_list)
        }
        
        await self.active_connections[user_uuid].send_json(state)
    
    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        """Broadcast message to all connected clients"""
        disconnected = []
        for user_uuid, websocket in self.active_connections.items():
            if exclude and user_uuid == exclude:
                continue
            try:
                await websocket.send_json(message)
            except:
                disconnected.append(user_uuid)
        
        # Clean up disconnected clients
        for user_uuid in disconnected:
            await self.disconnect(user_uuid)
    
    async def countdown_timer(self):
        """Background task to handle auction timer"""
        while self.time_remaining > 0:
            await asyncio.sleep(1)
            self.time_remaining -= 1
            
            # Broadcast timer update every 5 seconds or when under 10 seconds
            if self.time_remaining % 5 == 0 or self.time_remaining <= 10:
                await self.broadcast({
                    "type": "timer_update",
                    "time_remaining": self.time_remaining
                })
        
        # Auction ended
        await self.end_current_auction()
    
    async def start_next_auction(self):
        """Start the next auction from the queue"""
        if not self.auc_list:
            self.room_active = False
            self.current_item = None
            await self.broadcast({
                "type": "room_idle",
                "message": "No items in queue"
            })
            return
        
        auction_item = self.auc_list.popleft()
        await self.setup(auction_item)
    
    async def setup(self, auction_item: AuctionItem):
        """Setup a new auction"""
        self.current_item = auction_item
        self.time_remaining = auction_item.ttl
        self.current_bid = auction_item.starting
        self.current_winning_bidder = None
        self.bid_history = []
        self.room_active = True
        self.listing_name = self._update_listing_name()
        
        # Cancel previous timer if exists
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        
        # Start countdown timer
        self.timer_task = asyncio.create_task(self.countdown_timer())
        
        # Notify all clients of new auction
        await self.broadcast({
            "type": "auction_started",
            "item": {
                "card_name": auction_item.card.name,
                #"card_id": auction_item.card.id,
                "seller_uuid": auction_item.seller_uuid,
                "starting_bid": auction_item.starting,
                "buyout_price": auction_item.buyout,
                "time_limit": auction_item.ttl
            }
        })
    
    async def place_bid(self, user_uuid: str, amount: int) -> dict:
        """Handle a bid from a user"""
        if not self.room_active:
            return {"success": False, "error": "No active auction"}
        
        if not self.current_item:
            return {"success": False, "error": "No item being auctioned"}
        
        # Validate: seller can't bid on their own item
        if user_uuid == self.current_item.seller_uuid:
            return {"success": False, "error": "Cannot bid on your own item"}
        
        # Validate: bid must be higher than current
        if amount <= self.current_bid:
            return {"success": False, "error": f"Bid must be higher than current bid of {self.current_bid}"}
        
        # Check for buyout
        if amount >= self.current_item.buyout:
            self.current_bid = self.current_item.buyout
            self.current_winning_bidder = user_uuid
            await self.broadcast({
                "type": "buyout",
                "bidder": user_uuid,
                "amount": self.current_item.buyout
            })
            await self.end_current_auction()
            return {"success": True, "buyout": True}
        
        # Regular bid
        self.current_bid = amount
        self.current_winning_bidder = user_uuid
        self.bid_history.append(BidMessage(user_uuid, amount, datetime.now()))
        
        # Extend timer if bid placed in last 10 seconds
        if self.time_remaining < 10:
            self.time_remaining = 10
            await self.broadcast({
                "type": "timer_extended",
                "new_time": 10
            })
        
        await self.broadcast({
            "type": "new_bid",
            "bidder": user_uuid,
            "amount": amount,
            "time_remaining": self.time_remaining
        })
        
        return {"success": True, "buyout": False}
    
    async def end_current_auction(self):
        """End the current auction and process the winner"""
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        
        if self.current_winning_bidder and self.current_item:
            # Winner found - you'll implement transaction later
            await self.broadcast({
                "type": "auction_won",
                "winner": self.current_winning_bidder,
                "final_bid": self.current_bid,
                "item": self.current_item.card.name
            })
            
            # Here you would call transact() once implemented
            
        else:
            # No bids
            await self.broadcast({
                "type": "auction_failed",
                "reason": "No bids received"
            })
        
        # Start next auction after delay
        await asyncio.sleep(5)
        await self.start_next_auction()
    
    def add_to_auc_queue(self, item: AuctionItem):
        """Add an item to the auction queue"""
        self.auc_list.append(item)
        if not self.room_active and not self.current_item:
            # Start auction if room is idle
            asyncio.create_task(self.start_next_auction())


class AuctionHouse:
    def __init__(self):
        self.rooms: Dict[int, AuctionRoom] = {}
        # Initialize 10 rooms
        for i in range(10):
            self.rooms[i] = AuctionRoom(i)
    
    def get_room_status(self) -> list:
        """Get status of all auction rooms"""
        return [
            {
                "room_id": room.id,
                "listing_name": room.listing_name,
                "active": room.room_active,
                "current_bid": room.current_bid if room.current_item else None,
                "participants": len(room.active_connections),
                "queue_length": len(room.auc_list),
                "time_remaining": room.time_remaining if room.room_active else None
            }
            for room in self.rooms.values()
        ]
    
    def get_available_room(self) -> Optional[int]:
        """Find the best room to add a new auction item"""
        # Prioritize rooms with shortest queues
        sorted_rooms = sorted(
            self.rooms.values(),
            key=lambda r: len(r.auc_list)
        )
        if sorted_rooms:
            return sorted_rooms[0].id
        return None


auction_house = AuctionHouse()

@app.get("/auction/rooms")
async def get_auction_rooms():
    """REST endpoint to get all auction room statuses"""
    return {
        "rooms": auction_house.get_room_status()
    }

from pydantic import BaseModel

class ListItemRequest(BaseModel):
    card_name: str
    seller_uuid: str
    starting_bid: int
    buyout_price: int
    time_limit: int = 300

@app.post("/auction/list-item")
async def list_item(request: ListItemRequest):
    """REST endpoint to list an item for auction"""
    # Get card from database 
    from server_components.utils.db_access import select_card_by_name
    card = select_card_by_name(request.seller_uuid, request.card_name)
    classed_card = Card(card["card_name"], card["rarity"])
    
    # Find best room for the item
    room_id = auction_house.get_available_room()
    if room_id is None:
        raise HTTPException(status_code=503, detail="No available auction rooms")
    
    auction_item = AuctionItem(
        card=classed_card,
        seller_uuid=request.seller_uuid,
        ttl=request.time_limit,
        buyout=request.buyout_price,
        starting=request.starting_bid
    )
    
    room = auction_house.rooms[room_id]
    room.add_to_auc_queue(auction_item)
    
    return {
        "success": True,
        "room_id": room_id,
        "queue_position": len(room.auc_list)
    }

@app.websocket("/auction/room/{room_id}")
async def websocket_auction_room(
    websocket: WebSocket,
    room_id: int,
    user_uuid: str
):
    """WebSocket endpoint for auction room"""
    if room_id not in auction_house.rooms:
        await websocket.close(code=4004, reason="Room not found")
        return
    
    room = auction_house.rooms[room_id]
    await room.connect(websocket, user_uuid)
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            
            if data["type"] == "bid":
                result = await room.place_bid(
                    user_uuid=user_uuid,
                    amount=data["amount"]
                )
                
                if not result["success"]:
                    await websocket.send_json({
                        "type": "bid_error",
                        "error": result["error"]
                    })
            
            elif data["type"] == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        await room.disconnect(user_uuid)


        



class ConnectionManager:
    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

# joining the live trade waiting room.
@app.websocket("/ws/trade_waiting_room")
async def websocket_trade_waiting_room(websocket: WebSocket):
    manager = ConnectionManager()
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # TODO: Integrate JWT or session lookup to get actual username
            user_display = "User" 
            
            print(f"{current_time} - {user_display}: {data}")
            await manager.broadcast(f"You wrote: {data}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("WebSocket connection closed")
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    # init_db is handled by the startup event, but can be called here if running script directly
    uvicorn.run(app, host="0.0.0.0", port=8000)