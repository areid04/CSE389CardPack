from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pathlib import Path
import uuid
import csv

# import dataclasses
from server_components.server_classes import CreateUser, LoginUser

# import our fake db access functions
from server_components.utils.db_access import query_csv, append_to_csv

# 

app = FastAPI()

# startup functions

path_to_csv = Path('db/users.csv')
if not path_to_csv.exists():
    # create the csv file with headers if it doesn't exist
    with open('db/users.csv', mode='w', newline='') as csvfile:
        fieldnames = ['username', 'uuid', 'email', 'password']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

@app.get("/")
async def read_root():
    return {"Hello": "World"}

@app.post("/login")
async def login_user(user: LoginUser):
    # check that there is an email and password otherwise fail
    if not user.email or not user.password:
        return JSONResponse(status_code=400, content={"error": "Missing email or password"})
    else:
        path_to_csv = Path('db/users.csv')
        existing_user = query_csv(path_to_csv, 'email', user.email)
        if not existing_user:
            return JSONResponse(status_code=404, content={"error": "User not found"})
        else:
            if existing_user['password'] != user.password:
                return JSONResponse(status_code=401, content={"error": "Incorrect password"})
            else:
                return JSONResponse(status_code=200, content={"message": "Login successful"})

# pass a class object with username and password attributes
@app.post("/signup")
async def signup_user(user: CreateUser):
    # check that there is a username, email, and password othewise fail
    # return 400 error if any are missing
    if not user.username or not user.email or not user.password:
        return JSONResponse(status_code=400, content={"error": "Missing username, email, or password"})

    else:
        # check if user already exists

        # THIS DB STUFF SHOULD BE HANDLED ON AN INIT CALL!!! TODO: MOVE

        path_to_csv = Path('db/users.csv')

        existing_user = query_csv(path_to_csv, 'username', user.username)
        if existing_user:
            return JSONResponse(status_code=400, content={"error": "Username already exists"})

        # append new user to csv file
        fieldnames = ['username', 'uuid', 'email', 'password']
        data = {
            'username': user.username,
            'uuid': str(uuid.uuid4()),
            'email': user.email,
            'password': user.password  # TODO: hash password before storing
        }
        success = append_to_csv(path_to_csv, fieldnames, data)
        if success:
            return JSONResponse(status_code=201, content={"message": "User created successfully"})
        else:
            return JSONResponse(status_code=500, content={"error": "Failed to create user"})


# post search for auction information
# EXAMPLE USING SQLITE, BUT THE SEARCH SHOULD BE THE SAME STILL
@app.post("/post/marketplace")
async def post_marketplace_search(search: MarketSearchRequest):
    # query on a SQL db for matching items






if __name__ == "__main__":
    init()
    
