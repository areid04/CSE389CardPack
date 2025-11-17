from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pathlib import Path
import uuid
import csv

# import dataclasses
from server_components.server_classes import CreateUser

# import our fake db access functions
from server_components.utils.db_access import query_csv, append_to_csv

app = FastAPI()

@app.get("/")
async def read_root():
    return {"Hello": "World"}

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
        if not path_to_csv.exists():
            # create the csv file with headers if it doesn't exist
            with open('db/users.csv', mode='w', newline='') as csvfile:
                fieldnames = ['username', 'uuid', 'email', 'password']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

        # ###########




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





    
