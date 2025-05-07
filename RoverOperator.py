import requests
import json
import time
import websockets
import asyncio
import argparse

class RoverOperator:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        
    def get_map(self):
        response = self.session.get(f"{self.base_url}/map")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting map: {response.status_code}")
            return None
            
    def update_map(self, height, width):
        data = {"height": height, "width": width}
        response = self.session.put(f"{self.base_url}/map", json=data)
        if response.status_code == 200:
            print("Map updated successfully")
            return True
        else:
            print(f"Error updating map: {response.status_code} - {response.text}")
            return False
            
    def get_mines(self):
        response = self.session.get(f"{self.base_url}/mines")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting mines: {response.status_code}")
            return None
            
    def get_mine(self, mine_id):
        response = self.session.get(f"{self.base_url}/mines/{mine_id}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting mine {mine_id}: {response.status_code}")
            return None
            
    def create_mine(self, x, y, serial_number):
        data = {"x": x, "y": y, "serial_number": serial_number}
        response = self.session.post(f"{self.base_url}/mines", json=data)
        if response.status_code == 201:
            print(f"Mine created successfully with ID: {response.json()['id']}")
            return response.json()
        else:
            print(f"Error creating mine: {response.status_code} - {response.text}")
            return None
            
    def update_mine(self, mine_id, x=None, y=None, serial_number=None):
        data = {}
        if x is not None:
            data["x"] = x
        if y is not None:
            data["y"] = y
        if serial_number is not None:
            data["serial_number"] = serial_number
            
        response = self.session.put(f"{self.base_url}/mines/{mine_id}", json=data)
        if response.status_code == 200:
            print(f"Mine {mine_id} updated successfully")
            return response.json()
        else:
            print(f"Error updating mine {mine_id}: {response.status_code} - {response.text}")
            return None
            
    def delete_mine(self, mine_id):
        response = self.session.delete(f"{self.base_url}/mines/{mine_id}")
        if response.status_code == 204:
            print(f"Mine {mine_id} deleted successfully")
            return True
        else:
            print(f"Error deleting mine {mine_id}: {response.status_code} - {response.text}")
            return False
            
    def get_rovers(self):
        response = self.session.get(f"{self.base_url}/rovers")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting rovers: {response.status_code}")
            return None
            
    def get_rover(self, rover_id):
        response = self.session.get(f"{self.base_url}/rovers/{rover_id}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting rover {rover_id}: {response.status_code}")
            return None
            
    def create_rover(self, commands):
        data = {"commands": commands}
        response = self.session.post(f"{self.base_url}/rovers", json=data)
        if response.status_code == 201:
            print(f"Rover created successfully with ID: {response.json()['id']}")
            return response.json()
        else:
            print(f"Error creating rover: {response.status_code} - {response.text}")
            return None
            
    def update_rover(self, rover_id, commands):
        data = {"commands": commands}
        response = self.session.put(f"{self.base_url}/rovers/{rover_id}", json=data)
        if response.status_code == 200:
            print(f"Rover {rover_id} updated successfully")
            return response.json()
        else:
            print(f"Error updating rover {rover_id}: {response.status_code} - {response.text}")
            return None
            
    def delete_rover(self, rover_id):
        response = self.session.delete(f"{self.base_url}/rovers/{rover_id}")
        if response.status_code == 204:
            print(f"Rover {rover_id} deleted successfully")
            return True
        else:
            print(f"Error deleting rover {rover_id}: {response.status_code} - {response.text}")
            return False
            
    def dispatch_rover(self, rover_id):
        response = self.session.post(f"{self.base_url}/rovers/{rover_id}/dispatch")
        if response.status_code == 200:
            print(f"Rover {rover_id} dispatched successfully")
            return response.json()
        else:
            print(f"Error dispatching rover {rover_id}: {response.status_code} - {response.text}")
            return None
    
    def display_map(self, grid=None, rover_pos=None):
        if grid is None:
            grid = self.get_map()
            
        if grid is None:
            print("No map data available")
            return
            
        print("Map:")
        for y in range(len(grid)):
            row = ""
            for x in range(len(grid[y])):
                # Check if rover is at this position
                if rover_pos and rover_pos['x'] == x and rover_pos['y'] == y:
                    row += "R "
                elif grid[y][x] == 1:
                    row += "M "  # Mine
                else:
                    row += "0 "  # Empty
            print(row)
        print()
    
    def display_rover_path(self, rover_id):
        rover = self.get_rover(rover_id)
        if not rover:
            return
            
        if rover['status'] != 'Finished':
            print(f"Rover {rover_id} has not finished its path yet")
            return
            
        # Get the map
        grid = self.get_map()
        if not grid:
            return
            
        # Create a path map
        path_map = [[' ' for _ in range(len(grid[0]))] for _ in range(len(grid))]
        
        # Mark mines
        for y in range(len(grid)):
            for x in range(len(grid[0])):
                if grid[y][x] == 1:
                    path_map[y][x] = 'M'
                    
        # Simulate rover movement to draw path
        x, y = 0, 0  # Start at (0,0)
        direction_idx = 2  # Start facing South
        
        path_map[y][x] = '*'  # Start position
        
        for cmd in rover['executed_commands']:
            if cmd == 'L':
                direction_idx = (direction_idx - 1) % 4
            elif cmd == 'R':
                direction_idx = (direction_idx + 1) % 4
            elif cmd == 'M':
                dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][direction_idx]
                new_x, new_y = x + dx, y + dy
                
                if 0 <= new_x < len(grid[0]) and 0 <= new_y < len(grid):
                    x, y = new_x, new_y
                    if path_map[y][x] != 'M':  # Don't overwrite mines
                        path_map[y][x] = '*'
                        
        # Display the path map
        print(f"Path for Rover {rover_id}:")
        for row in path_map:
            print(''.join(row))
        print()
        
    async def control_rover_realtime(self, rover_id):
        try:
            uri = f"ws://{self.base_url.split('://')[-1]}/ws/{rover_id}"
            async with websockets.connect(uri) as websocket:
                print(f"Connected to rover {rover_id} for real-time control")
            print("Commands: L (turn left), R (turn right), M (move forward), D (dig)")
            print("Enter 'q' to quit")
            
            # Get initial rover information
            rover = self.get_rover(rover_id)
            if rover:
                print(f"Rover status: {rover['status']}")
                if 'position' in rover:
                    print(f"Initial position: ({rover['position']['x']}, {rover['position']['y']})")
            
            while True:
                # Get map to display current state
                grid = self.get_map()
                if grid and 'position' in rover:
                    self.display_map(grid, rover['position'])
                
                # Get command from user
                command = input("Enter command: ").upper()
                
                if command.lower() == 'q':
                    print("Exiting real-time control")
                    break
                
                if command not in ['L', 'R', 'M', 'D']:
                    print("Invalid command. Use L, R, M, or D")
                    continue
                
                # Send command to server
                await websocket.send(command)
                
                # Receive response
                response = await websocket.recv()
                response_data = json.loads(response)
                
                if 'error' in response_data:
                    print(f"Error: {response_data['error']}")
                else:
                    print(f"Command executed: {command}")
                    
                    if command == 'M' and 'new_position' in response_data:
                        print(f"New position: ({response_data['new_position']['x']}, {response_data['new_position']['y']})")
                        if 'position' in rover:
                            rover['position'] = response_data['new_position']
                    
                    elif command == 'D' and 'pin' in response_data:
                        print(f"Mine disarmed! PIN: {response_data['pin']}")
            
        except websockets.exceptions.ConnectionClosed:
            print(f"Connection to rover {rover_id} closed")
        except Exception as e:
            print(f"Error in real-time control: {e}")


def main():
    parser = argparse.ArgumentParser(description='Rover Operator CLI')
    parser.add_argument('--url', default='http://localhost:8000', help='Base URL of the server')
    args = parser.parse_args()
    
    operator = RoverOperator(args.url)
    
    while True:
        print("\n==== Rover Operator Menu ====")
        print("1. Map Operations")
        print("2. Mine Operations")
        print("3. Rover Operations")
        print("4. Exit")
        
        choice = input("Enter your choice (1-4): ")
        
        if choice == '1':
            map_menu(operator)
        elif choice == '2':
            mine_menu(operator)
        elif choice == '3':
            rover_menu(operator)
        elif choice == '4':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")


def map_menu(operator):
    while True:
        print("\n==== Map Operations ====")
        print("1. Get Map")
        print("2. Update Map")
        print("3. Back to Main Menu")
        
        choice = input("Enter your choice (1-3): ")
        
        if choice == '1':
            grid = operator.get_map()
            if grid:
                operator.display_map(grid)
        elif choice == '2':
            try:
                height = int(input("Enter map height: "))
                width = int(input("Enter map width: "))
                operator.update_map(height, width)
            except ValueError:
                print("Invalid input. Please enter numbers.")
        elif choice == '3':
            break
        else:
            print("Invalid choice. Please try again.")


def mine_menu(operator):
    while True:
        print("\n==== Mine Operations ====")
        print("1. List All Mines")
        print("2. Get Mine Details")
        print("3. Create Mine")
        print("4. Update Mine")
        print("5. Delete Mine")
        print("6. Back to Main Menu")
        
        choice = input("Enter your choice (1-6): ")
        
        if choice == '1':
            mines = operator.get_mines()
            if mines:
                print("Mines:")
                for mine in mines:
                    print(f"ID: {mine['id']}, Position: ({mine['x']}, {mine['y']}), Serial: {mine['serial_number']}")
        elif choice == '2':
            mine_id = input("Enter mine ID: ")
            mine = operator.get_mine(mine_id)
            if mine:
                print(f"Mine ID: {mine['id']}")
                print(f"Position: ({mine['x']}, {mine['y']})")
                print(f"Serial Number: {mine['serial_number']}")
        elif choice == '3':
            try:
                x = int(input("Enter X coordinate: "))
                y = int(input("Enter Y coordinate: "))
                serial = input("Enter serial number: ")
                operator.create_mine(x, y, serial)
            except ValueError:
                print("Invalid input. Please enter numbers for coordinates.")
        elif choice == '4':
            mine_id = input("Enter mine ID: ")
            try:
                x_input = input("Enter new X coordinate (leave blank to keep current): ")
                y_input = input("Enter new Y coordinate (leave blank to keep current): ")
                serial = input("Enter new serial number (leave blank to keep current): ")
                
                x = int(x_input) if x_input else None
                y = int(y_input) if y_input else None
                serial = serial if serial else None
                
                operator.update_mine(mine_id, x, y, serial)
            except ValueError:
                print("Invalid input. Please enter numbers for coordinates.")
        elif choice == '5':
            mine_id = input("Enter mine ID to delete: ")
            operator.delete_mine(mine_id)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")


def rover_menu(operator):
    while True:
        print("\n==== Rover Operations ====")
        print("1. List All Rovers")
        print("2. Get Rover Details")
        print("3. Create Rover")
        print("4. Update Rover")
        print("5. Delete Rover")
        print("6. Dispatch Rover")
        print("7. Display Rover Path")
        print("8. Control Rover (Real-time)")
        print("9. Back to Main Menu")
        
        choice = input("Enter your choice (1-9): ")
        
        if choice == '1':
            rovers = operator.get_rovers()
            if rovers:
                print("Rovers:")
                for rover in rovers:
                    print(f"ID: {rover['id']}, Status: {rover['status']}")
        elif choice == '2':
            rover_id = input("Enter rover ID: ")
            rover = operator.get_rover(rover_id)
            if rover:
                print(f"Rover ID: {rover['id']}")
                print(f"Status: {rover['status']}")
                if 'position' in rover:
                    print(f"Position: ({rover['position']['x']}, {rover['position']['y']})")
                if 'commands' in rover:
                    print(f"Commands: {rover['commands']}")
        elif choice == '3':
            commands = input("Enter commands (e.g., LMRMMD): ")
            operator.create_rover(commands)
        elif choice == '4':
            rover_id = input("Enter rover ID: ")
            commands = input("Enter new commands (e.g., LMRMMD): ")
            operator.update_rover(rover_id, commands)
        elif choice == '5':
            rover_id = input("Enter rover ID to delete: ")
            operator.delete_rover(rover_id)
        elif choice == '6':
            rover_id = input("Enter rover ID to dispatch: ")
            result = operator.dispatch_rover(rover_id)
            if result:
                print(f"Rover dispatched. Final position: ({result['position']['x']}, {result['position']['y']})")
                print(f"Executed commands: {result['executed_commands']}")
        elif choice == '7':
            rover_id = input("Enter rover ID to display path: ")
            operator.display_rover_path(rover_id)
        elif choice == '8':
            rover_id = input("Enter rover ID for real-time control: ")
            asyncio.run(operator.control_rover_realtime(rover_id))
        elif choice == '9':
            break
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()