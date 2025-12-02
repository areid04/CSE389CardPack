from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uuid
from datetime import datetime

# import dataclasses
from server_classes import CreateUser, LoginUser, Email

# import our DB access functions
from utils.db_access import (
    init_db, 
    get_user_by_email, 
    get_user_by_username, 
    create_user_entry
)

app = FastAPI()

# startup functions
@app.on_event("startup")
async def startup_event():
    # Initialize the SQLite DB defined in the schema
    init_db()

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

    # TODO: generate a card pack for the new user -> Insert into Inventory Table here
    from utils.db_access import add_default_pack
    add_default_pack(new_uuid)

    if success:
        return JSONResponse(status_code=201, content={"message": "User created successfully", "uuid": new_uuid})
    else:
        return JSONResponse(status_code=500, content={"error": "Failed to create user"})


# debug example endpoint, some one make a more general "buy a card pack" endpoint please 
@app.post("/gen_default_pack")
async def debug_gen(email: Email):
    from utils.db_access import get_user_by_email
    row = get_user_by_email(email.email)

    # add to the inventory
    from utils.db_access import add_default_pack
    add_default_pack(row['uuid'])
    return JSONResponse(status_code=201, content={"message": "User created successfully"})

# debug example endpoint

@app.post("/open_pack")
async def debug_open(email: Email):
    from utils.db_access import open_default_pack
    from utils.db_access import get_user_by_email
    row = get_user_by_email(email.email)
    result = open_default_pack(row['uuid'])
    if (result != False): # we should have gotten a path
        from card_utils.pack_utils import pack_from_path
        pack = pack_from_path(result)
        # pack object
        cards = pack.open_pack()
        print(cards) # for our debug statement
        return JSONResponse(status_code=201, content={"message": "Opened Pack Successfully"})
    else:
        return JSONResponse(status_code=401, content={"message": "Coukd Not Open Pack; do you really have this?"})





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