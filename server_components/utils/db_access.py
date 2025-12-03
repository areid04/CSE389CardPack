import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
import datetime

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
    cards: list of Card objects with .name and .rarity attributes
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for card in cards:
            cursor.execute("""
                INSERT INTO CardsOpened (uuid, card_name, rarity)
                VALUES (?, ?, ?)
            """, (user_uuid, card.name, card.rarity))
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

from ..card_utils.card import Card


# swap hands basically
# swap hands basically
def change_card_ownership(seller_uuid:str, buyer_uuid:str, card:Card):
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