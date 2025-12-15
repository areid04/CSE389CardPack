from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
from datetime import datetime
from server_components.card_utils.card import Card
from dataclasses import dataclass, field
from collections import deque
from typing import Dict, Optional, Set
import asyncio
import json
import uuid
from datetime import datetime
from server_components.utils.db_access import give_daily_login_bonus


from pydantic import BaseModel

#logging stuff
from server_logs.loggers import server_logger, auction_logger, marketplace_logger
from server_logs.endpoints import router as logs_router
from server_logs.middleware import RequestLoggingMiddleware
from server_logs.loggers import server_logger, transaction_logger

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
    create_bank_account,
    querey_marketplace,
    add_to_marketplace,
    remove_from_marketplace,
    select_card_by_name
)

app = FastAPI()
app.include_router(logs_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

app.add_middleware(RequestLoggingMiddleware, logger=server_logger)

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
            
            #log code
            server_logger.info(
                "startup_packs_registered",
                count=len(results["added"]),
                packs=results["added"]
            )

        if results["errors"]:
            #log code
            server_logger.warning(
                "startup_pack_registration_errors",
                errors=results["errors"]
            )

@app.get("/")
async def read_root():
    return {"Hello": "World"}

@app.post("/login")
async def login_user(user: LoginUser):
    #logs for login attempt
    server_logger.info(
        "login_attempt",
        email=user.email
    )

    # check that there is an email and password otherwise fail
    if not user.email or not user.password:

        #log code
        server_logger.warning(
            "login_failed_missing_fields",
            email=user.email
        )

        return JSONResponse(status_code=400, content={"error": "Missing email or password"})
    
    # Query the SQLite DB
    existing_user = get_user_by_email(user.email)
    
    if not existing_user:

        #log code
        server_logger.warning(
            "login_failed_user_not_found",
            email=user.email
        )
        return JSONResponse(status_code=404, content={"error": "User not found"})
    else:
        # In production, compare hashes, not plain text
        if existing_user['password'] != user.password:
            
            #log code
            server_logger.warning(
            "login_failed_bad_password",
            email=user.email,
            user_uuid=existing_user["uuid"]
            )
            
            return JSONResponse(status_code=401, content={"error": "Incorrect password"})
        else:
            
            #log code
            server_logger.info(
                "login_success",
                user_uuid=existing_user["uuid"],
                username=existing_user["username"]
            )
            # Daily login bonus
            bonus_given = give_daily_login_bonus(existing_user['uuid'])
            if bonus_given:
                print(f"Daily login bonus awarded to {existing_user['username']}")
                
            response_content = {
                "message": "Login successful",
                "uuid": existing_user['uuid'],
                "username": existing_user['username'],
                "email": existing_user['email'],
                "daily_bonus": bonus_given
            }
            if bonus_given:
                response_content["bonus_amount"] = 100
        return JSONResponse(status_code=200, content=response_content)

STARTING_BALANCE = 100

@app.post("/signup")
async def signup_user(user: CreateUser):

    #log code
    server_logger.info(
        "signup_attempt",
        username=user.username,
        email=user.email
    )

    # check that there is a username, email, and password otherwise fail
    if not user.username or not user.email or not user.password:

        #log code
        server_logger.warning(
            "signup_failed_missing_fields",
            username=user.username,
            email=user.email
        )

        return JSONResponse(status_code=400, content={"error": "Missing username, email, or password"})

    # Check if username exists in DB
    if get_user_by_username(user.username):

        #log code
        server_logger.warning(
            "signup_failed_username_exists",
            username=user.username
        )

        return JSONResponse(status_code=400, content={"error": "Username already exists"})
    
    # Check if email exists in DB
    if get_user_by_email(user.email):

        #log code
        server_logger.warning(
            "signup_failed_email_exists",
            email=user.email
        )

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

        #log code
        server_logger.warning(
            "signup_attempt_fail",
            email=user.email
        )

        return JSONResponse(status_code=500, content={"error": "Failed to create user"})


    #log code (might be wrong spot?)
    server_logger.info(
        "signup_success",
        user_uuid=new_uuid,
        username=user.username
    )

    # Create bank account for new user
    create_bank_account(new_uuid, STARTING_BALANCE)

    # Give new user a random starter pack
    import random
    available = get_available_packs()
    if available:
        pack_name = random.choice(list(available.keys()))
        pack_path = available[pack_name]
        add_pack_to_inventory(new_uuid, pack_name, pack_path)

        #log code
        server_logger.info(
            "starter_pack_granted",
            user_uuid=new_uuid,
            pack_name=pack_name
        )

    return JSONResponse(status_code=201, content={
        "message": "User created successfully", 
        "uuid": new_uuid,
    })


# debug example endpoint - will be replaced with marketplace
@app.post("/gen_default_pack")
async def debug_gen(email: Email):
    import random

    #log code
    server_logger.info(
        "debug_gen_pack_invoked",
        email=email.email
    )

    row = get_user_by_email(email.email)
    if not row:
        
        #log code
        server_logger.warning(
            "debug_gen_pack_user_not_found",
            email=email.email
        )

        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    # Randomly pick from available packs
    available = get_available_packs()
    if not available:

        #log code
        server_logger.error(
            "debug_gen_pack_no_packs_available"
        )
        
        return JSONResponse(status_code=500, content={"error": "No packs available"})
    
    pack_name = random.choice(list(available.keys()))
    pack_path = available[pack_name]
    
    add_pack_to_inventory(row['uuid'], pack_name, pack_path)

    #log code
    server_logger.info(
        "debug_pack_granted",
        user_uuid=row["uuid"],
        pack_name=pack_name,
        email=email.email
    )

    return JSONResponse(status_code=201, content={
        "message": f"Pack added successfully",
        "pack_name": pack_name
    })


@app.post("/add_pack")
async def add_pack(req: AddPackRequest):
    """Add a specific pack type to user's inventory."""

    #log code
    server_logger.info(
        "add_pack_requested",
        email=req.email,
        pack_name=req.pack_name
    )

    
    row = get_user_by_email(req.email)
    if not row:

        #log code
        server_logger.warning(
            "add_pack_user_not_found",
            email=req.email
        )

        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    available = get_available_packs()
    if req.pack_name not in available:

        #log code
        server_logger.warning(
            "add_pack_invalid_pack_name",
            email=req.email,
            pack_name=req.pack_name
        )

        return JSONResponse(status_code=400, content={
            "error": f"Invalid pack name. Available packs: {list(available.keys())}"
        })
    
    pack_path = available[req.pack_name]
    success = add_pack_to_inventory(row['uuid'], req.pack_name, pack_path)
    
    if success:

        #log code
        server_logger.info(
            "add_pack_success",
            user_uuid=row["uuid"],
            pack_name=req.pack_name,
            email=req.email
        )

        return JSONResponse(status_code=201, content={
            "message": f"{req.pack_name} added to inventory"
        })
    else:

        #log code
        server_logger.error(
            "add_pack_inventory_write_failed",
            user_uuid=row["uuid"],
            pack_name=req.pack_name
        )

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
    
    #log code
    server_logger.info(
        "admin_register_packs_invoked"
    )

    # Get the pack_json directory path
    pack_json_dir = Path(__file__).parent / "pack_json"
    
    if not pack_json_dir.exists():

        #log code
        server_logger.error(
            "admin_register_packs_dir_not_found",
            path=str(pack_json_dir)
        )

        return JSONResponse(status_code=500, content={
            "error": "pack_json directory not found"
        })
    
    results = scan_and_register_packs(pack_json_dir)
    
    if results["errors"]:
        
        #log code
        server_logger.warning(
            "admin_register_packs_had_errors",
            errors=results["errors"]
        )

    #log code
    server_logger.info(
        "admin_register_packs_complete",
        added_count=len(results["added"]),
        skipped_count=len(results["skipped"]),
        error_count=len(results["errors"]),
        added=results["added"]
    )

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

    #log code
    server_logger.info(
        "open_pack_attempt",
        email=req.email,
        pack_name=req.pack_name
    )

    row = get_user_by_email(req.email)
    if not row:

        #log code
        server_logger.warning(
            "open_pack_user_not_found",
            email=req.email
        )

        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    pack_result = open_pack_for_user(row['uuid'], req.pack_name)
    
    if not pack_result:
        if req.pack_name:

            #log code
            server_logger.warning(
                "open_pack_specific_pack_not_owned",
                user_uuid=row["uuid"],
                pack_name=req.pack_name
            )

            
            return JSONResponse(status_code=400, content={
                "error": f"You don't have any '{req.pack_name}' packs"
            })
        else:

            #log code
            server_logger.warning(
                "open_pack_no_packs_owned",
                user_uuid=row["uuid"]
            )

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
    
    #log code
    server_logger.info(
        "open_pack_success",
        user_uuid=row["uuid"],
        pack_name=pack_result["pack_name"],
        cards_received=len(cards_data)
    )
    
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

    #log code
    server_logger.info(
        "debug_get_balance_attempt",
        email=req.email
    )

    row = get_user_by_email(req.email)
    if not row:

        #log code
        server_logger.warning(
            "debug_get_balance_user_not_found",
            email=req.email
        )

        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    from server_components.utils.db_access import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT money FROM Bank WHERE uuid = ?", (row['uuid'],))
        bank_row = cursor.fetchone()
        if not bank_row:

            #log code
            server_logger.warning(
                "debug_get_balance_bank_account_not_found",
                user_uuid=row["uuid"],
                email=req.email
            )

            return JSONResponse(status_code=404, content={"error": "Bank account not found"})
        
        #log code
        server_logger.info(
            "debug_get_balance_success",
            user_uuid=row["uuid"],
            balance=bank_row["money"]
        )
        
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

    #log code
    server_logger.info(
        "debug_change_money_attempt",
        email=req.email,
        amount=req.amount
    )

    row = get_user_by_email(req.email)
    if not row:

        #log code
        server_logger.warning(
            "debug_change_money_user_not_found",
            email=req.email
        )


        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    from server_components.utils.db_access import change_money
    success = change_money(req.amount, row['uuid'])
    
    if success:

        #log code
        server_logger.info(
            "debug_change_money_success",
            user_uuid=row["uuid"],
            amount=req.amount
        )

        return JSONResponse(status_code=200, content={
            "message": f"Balance changed by {req.amount}",
            "uuid": row['uuid']
        })
    else:

        #log code
        server_logger.warning(
            "debug_change_money_failed",
            user_uuid=row["uuid"],
            amount=req.amount
        )

        return JSONResponse(status_code=400, content={
            "error": "Transaction failed (insufficient balance or account not found)"
        })


@app.post("/debug/exchange_money")
async def debug_exchange_money(req: ExchangeMoneyRequest):
    """Transfer money from one user to another."""

    #log code
    server_logger.info(
        "debug_exchange_money_attempt",
        giver_email=req.giver_email,
        taker_email=req.taker_email,
        amount=req.amount
    )

    giver = get_user_by_email(req.giver_email)
    taker = get_user_by_email(req.taker_email)
    
    if not giver:

        #log code
        server_logger.warning(
            "debug_exchange_money_giver_not_found",
            giver_email=req.giver_email
        )

        return JSONResponse(status_code=404, content={"error": "Giver not found"})
    if not taker:

        #log code
        server_logger.warning(
            "debug_exchange_money_taker_not_found",
            taker_email=req.taker_email
        )

        return JSONResponse(status_code=404, content={"error": "Taker not found"})
    if req.amount <= 0:

        #log code
        server_logger.warning(
            "debug_exchange_money_invalid_amount",
            giver_uuid=giver["uuid"],
            taker_uuid=taker["uuid"],
            amount=req.amount
        )

        return JSONResponse(status_code=400, content={"error": "Amount must be positive"})
    
    from server_components.utils.db_access import exchange_money
    success = exchange_money(giver['uuid'], taker['uuid'], req.amount)
    
    if success:

        #log code
        server_logger.info(
            "debug_exchange_money_success",
            giver_uuid=giver["uuid"],
            taker_uuid=taker["uuid"],
            amount=req.amount
        )

        return JSONResponse(status_code=200, content={
            "message": f"Transferred {req.amount} from {req.giver_email} to {req.taker_email}",
            "giver_uuid": giver['uuid'],
            "taker_uuid": taker['uuid']
        })
    else:

        #log code
        server_logger.warning(
            "debug_exchange_money_failed",
            giver_uuid=giver["uuid"],
            taker_uuid=taker["uuid"],
            amount=req.amount
        )

        return JSONResponse(status_code=400, content={
            "error": "Transfer failed (insufficient balance or account not found)"
        })


@app.post("/debug/set_balance")
async def debug_set_balance(req: ChangeMoneyRequest):
    """Directly set a user's balance (bypasses checks - debug only)."""

    #log code
    server_logger.info(
        "debug_set_balance_attempt",
        email=req.email,
        amount=req.amount
    )

    row = get_user_by_email(req.email)
    if not row:

        #log code
        server_logger.warning(
            "debug_set_balance_user_not_found",
            email=req.email
        )

        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    from server_components.utils.db_access import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE Bank SET balance = ? WHERE uuid = ?
        """, (req.amount, row['uuid']))
        conn.commit()

        #log code
        server_logger.info(
            "debug_set_balance_success",
            user_uuid=row["uuid"],
            new_balance=req.amount
        )

        return JSONResponse(status_code=200, content={
            "message": f"Balance set to {req.amount}",
            "uuid": row['uuid']
        })
    except Exception as e:

        #log code
        server_logger.error(
            "debug_set_balance_error",
            user_uuid=row["uuid"],
            amount=req.amount,
            error=str(e)
        )

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
    # AuctionRoom manages a simple in-memory FIFO auction queue. Each room
    # holds a queue of AuctionItem objects, runs a countdown for the active
    # item, collects bids, and settles the winner when time expires.
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
            return f"Auction Room {self.id} | Selling {self.current_item.card.card_name}"
        return f"Auction Room {self.id} | Open"
    
    async def connect(self, websocket: WebSocket, user_uuid: str):
        """Add a new WebSocket connection to the room"""
        await websocket.accept()
        self.active_connections[user_uuid] = websocket
        
        #log code
        auction_logger.info(
            "auction_room_user_connected",
            room_id=self.id,
            user_uuid=user_uuid,
            total_participants=len(self.active_connections)
        )

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
        
        #log code
        auction_logger.info(
            "auction_room_user_disconnected",
            room_id=self.id,
            user_uuid=user_uuid,
            total_participants=len(self.active_connections)
        )

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
                "card_name": self.current_item.card.card_name if self.current_item else None,
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

            #log code
            auction_logger.info(
                "auction_room_idle",
                room_id=self.id
            )

            await self.broadcast({
                "type": "room_idle",
                "message": "No items in queue"
            })
            return
        
        auction_item = self.auc_list.popleft()

        #log code
        auction_logger.info(
            "auction_starting_next",
            room_id=self.id,
            card_name=auction_item.card.card_name,
            seller_uuid=auction_item.seller_uuid,
            starting_bid=auction_item.starting,
            queue_remaining=len(self.auc_list)
        )
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
        
        #log code
        auction_logger.info(
            "auction_started",
            room_id=self.id,
            card_name=auction_item.card.card_name,
            seller_uuid=auction_item.seller_uuid,
            starting_bid=auction_item.starting,
            buyout_price=auction_item.buyout,
            time_limit=auction_item.ttl
        )

        # Notify all clients of new auction
        await self.broadcast({
            "type": "auction_started",
            "item": {
                "card_name": auction_item.card.card_name,
                #"card_id": auction_item.card.id,
                "seller_uuid": auction_item.seller_uuid,
                "starting_bid": auction_item.starting,
                "buyout_price": auction_item.buyout,
                "time_limit": auction_item.ttl
            }
        })
    
    async def place_bid(self, user_uuid: str, amount: int) -> dict:
        """Handle a bid from a user"""

        #log code
        auction_logger.info(
            "bid_attempt",
            room_id=self.id,
            user_uuid=user_uuid,
            amount=amount
        )

        if not self.room_active:

            #log code
            auction_logger.warning(
                "bid_failed_no_active_auction",
                room_id=self.id,
                user_uuid=user_uuid
            )

            return {"success": False, "error": "No active auction"}
        
        if not self.current_item:
            #log code
            auction_logger.warning(
                "bid_failed_no_item",
                room_id=self.id,
                user_uuid=user_uuid
            )
            return {"success": False, "error": "No item being auctioned"}
        
        # Validate: seller can't bid on their own item
        if user_uuid == self.current_item.seller_uuid:

            #log code
            auction_logger.warning(
                "bid_failed_self_bid",
                room_id=self.id,
                user_uuid=user_uuid,
                card_name=self.current_item.card.card_name
            )
            return {"success": False, "error": "Cannot bid on your own item"}
        
        # Validate: bid must be higher than current
        if amount <= self.current_bid:

            #log code
            auction_logger.warning(
                "bid_failed_too_low",
                room_id=self.id,
                user_uuid=user_uuid,
                amount=amount,
                current_bid=self.current_bid
            )
            return {"success": False, "error": f"Bid must be higher than current bid of {self.current_bid}"}
        
        # Check for buyout
        if amount >= self.current_item.buyout:
            self.current_bid = self.current_item.buyout
            self.current_winning_bidder = user_uuid

            #log code
            auction_logger.info(
                "bid_buyout",
                room_id=self.id,
                user_uuid=user_uuid,
                amount=self.current_item.buyout,
                card_name=self.current_item.card.card_name
            )

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

            #log code
            auction_logger.info(
                "bid_timer_extended",
                room_id=self.id,
                user_uuid=user_uuid
            )

            await self.broadcast({
                "type": "timer_extended",
                "new_time": 10
            })
        #log code
        auction_logger.info(
            "bid_success",
            room_id=self.id,
            user_uuid=user_uuid,
            amount=amount,
            card_name=self.current_item.card.card_name
        )

        await self.broadcast({
            "type": "new_bid",
            "bidder": user_uuid,
            "amount": amount,
            "time_remaining": self.time_remaining
        })
        
        return {"success": True, "buyout": False}
    
    async def end_current_auction(self):
        """End the current auction and process the winner"""

        #log code
        auction_logger.info(
            "auction_ending",
            room_id=self.id,
            card_name=self.current_item.card.card_name if self.current_item else None,
            final_bid=self.current_bid,
            winner_uuid=self.current_winning_bidder
        )    
        
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        
        # Capture current state locally so we can reset the room immediately
        curr_item = self.current_item
        curr_winner = self.current_winning_bidder
        curr_bid = self.current_bid

        # Reset room so new listings can be queued/started immediately
        self.current_item = None
        self.room_active = False
        self.listing_name = self._update_listing_name()

        if curr_winner and curr_item:
            # Broadcast that the auction was won
            await self.broadcast({
                "type": "auction_won",
                "winner": curr_winner,
                "final_bid": curr_bid,
                "item": curr_item.card.card_name
            })

            # Attempt to transfer funds from winner -> seller, then transfer card ownership
            seller_uuid = curr_item.seller_uuid
            winner_uuid = curr_winner
            final_amount = int(curr_bid)

            try:
                # Local import to avoid circular imports at module level
                from server_components.utils.db_access import exchange_money, change_card_ownership

                # Winner pays seller
                paid = exchange_money(winner_uuid, seller_uuid, final_amount)
                if not paid:

                    #log code
                    auction_logger.error(
                        "auction_settlement_failed_insufficient_funds",
                        room_id=self.id,
                        winner_uuid=winner_uuid,
                        seller_uuid=seller_uuid,
                        amount=final_amount,
                        card_name=curr_item.card.card_name
                    )

                    # Insufficient funds — notify participants
                    await self.broadcast({
                        "type": "auction_settlement_failed",
                        "reason": "Insufficient funds from winner",
                        "winner": winner_uuid,
                        "seller": seller_uuid,
                        "amount": final_amount
                    })
                else:
                    # Transfer the card from seller -> winner
                    transfer_ok = change_card_ownership(seller_uuid, winner_uuid, curr_item.card)
                    if transfer_ok:

                        #log code
                        auction_logger.info(
                            "auction_settled",
                            room_id=self.id,
                            winner_uuid=winner_uuid,
                            seller_uuid=seller_uuid,
                            amount=final_amount,
                            card_name=curr_item.card.card_name
                        )
                        await self.broadcast({
                            "type": "auction_settled",
                            "winner": winner_uuid,
                            "seller": seller_uuid,
                            "amount": final_amount,
                            "card": curr_item.card.card_name
                        })
                    else:
                        #log code
                        auction_logger.error(
                            "auction_settlement_failed_card_transfer",
                            room_id=self.id,
                            winner_uuid=winner_uuid,
                            seller_uuid=seller_uuid,
                            amount=final_amount,
                            card_name=curr_item.card.card_name
                        )

                        # If card transfer failed, refund the winner
                        exchange_money(seller_uuid, winner_uuid, final_amount)

                        #log code
                        auction_logger.info(
                            "auction_refund_issued",
                            room_id=self.id,
                            winner_uuid=winner_uuid,
                            amount=final_amount
                        )

                        await self.broadcast({
                            "type": "auction_settlement_failed",
                            "reason": "Card transfer failed; buyer refunded",
                            "winner": winner_uuid,
                            "seller": seller_uuid,
                            "amount": final_amount
                        })
            except Exception as e:
                #log code
                auction_logger.error(
                    "auction_settlement_exception",
                    room_id=self.id,
                    winner_uuid=winner_uuid,
                    seller_uuid=seller_uuid,
                    amount=final_amount,
                    card_name=curr_item.card.card_name,
                    error=str(e)
                )
                # On unexpected error, attempt best-effort refund if necessary and notify
                try:
                    from server_components.utils.db_access import exchange_money
                    # Attempt refund (may fail silently)
                    exchange_money(seller_uuid, winner_uuid, final_amount)
                    #log code
                    auction_logger.info(
                        "auction_refund_attempted",
                        room_id=self.id,
                        winner_uuid=winner_uuid,
                        amount=final_amount
                    )

                except Exception as refund_error:

                    #log code
                    auction_logger.error(
                        "auction_refund_failed",
                        room_id=self.id,
                        winner_uuid=winner_uuid,
                        amount=final_amount,
                        error=str(refund_error)
                    )
                await self.broadcast({
                    "type": "auction_settlement_failed",
                    "reason": f"Unexpected error during settlement: {e}"
                })
        else:
            #log code
            auction_logger.info(
                "auction_ended_no_bids",
                room_id=self.id,
                card_name=curr_item.card.card_name if curr_item else None,
                seller_uuid=curr_item.seller_uuid if curr_item else None
            )
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

        #log code
        auction_logger.info(
            "auction_item_queued",
            room_id=self.id,
            card_name=item.card.card_name,
            seller_uuid=item.seller_uuid,
            starting_bid=item.starting,
            buyout_price=item.buyout,
            queue_position=len(self.auc_list)
        )

        if not self.room_active and not self.current_item:

            #log code
            auction_logger.info(
                "auction_room_starting_from_idle",
                room_id=self.id
            )

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

    #log code
    auction_logger.info(
        "auction_list_item_attempt",
        seller_uuid=request.seller_uuid,
        card_name=request.card_name,
        starting_bid=request.starting_bid,
        buyout_price=request.buyout_price
    )
    # Get card from database 
    from server_components.utils.db_access import select_card_by_name
    card = select_card_by_name(request.seller_uuid, request.card_name)

    if not card:
        
        #log code
        auction_logger.warning(
            "auction_list_item_card_not_found",
            seller_uuid=request.seller_uuid,
            card_name=request.card_name
        )
        
        raise HTTPException(status_code=404, detail="Card not found")
    
    classed_card = Card(card["card_name"], card["rarity"])
    
    # Find best room for the item
    room_id = auction_house.get_available_room()
    if room_id is None:

        #log code
        auction_logger.error(
            "auction_list_item_no_rooms",
            seller_uuid=request.seller_uuid,
            card_name=request.card_name
        )
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
    
    #log code
    auction_logger.info(
        "auction_list_item_success",
        seller_uuid=request.seller_uuid,
        card_name=request.card_name,
        room_id=room_id,
        queue_position=len(room.auc_list)
    )

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

        #log code
        auction_logger.warning(
            "auction_ws_room_not_found",
            room_id=room_id,
            user_uuid=user_uuid
        )

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

            elif data["type"] == "status":
                await room.send_current_state(user_uuid)
            
            elif data["type"] == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:

        #log code
        auction_logger.info(
            "auction_ws_disconnected",
            room_id=room_id,
            user_uuid=user_uuid
        )
        
        await room.disconnect(user_uuid)
    
    except Exception as e:
        
        #log code
        auction_logger.error(
            "auction_ws_error",
            room_id=room_id,
            user_uuid=user_uuid,
            error=str(e)
        )
        
        await room.disconnect(user_uuid)


class MarketListRequest(BaseModel):
    email: str
    card_name: str
    rarity: str
    price: int

class MarketBuyRequest(BaseModel):
    email: str
    listing_id: int

class MarketSearchRequest(BaseModel):
    card_names: list[str] | None = None
    rarities: list[str] | None = None
    price_min: int | None = None
    price_max: int | None = None
    limit: int = 10


@app.post("/marketplace/list")
async def marketplace_list(req: MarketListRequest):
    """List a card for sale on the marketplace."""
    # Endpoint: validate ownership then insert a marketplace row. This is a
    # convenience listing model (no reservation of a specific card row).

    #log code
    marketplace_logger.info(
        "marketplace_list_attempt",
        email=req.email,
        card_name=req.card_name,
        rarity=req.rarity,
        price=req.price
    )

    user = get_user_by_email(req.email)
    if not user:

        #log code
        marketplace_logger.warning(
            "marketplace_list_user_not_found",
            email=req.email
        )

        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    # Check user owns this card
    card = select_card_by_name(user['uuid'], req.card_name)
    if not card or card['rarity'] != req.rarity:

        #log code
        marketplace_logger.warning(
            "marketplace_list_card_not_owned",
            user_uuid=user["uuid"],
            card_name=req.card_name,
            rarity=req.rarity
        )

        return JSONResponse(status_code=400, content={"error": "You don't own this card"})
    
    if req.price <= 0:

        #log code
        marketplace_logger.warning(
            "marketplace_list_invalid_price",
            user_uuid=user["uuid"],
            price=req.price
        )

        return JSONResponse(status_code=400, content={"error": "Price must be positive"})
    
    success = add_to_marketplace(user['uuid'], req.card_name, req.rarity, req.price)
    if success:

        #log code
        marketplace_logger.info(
            "marketplace_list_success",
            user_uuid=user["uuid"],
            card_name=req.card_name,
            rarity=req.rarity,
            price=req.price
        )

        return JSONResponse(status_code=201, content={"message": "Card listed successfully"})
    
    #log code
    marketplace_logger.error(
        "marketplace_list_failed",
        user_uuid=user["uuid"],
        card_name=req.card_name,
        rarity=req.rarity
    )

    return JSONResponse(status_code=500, content={"error": "Failed to list card"})


@app.post("/marketplace/search")
async def marketplace_search(req: MarketSearchRequest):
    """Search marketplace listings."""
    # Simple search wrapper around DB helper; returns listing rows.

    #log code
    marketplace_logger.info(
        "marketplace_search",
        card_names=req.card_names,
        rarities=req.rarities,
        price_min=req.price_min,
        price_max=req.price_max,
        limit=req.limit
    )

    listings = querey_marketplace(
        ammount=req.limit,
        card_names=req.card_names,
        rarities=req.rarities,
        price_min=req.price_min,
        price_max=req.price_max
    )

    #log code
    marketplace_logger.info(
        "marketplace_search_results",
        results_count=len(listings)
    )

    return JSONResponse(status_code=200, content={"listings": listings, "count": len(listings)})


@app.post("/marketplace/buy")
async def marketplace_buy(req: MarketBuyRequest):
    """Buy a card from the marketplace."""
    # Buy flow (minimal): 1) get listing, 2) transfer money, 3) transfer one
    # matching card from seller -> buyer, 4) remove the listing. This approach
    # transfers the first matching card instance

    #log code
    marketplace_logger.info(
        "marketplace_buy_attempt",
        email=req.email,
        listing_id=req.listing_id
    )

    buyer = get_user_by_email(req.email)
    if not buyer:

        #log code
        marketplace_logger.warning(
            "marketplace_buy_user_not_found",
            email=req.email
        )

        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    # Get the listing
    from server_components.utils.db_access import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Marketplace WHERE id = ?", (req.listing_id,))
    listing = cursor.fetchone()
    conn.close()
    
    if not listing:

        #log code
        marketplace_logger.warning(
            "marketplace_buy_listing_not_found",
            user_uuid=buyer["uuid"],
            listing_id=req.listing_id
        )
        return JSONResponse(status_code=404, content={"error": "Listing not found"})
    
    listing = dict(listing)
    seller_uuid = listing['uuid']
    
    if buyer['uuid'] == seller_uuid:

        #log code
        marketplace_logger.warning(
            "marketplace_buy_own_listing",
            user_uuid=buyer["uuid"],
            listing_id=req.listing_id
        )

        return JSONResponse(status_code=400, content={"error": "Cannot buy your own listing"})
    
    # Transfer money (buyer -> seller)
    if not exchange_money(buyer['uuid'], seller_uuid, listing['price']):

        #log code
        marketplace_logger.warning(
            "marketplace_buy_insufficient_funds",
            buyer_uuid=buyer["uuid"],
            seller_uuid=seller_uuid,
            price=listing["price"]
        )

        return JSONResponse(status_code=400, content={"error": "Insufficient funds"})
    
    # Transfer card ownership
    card = Card(listing['card_name'], listing['rarity'])
    from server_components.utils.db_access import change_card_ownership
    change_card_ownership(seller_uuid, buyer['uuid'], card)
    
    # Remove listing
    remove_from_marketplace(seller_uuid, listing['card_name'], listing['rarity'], listing['price'])
    
    #log code
    transaction_logger.info(
        "marketplace_purchase",
        buyer_uuid=buyer["uuid"],
        buyer_email=req.email,
        seller_uuid=seller_uuid,
        card_name=listing["card_name"],
        rarity=listing["rarity"],
        price=listing["price"],
        listing_id=req.listing_id
    )

    return JSONResponse(status_code=200, content={
        "message": "Purchase successful",
        "card_name": listing['card_name'],
        "price": listing['price']
    })  



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

    #log code
    server_logger.info(
        "trade_waiting_room_connected"
    )

    try:
        while True:
            data = await websocket.receive_text()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # TODO: Integrate JWT or session lookup to get actual username
            user_display = "User" 
            
            #log code
            server_logger.debug(
                "trade_waiting_room_message",
                user=user_display,
                message=data
            )
            #print(f"{current_time} - {user_display}: {data}")
            await manager.broadcast(f"You wrote: {data}")

    except WebSocketDisconnect:

        #log code
        server_logger.info(
            "trade_waiting_room_disconnected"
        )

        manager.disconnect(websocket)
        # print("WebSocket connection closed")
    except Exception as e:
        #log code
        server_logger.error(
            "trade_waiting_room_error",
            error=str(e)
        )
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    # init_db is handled by the startup event, but can be called here if running script directly
    uvicorn.run(app, host="0.0.0.0", port=8000)