import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING
import datetime

if TYPE_CHECKING:
    from ..card_utils.card import Card

DB_PATH = Path("../db/CardPack_DB.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn

def init_db():
    """
    """
    if not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True)

    # ADD THIS PRINT STATEMENT:
    print(f"---------> DATABASE IS LOCATED AT: {DB_PATH.resolve()} <---------") 

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Enable Foreign Keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Users Table
    # Note: Schema src lists username/password as INTEGER, changed to TEXT for functionality.
    # Schema src lists uuid as BLOB, changed to TEXT to match Python UUID string generation.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        username TEXT NOT NULL UNIQUE,
        uuid TEXT NOT NULL PRIMARY KEY,
        email TEXT,
        password TEXT,
        is_admin BOOLEAN DEFAULT 0,
        inv BLOB
    );
    """)

    # Inventory Table (Foreign Key to Users.uuid)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Inventory (
        uuid TEXT NOT NULL, 
        pack_name TEXT NOT NULL,
        pack_path TEXT NOT NULL,
        qty INTEGER NOT NULL DEFAULT 1,
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(uuid) REFERENCES Users(uuid)
    );
    """)
    
    # CardsOpened Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS CardsOpened (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid TEXT NOT NULL,
        card_name TEXT NOT NULL,
        rarity TEXT NOT NULL,
        acquired_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(uuid) REFERENCES Users(uuid)
    );
    """)

    # Packs Table - Available pack types for purchase
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Packs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pack_name TEXT NOT NULL UNIQUE,
        pack_path TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed default packs if table is empty
    cursor.execute("SELECT COUNT(*) as count FROM Packs")
    if cursor.fetchone()['count'] == 0:
        cursor.executemany("""
            INSERT INTO Packs (pack_name, pack_path) VALUES (?, ?)
        """, [
            ("Music Pack Vol 1", "/music/music_pack_vol_1.json"),
            ("Food Pack Vol 1", "/food/food_pack_vol_1.json")
        ])

    conn.commit()
    conn.close()


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def create_user_entry(data: Dict[str, Any]) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Schema requires: username, uuid, email, password, is_admin (default 0)
        cursor.execute("""
            INSERT INTO Users (username, uuid, email, password, is_admin)
            VALUES (?, ?, ?, ?, ?)
        """, (data['username'], data['uuid'], data['email'], data['password'], data.get('is_admin', 0)))
        conn.commit()
        return True
    except sqlite3.IntegrityError as e:
        print(f"Database Integrity Error: {e}")
        return False
    except Exception as e:
        print(f"Database Error: {e}")
        return False
    finally:
        conn.close()

# take the uuid
def add_default_pack(user_uuid) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()

    # music pack vol
    pack_name = "Music Pack Vol 1"
    pack_path = "/music/music_pack_vol_1.json"

    try:
        cursor.execute("""
            SELECT id, qty FROM Inventory 
            WHERE uuid = ? AND pack_name = ?
        """, (user_uuid, pack_name))
        
        row = cursor.fetchone()
        
        if row:
            pack_id = row['id'] 
            new_qty = row['qty'] + 1
            cursor.execute("""
                UPDATE Inventory 
                SET qty = ? 
                WHERE id = ?
            """, (new_qty, pack_id))
            
        else:
            cursor.execute("""
                INSERT INTO Inventory (uuid, pack_name, pack_path, qty)
                VALUES (?, ?, ?, 1)
            """, (user_uuid, pack_name, pack_path))
            
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error adding pack to inventory: {e}")
        return False
    finally:
        conn.close()

# take uuid
def open_default_pack(user_uuid: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Target the specific default pack
    pack_name = "Music Pack Vol 1"
    
    try:
        # 1. Check if user has the pack and qty > 0
        cursor.execute("""
            SELECT id, qty,pack_path FROM Inventory 
            WHERE uuid = ? AND pack_name = ?
        """, (user_uuid, pack_name))
        
        row = cursor.fetchone()
        
        if row and row['qty'] > 0:
            # 2. Decrement the quantity
            pack_id = row['id']
            new_qty = row['qty'] - 1
            
            cursor.execute("""
                UPDATE Inventory 
                SET qty = ? 
                WHERE id = ?
            """, (new_qty, pack_id))
            
            conn.commit()

            return row["pack_path"]
            
        else:
            # User has 0 packs or the row doesn't exist
            return False
            
    except Exception as e:
        print(f"Error opening default pack: {e}")
        return False
    finally:
        conn.close()
    # TODO:  take the confirmed existing card pack, decrement it, and generate card pack, add those all to user inventroy


def add_card_to_collection(user_uuid: str, card_name: str, rarity: str) -> bool:
    """
    Save a single opened card to the user's CardsOpened collection.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO CardsOpened (uuid, card_name, rarity)
            VALUES (?, ?, ?)
        """, (user_uuid, card_name, rarity))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding card to collection: {e}")
        return False
    finally:
        conn.close()


def add_cards_to_collection(user_uuid: str, cards: list) -> bool:
    """
    Save multiple opened cards to the user's CardsOpened collection.
    cards: list of Card objects with .card_name and .rarity attributes
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for card in cards:
            cursor.execute("""
                INSERT INTO CardsOpened (uuid, card_name, rarity)
                VALUES (?, ?, ?)
            """, (user_uuid, card.card_name, card.rarity))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding cards to collection: {e}")
        return False
    finally:
        conn.close()


def get_user_cards(user_uuid: str) -> list:
    """
    Retrieve all cards owned by a user, grouped by card name and rarity.
    Returns list of dicts with card_name, rarity, qty, and latest acquired_at.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT card_name, rarity, COUNT(*) as qty, MAX(acquired_at) as acquired_at
            FROM CardsOpened
            WHERE uuid = ?
            GROUP BY card_name, rarity
            ORDER BY acquired_at DESC
        """, (user_uuid,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error getting user cards: {e}")
        return []
    finally:
        conn.close()


def get_user_inventory(user_uuid: str) -> list:
    """
    Retrieve all packs owned by a user.
    Returns list of dicts with pack_name, qty, pack_path, and created_at.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT pack_name, qty, pack_path, created_at
            FROM Inventory
            WHERE uuid = ? AND qty > 0
            ORDER BY created_at DESC
        """, (user_uuid,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error getting user inventory: {e}")
        return []
    finally:
        conn.close()


def select_card_by_name(user_uuid: str, card_name:str):
    conn = get_db_connection()  
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT card_name, rarity, acquired_at
            FROM CardsOpened
            WHERE uuid = ?
            ORDER BY card_name
        """, (user_uuid,))

        all_cards = cursor.fetchall()

        cursor.execute("""
            SELECT card_name, rarity, acquired_at
            FROM CardsOpened
            WHERE uuid = ? AND card_name = ?
        """, (user_uuid, card_name))
        
        row = cursor.fetchone()
        print(row)

        if row:
            # Convert row to dictionary for easier access
            return {
                "card_name": row[0],
                "rarity": row[1],
                "uuid": user_uuid
            }
        return None  # Return None if no card found
    except Exception as e:
        print(f"Error getting card{e}")
        return []
    finally:
        conn.close()


# swap hands basically
def change_card_ownership(seller_uuid: str, buyer_uuid: str, card: "Card"):
    """
    Transfer card ownership from seller to buyer.
    card: Card object with card_name and rarity attributes
    """
    card_name = card.card_name
    card_rarity = card.rarity

    conn = get_db_connection()  
    cursor = conn.cursor()
    try:
        # check that seller owns this card
        cursor.execute("""
            SELECT id FROM CardsOpened
            WHERE uuid = ? AND card_name = ? AND rarity = ?
        """, (seller_uuid, card_name, card_rarity))
        
        row = cursor.fetchone()

        if row:
            card_id = row['id']
            # Update the uuid to transfer ownership to buyer
            cursor.execute("""
                UPDATE CardsOpened
                SET uuid = ?
                WHERE id = ?
            """, (buyer_uuid, card_id))
            
            conn.commit()
            return True
        else:
            print(f"Card {card_name} ({card_rarity}) not found in {seller_uuid}'s collection")
            return False
            
    except Exception as e:
        print(f"Error changing card ownership: {e}")
        return False
    finally:
        conn.close()


def open_pack_for_user(user_uuid: str, pack_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Open a pack for a user. If pack_name is provided, open that specific pack type.
    If pack_name is None, open the most recently acquired pack.
    Returns dict with pack info (id, pack_name, pack_path) or None if no pack available.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if pack_name:
            # Open specific pack type
            cursor.execute("""
                SELECT id, qty, pack_path, pack_name 
                FROM Inventory 
                WHERE uuid = ? AND pack_name = ? AND qty > 0 
                LIMIT 1
            """, (user_uuid, pack_name))
        else:
            # Open most recently acquired pack
            cursor.execute("""
                SELECT id, qty, pack_path, pack_name 
                FROM Inventory 
                WHERE uuid = ? AND qty > 0 
                ORDER BY created_at DESC 
                LIMIT 1
            """, (user_uuid,))
        
        row = cursor.fetchone()
        
        if not row or row['qty'] <= 0:
            # Debug: Check what's in the inventory
            cursor.execute("""
                SELECT pack_name, qty FROM Inventory WHERE uuid = ?
            """, (user_uuid,))
            all_packs = cursor.fetchall()
            print(f"DEBUG: User inventory: {[dict(p) for p in all_packs]}")
            print(f"DEBUG: Looking for pack_name: '{pack_name}'")
            return None
        
        # Decrement quantity
        pack_id = row['id']
        new_qty = row['qty'] - 1
        cursor.execute("UPDATE Inventory SET qty = ? WHERE id = ?", (new_qty, pack_id))
        conn.commit()
        
        return {
            'id': row['id'],
            'pack_name': row['pack_name'],
            'pack_path': row['pack_path'],
            'qty_remaining': new_qty
        }
        
    except Exception as e:
        print(f"Error opening pack: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def add_pack_to_inventory(user_uuid: str, pack_name: str, pack_path: str) -> bool:
    """
    Add a pack to user's inventory. If pack already exists, increment qty.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, qty FROM Inventory 
            WHERE uuid = ? AND pack_name = ?
        """, (user_uuid, pack_name))
        
        row = cursor.fetchone()
        
        if row:
            new_qty = row['qty'] + 1
            cursor.execute("UPDATE Inventory SET qty = ? WHERE id = ?", (new_qty, row['id']))
        else:
            cursor.execute("""
                INSERT INTO Inventory (uuid, pack_name, pack_path, qty)
                VALUES (?, ?, ?, 1)
            """, (user_uuid, pack_name, pack_path))
            
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error adding pack to inventory: {e}")
        return False
    finally:
        conn.close()


def get_available_packs() -> Dict[str, str]:
    """
    Query the Packs table to get all available pack types.
    Returns dict of pack_name -> pack_path.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT pack_name, pack_path FROM Packs")
        rows = cursor.fetchall()
        return {row['pack_name']: row['pack_path'] for row in rows}
    except Exception as e:
        print(f"Error getting available packs: {e}")
        return {}
    finally:
        conn.close()


def add_pack_type(pack_name: str, pack_path: str) -> bool:
    """
    Add a new pack type to the Packs table.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Packs (pack_name, pack_path) VALUES (?, ?)
        """, (pack_name, pack_path))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding pack type: {e}")
        return False
    finally:
        conn.close()


def scan_and_register_packs(pack_json_dir: Path) -> Dict[str, Any]:
    """
    Scan pack_json directory and register any new packs not in the Packs table.
    Returns dict with stats about packs added, skipped, and errors.
    """
    import json
    
    results = {
        "added": [],
        "skipped": [],
        "errors": []
    }
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get existing packs from database
        cursor.execute("SELECT pack_name FROM Packs")
        existing_packs = {row['pack_name'] for row in cursor.fetchall()}
        
        # Scan all subdirectories in pack_json
        for category_dir in pack_json_dir.iterdir():
            if not category_dir.is_dir():
                continue
                
            category = category_dir.name
            
            # Check each JSON file in the category
            for json_file in category_dir.glob("*.json"):
                try:
                    # Read pack metadata from JSON
                    with open(json_file, 'r') as f:
                        pack_data = json.load(f)
                    
                    pack_name = pack_data.get('pack_name')
                    if not pack_name:
                        results["errors"].append(f"{json_file.name}: No pack_name in JSON")
                        continue
                    
                    # Check if already registered
                    if pack_name in existing_packs:
                        results["skipped"].append(pack_name)
                        continue
                    
                    # Register new pack
                    pack_path = f"/{category}/{json_file.name}"
                    cursor.execute("""
                        INSERT INTO Packs (pack_name, pack_path) VALUES (?, ?)
                    """, (pack_name, pack_path))
                    results["added"].append(pack_name)
                    
                except json.JSONDecodeError:
                    results["errors"].append(f"{json_file.name}: Invalid JSON")
                except Exception as e:
                    results["errors"].append(f"{json_file.name}: {str(e)}")
        
        conn.commit()
        
    except Exception as e:
        results["errors"].append(f"Database error: {str(e)}")
    finally:
        conn.close()
    
    return results


# @EmiF1

def change_money(ammount: int, account_uuid:str):
    # update Bank table based on this function call
    pass

def exchange_money(giver_uuid: str, taker_uuid: str):
    # update bank table from one end to the other
    pass

def non_negative_check(ammount: int, account_uuid: str):
    # check this does not lead to a negative balance
    pass

# another nice thing to have would be a daily-login cash bonus!

# one way that you can achieve this is with:

# 1. create a set() called "uuids_logged_in_today"

# 2. on the login endpoint in server.py, check if "logging_in_user" in uuids_logged...

# 3. if this is a daily login, send a cash bonus (100 coins / monies whatever)

# Update the endpoint (minimally) to make this possible

# it's okay if the data does not exist after a shutdown; small project example

# 4. make a background process that 1. checks time until midnight on start
#   2. sleep until midnight (that found time)
#   3. at midnight, uuids_logged... = set()
#   4. wait until next midnight, repeat.
