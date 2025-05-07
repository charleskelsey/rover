import hashlib
import json
import os
from enum import Enum
from typing import List, Optional, Dict, Any, Union

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Rover Control API")

# Enum for rover status
class RoverStatus(str, Enum):
    NOT_STARTED = "Not Started"
    MOVING = "Moving"
    FINISHED = "Finished"
    ELIMINATED = "Eliminated"

# Model definitions
class MineBase(BaseModel):
    x: int
    y: int
    serial_number: str

class MineCreate(MineBase):
    pass

class MineUpdate(BaseModel):
    x: Optional[int] = None
    y: Optional[int] = None
    serial_number: Optional[str] = None

class Mine(MineBase):
    id: int

class RoverBase(BaseModel):
    commands: str

class RoverCreate(RoverBase):
    pass

class RoverUpdate(RoverBase):
    pass

class RoverPosition(BaseModel):
    x: int
    y: int
    facing: str

class Rover(RoverBase):
    id: int
    status: RoverStatus
    position: RoverPosition
    executed_commands: str = ""

class MapDimensions(BaseModel):
    height: int
    width: int

# In-memory data storage
class DataStore:
    def __init__(self):
        self.map_height = 10
        self.map_width = 10
        self.grid = [[0 for _ in range(self.map_width)] for _ in range(self.map_height)]
        self.mines = {}  # id -> Mine
        self.rovers = {}  # id -> Rover
        self.next_mine_id = 1
        self.next_rover_id = 1

    def get_grid(self):
        return [row[:] for row in self.grid]  # Create a deep copy

    def update_grid_for_mine(self, mine_id, old_x=None, old_y=None):
        mine = self.mines.get(mine_id)
        if mine:
            # Clear old position if provided
            if old_x is not None and old_y is not None:
                if 0 <= old_x < self.map_width and 0 <= old_y < self.map_height:
                    self.grid[old_y][old_x] = 0
            
            # Set new position
            if 0 <= mine.x < self.map_width and 0 <= mine.y < self.map_height:
                self.grid[mine.y][mine.x] = 1

    def is_valid_position(self, x, y):
        return 0 <= x < self.map_width and 0 <= y < self.map_height

    def find_pin(self, serial):
        """Computes a PIN for the mine using a brute-force search on SHA256 hashes."""
        pin = 0
        while True:
            temp_key = serial + str(pin)
            hash_hex = hashlib.sha256(temp_key.encode()).hexdigest()
            if hash_hex.startswith('000000'):
                return pin
            pin += 1
            # Limiting search to prevent infinite loops
            if pin > 100000:
                return pin - 1

# Initialize data store
db = DataStore()

# Directions mapping
directions = ['N', 'E', 'S', 'W']
direction_moves = {
    'N': (0, -1),
    'E': (1, 0),
    'S': (0, 1),
    'W': (-1, 0),
}

# Map endpoints
@app.get("/map", response_model=List[List[int]])
async def get_map():
    return db.get_grid()

@app.put("/map", status_code=status.HTTP_200_OK)
async def update_map(dimensions: MapDimensions):
    if dimensions.height <= 0 or dimensions.width <= 0:
        raise HTTPException(status_code=400, detail="Height and width must be positive")
    
    # Update map dimensions
    old_height, old_width = db.map_height, db.map_width
    db.map_height = dimensions.height
    db.map_width = dimensions.width
    
    # Create new grid
    new_grid = [[0 for _ in range(db.map_width)] for _ in range(db.map_height)]
    
    # Copy over old grid values where possible
    for y in range(min(old_height, db.map_height)):
        for x in range(min(old_width, db.map_width)):
            new_grid[y][x] = db.grid[y][x]
    
    db.grid = new_grid
    
    # Update mines to ensure they are within the new grid
    for mine_id, mine in list(db.mines.items()):
        if not db.is_valid_position(mine.x, mine.y):
            del db.mines[mine_id]
        else:
            db.update_grid_for_mine(mine_id)
    
    return {"message": "Map dimensions updated successfully"}

# Mines endpoints
@app.get("/mines", response_model=List[Mine])
async def get_mines():
    return list(db.mines.values())

@app.get("/mines/{mine_id}", response_model=Mine)
async def get_mine(mine_id: int):
    mine = db.mines.get(mine_id)
    if mine is None:
        raise HTTPException(status_code=404, detail="Mine not found")
    return mine

@app.delete("/mines/{mine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mine(mine_id: int):
    mine = db.mines.get(mine_id)
    if mine is None:
        raise HTTPException(status_code=404, detail="Mine not found")
    
    # Remove mine from grid
    if db.is_valid_position(mine.x, mine.y):
        db.grid[mine.y][mine.x] = 0
    
    # Remove mine from storage
    del db.mines[mine_id]
    return None

@app.post("/mines", response_model=Mine, status_code=status.HTTP_201_CREATED)
async def create_mine(mine: MineCreate):
    if not db.is_valid_position(mine.x, mine.y):
        raise HTTPException(status_code=400, detail="Invalid mine position")
    
    # Check if position is already occupied by a mine
    for existing_mine in db.mines.values():
        if existing_mine.x == mine.x and existing_mine.y == mine.y:
            raise HTTPException(status_code=400, detail="Position already occupied by a mine")
    
    # Create new mine
    mine_id = db.next_mine_id
    db.next_mine_id += 1
    
    new_mine = Mine(
        id=mine_id,
        x=mine.x,
        y=mine.y,
        serial_number=mine.serial_number
    )
    
    db.mines[mine_id] = new_mine
    db.update_grid_for_mine(mine_id)
    
    return new_mine

@app.put("/mines/{mine_id}", response_model=Mine)
async def update_mine(mine_id: int, mine_update: MineUpdate):
    if mine_id not in db.mines:
        raise HTTPException(status_code=404, detail="Mine not found")

    mine = db.mines[mine_id]
    old_x, old_y = mine.x, mine.y # Store original position

    update_data = mine_update.dict(exclude_unset=True)

    # --- Prepare potential new values ---
    new_x = update_data.get('x', mine.x)
    new_y = update_data.get('y', mine.y)
    new_serial = update_data.get('serial_number', mine.serial_number)

    # --- Validation ---
    # 1. Validate new position bounds
    if not db.is_valid_position(new_x, new_y):
        # Revert changes if position is invalid and was part of the update
        if 'x' in update_data or 'y' in update_data:
             raise HTTPException(status_code=400, detail=f"Invalid new mine position ({new_x}, {new_y}). Out of bounds.")
        # else: Allow update if only serial was changed

    # 2. Check if the new position is occupied by ANOTHER mine
    if 'x' in update_data or 'y' in update_data: # Only check if position actually changed
        for other_mine_id, other_mine in db.mines.items():
            if other_mine_id != mine_id and other_mine.x == new_x and other_mine.y == new_y:
                raise HTTPException(
                    status_code=400,
                    detail=f"New position ({new_x}, {new_y}) is already occupied by mine {other_mine_id}"
                )

    # --- Apply Updates ---
    mine.x = new_x
    mine.y = new_y
    mine.serial_number = new_serial

    # --- Update Grid ---
    # Only update grid if position actually changed
    if mine.x != old_x or mine.y != old_y:
        # Clear old position on the grid
        if db.is_valid_position(old_x, old_y):
            db.grid[old_y][old_x] = 0
        # Set new position on the grid
        if db.is_valid_position(mine.x, mine.y):
             db.grid[mine.y][mine.x] = 1 # Assuming 1 represents a mine

    return mine

# Rovers endpoints
@app.get("/rovers", response_model=List[Rover])
async def get_rovers():
    return list(db.rovers.values())

@app.get("/rovers/{rover_id}", response_model=Rover)
async def get_rover(rover_id: int):
    rover = db.rovers.get(rover_id)
    if rover is None:
        raise HTTPException(status_code=404, detail="Rover not found")
    return rover

@app.post("/rovers", response_model=Rover, status_code=status.HTTP_201_CREATED)
async def create_rover(rover: RoverCreate):
    # Validate commands
    if not all(cmd in 'LRMD' for cmd in rover.commands):
        raise HTTPException(status_code=400, detail="Invalid commands. Only L, R, M, D are allowed.")
    
    # Create new rover
    rover_id = db.next_rover_id
    db.next_rover_id += 1
    
    new_rover = Rover(
        id=rover_id,
        commands=rover.commands,
        status=RoverStatus.NOT_STARTED,
        position=RoverPosition(x=0, y=0, facing='S')  # Start at (0,0) facing South
    )
    
    db.rovers[rover_id] = new_rover
    return new_rover

@app.delete("/rovers/{rover_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rover(rover_id: int):
    if rover_id not in db.rovers:
        raise HTTPException(status_code=404, detail="Rover not found")
    
    del db.rovers[rover_id]
    return None

@app.put("/rovers/{rover_id}", response_model=Rover)
async def update_rover(rover_id: int, rover_update: RoverUpdate):
    if rover_id not in db.rovers:
        raise HTTPException(status_code=404, detail="Rover not found")
    
    rover = db.rovers[rover_id]
    
    # Can only update if rover is not currently in motion
    if rover.status not in [RoverStatus.NOT_STARTED, RoverStatus.FINISHED]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot update rover while status is {rover.status}"
        )
    
    # Validate commands
    if not all(cmd in 'LRMD' for cmd in rover_update.commands):
        raise HTTPException(status_code=400, detail="Invalid commands. Only L, R, M, D are allowed.")
    
    rover.commands = rover_update.commands
    rover.status = RoverStatus.NOT_STARTED
    rover.position = RoverPosition(x=0, y=0, facing='S')  # Reset position
    rover.executed_commands = ""
    
    return rover

@app.post("/rovers/{rover_id}/dispatch", response_model=Rover)
async def dispatch_rover(rover_id: int):
    if rover_id not in db.rovers:
        raise HTTPException(status_code=404, detail="Rover not found")
    
    rover = db.rovers[rover_id]
    
    # Only dispatch if rover is ready
    if rover.status not in [RoverStatus.NOT_STARTED, RoverStatus.FINISHED]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot dispatch rover while status is {rover.status}"
        )
    
    # Reset rover state
    rover.status = RoverStatus.MOVING
    rover.position = RoverPosition(x=0, y=0, facing='S')  # Start at (0,0) facing South
    rover.executed_commands = ""
    
    # Process commands
    direction_idx = 2  # Start facing South (index 2 in directions list)
    current_pos = (0, 0)
    executed = []
    exploded = False
    on_mine = False
    
    for cmd in rover.commands:
        if cmd == 'L':
            direction_idx = (direction_idx - 1) % 4
            rover.position.facing = directions[direction_idx]
        elif cmd == 'R':
            direction_idx = (direction_idx + 1) % 4
            rover.position.facing = directions[direction_idx]
        elif cmd == 'M':
            # If we are on an active mine and try to move without disarming, we explode.
            if on_mine:
                exploded = True
                break
            
            # Execute the move
            dx, dy = direction_moves[rover.position.facing]
            new_x = rover.position.x + dx
            new_y = rover.position.y + dy
            
            # Check if move is valid
            if db.is_valid_position(new_x, new_y):
                rover.position.x = new_x
                rover.position.y = new_y
                
                # Check if landed on a mine
                if db.grid[new_y][new_x] > 0:
                    on_mine = True
                else:
                    on_mine = False
            else:
                # Out of bounds, ignore move
                pass
        elif cmd == 'D':
            # Disarming command - only works if we are on an active mine
            if on_mine and db.grid[rover.position.y][rover.position.x] > 0:
                # Find which mine is at this position
                mine_id = None
                for mid, mine in db.mines.items():
                    if mine.x == rover.position.x and mine.y == rover.position.y:
                        mine_id = mid
                        break
                
                if mine_id is not None:
                    mine = db.mines[mine_id]
                    pin = db.find_pin(mine.serial_number)
                    
                    # Disarm the mine
                    if db.is_valid_position(mine.x, mine.y):
                        db.grid[mine.y][mine.x] = 0
                    
                    # Remove the mine
                    del db.mines[mine_id]
                    
                    on_mine = False
            else:
                # No mine to disarm
                pass
        
        executed.append(cmd)
    
    rover.executed_commands = ''.join(executed)
    
    if exploded:
        rover.status = RoverStatus.ELIMINATED
    else:
        rover.status = RoverStatus.FINISHED
    
    return rover

# WebSocket for real-time control
@app.websocket("/ws/{rover_id}")
async def websocket_endpoint(websocket: WebSocket, rover_id: int):
    await websocket.accept()
    
    # Check if rover exists
    if rover_id not in db.rovers:
        await websocket.send_text(json.dumps({"error": "Rover not found"}))
        await websocket.close()
        return
    
    rover = db.rovers[rover_id]
    
    # Check if rover is in a valid state
    if rover.status not in [RoverStatus.NOT_STARTED, RoverStatus.FINISHED]:
        await websocket.send_text(json.dumps({"error": f"Rover is {rover.status}, cannot control"}))
        await websocket.close()
        return
    
    # Reset rover state for real-time control
    rover.status = RoverStatus.MOVING
    rover.position = RoverPosition(x=0, y=0, facing='S')  # Start at (0,0) facing South
    rover.commands = ""
    rover.executed_commands = ""
    
    direction_idx = 2  # Start facing South (index 2 in directions list)
    on_mine = False
    
    try:
        while True:
            command = await websocket.receive_text()
            
            # Validate command
            if command not in 'LRMD':
                await websocket.send_json({
                    "status": "error",
                    "message": "Invalid command. Only L, R, M, D are allowed."
                })
                continue
            
            if command == 'L':
                direction_idx = (direction_idx - 1) % 4
                rover.position.facing = directions[direction_idx]
                await websocket.send_json({
                    "status": "success",
                    "command": "L",
                    "newFacing": rover.position.facing
                })
                
            elif command == 'R':
                direction_idx = (direction_idx + 1) % 4
                rover.position.facing = directions[direction_idx]
                await websocket.send_json({
                    "status": "success",
                    "command": "R",
                    "newFacing": rover.position.facing
                })
                
            elif command == 'M':
                # If we are on an active mine and try to move without disarming, we explode
                if on_mine:
                    rover.status = RoverStatus.ELIMINATED
                    await websocket.send_json({
                        "status": "eliminated",
                        "message": "Rover eliminated! Stepped on a mine without disarming"
                    })
                    break
                
                # Execute the move
                dx, dy = direction_moves[rover.position.facing]
                new_x = rover.position.x + dx
                new_y = rover.position.y + dy
                
                # Check if move is valid
                if db.is_valid_position(new_x, new_y):
                    rover.position.x = new_x
                    rover.position.y = new_y
                    
                    # Check if landed on a mine
                    if db.grid[new_y][new_x] > 0:
                        on_mine = True
                        await websocket.send_json({
                            "status": "warning",
                            "command": "M",
                            "newPosition": {"x": new_x, "y": new_y},
                            "message": "Rover is on a mine! Disarm it before moving."
                        })
                    else:
                        on_mine = False
                        await websocket.send_json({
                            "status": "success",
                            "command": "M",
                            "newPosition": {"x": new_x, "y": new_y}
                        })
                else:
                    # Out of bounds, ignore move
                    await websocket.send_json({
                        "status": "error",
                        "command": "M",
                        "message": "Cannot move outside the map boundaries"
                    })
                    
            elif command == 'D':
                # Disarming command - only works if we are on an active mine
                if on_mine and db.grid[rover.position.y][rover.position.x] > 0:
                    # Find which mine is at this position
                    mine_id = None
                    for mid, mine in db.mines.items():
                        if mine.x == rover.position.x and mine.y == rover.position.y:
                            mine_id = mid
                            break
                    
                    if mine_id is not None:
                        mine = db.mines[mine_id]
                        pin = db.find_pin(mine.serial_number)
                        
                        # Disarm the mine
                        if db.is_valid_position(mine.x, mine.y):
                            db.grid[mine.y][mine.x] = 0
                        
                        # Remove the mine
                        del db.mines[mine_id]
                        
                        on_mine = False
                        await websocket.send_json({
                            "status": "success",
                            "command": "D",
                            "mineId": mine_id,
                            "pin": pin,
                            "message": "Mine successfully disarmed"
                        })
                    else:
                        await websocket.send_json({
                            "status": "error",
                            "command": "D",
                            "message": "Mine data inconsistency detected"
                        })
                else:
                    # No mine to disarm
                    await websocket.send_json({
                        "status": "error",
                        "command": "D",
                        "message": "No mine to disarm at this position"
                    })
            
            rover.executed_commands += command
            
    except WebSocketDisconnect:
        if rover.status == RoverStatus.MOVING:
            rover.status = RoverStatus.FINISHED
        print(f"Client for rover {rover_id} disconnected")

origins = [
    "http://localhost",         
    "http://localhost:8000",    
    "null"                     
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def read_root():
    try:
        return FileResponse('index.html')
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="index.html not found")

app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/map", response_model=List[List[int]])
async def get_map():
    return db.get_grid()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)