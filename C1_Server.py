import socket
import threading
import logging
import signal
import sys
from queue import Queue
from typing import List, Optional
from dataclasses import dataclass
import time
import random
import string
import codecs
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)

@dataclass
class Client:
    """Class to store client information"""
    socket: socket.socket
    address: tuple
    id: int
    player_number: int
    name: Optional[str] = None

class SocketServer:
    def __init__(self, host: str = '0.0.0.0', port: int = 8089):
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients: List[Client] = []
        self.client_lock = threading.Lock()
        self.running = False
        self.message_queue = Queue()
        self.client_counter = 0
        self.player_counter = 0
        self.password = self.generate_password()
        self.rotation_value = random.randint(5, 17)  # Randomize rotation value between 5 and 17
        self.encoded_password = self.custom_encode(self.password, self.rotation_value)
        self.player_2_connected = False  # Flag to track if Player 2 is connected
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def generate_password(self) -> str:
        """Generate a random password by selecting a 7-letter word"""
        # List of 7-letter words
        words = [
            "abacus", "freely", "blight", "shower", "splint", "debate", "jungle", "hockey", "glisten", "plaque",
            "decent", "crumble", "fleece", "candy", "blight", "banner", "engine", "flavor", "gather", "dozens"
        ]
        # Pick a random word from the list
        return random.choice(words)

    def custom_encode(self, text: str, rotation_value: int) -> str:
        """Encode text by rotating each letter by the given rotation value (between 5 and 17)"""
        result = []
        for char in text:
            if char.isalpha():  # Only encode letters
                # Shift letter within its range (lowercase or uppercase)
                shift = rotation_value if char.islower() else rotation_value
                new_char = chr(((ord(char.lower()) - ord('a') + shift) % 26) + ord('a'))
                if char.isupper():
                    new_char = new_char.upper()
                result.append(new_char)
            else:
                # Non-alphabetic characters are not changed
                result.append(char)
        return ''.join(result)

    def start(self):
        """Start the server"""
        try:
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            logging.info(f"Server started on {self.host}:{self.port}")
            print(f"Server is running on port {self.port}...")
            print(f"Generated password: {self.password}")
            print(f"Encoded password with rotation {self.rotation_value}: {self.encoded_password}")
            
            # Start message handler thread
            threading.Thread(target=self.handle_messages, daemon=True).start()
            
            # Main server loop
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    self.client_counter += 1
                    self.player_counter += 1
                    
                    client = Client(
                        socket=client_socket,
                        address=address,
                        id=self.client_counter,
                        player_number=self.player_counter
                    )
                    
                    # Start new thread for client
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client,),
                        daemon=True
                    )
                    client_thread.start()
                    
                    with self.client_lock:
                        self.clients.append(client)
                    
                    # Log and announce the new player connection
                    connection_msg = f"Player ({self.player_counter}) has connected"
                    print(connection_msg)
                    logging.info(f"{connection_msg} from {address}")
                    
                    # Handle player-specific logic
                    if self.player_counter == 1:
                        # Player 1 will wait for Player 2
                        wait_msg = "\nYou are Player (1). Waiting for Player 2 to connect...\n"
                        client.socket.send(wait_msg.encode())
                    
                    elif self.player_counter == 2:
                        # Player 2 connects, send the hint to Player 1
                        self.player_2_connected = True
                        prompt_msg = f"\nYou are Player (2). Please decode the password that Player (1) gave you.\n"
                        prompt_msg += f"The encoded password is: {self.encoded_password}\n"
                        prompt_msg += "Enter the decoded password:\n"
                        client.socket.send(prompt_msg.encode())
                        
                        # Now send the hint to Player 1
                        hint_msg = f"\nYou are Player (1). My favorite number is {self.rotation_value}.\n"
                        for c in self.clients:
                            if c.player_number == 1:
                                c.socket.send(hint_msg.encode())
                    
                    # Broadcast to other clients
                    self.broadcast(connection_msg, exclude_client=client)
                    
                except socket.error as e:
                    if self.running:
                        logging.error(f"Socket error: {e}")
                        
        except Exception as e:
            logging.error(f"Server error: {e}")
            self.shutdown()

    def handle_client(self, client: Client):
        """Handle individual client connections"""
        try:
            # Send welcome message
            welcome_msg = f"Welcome Player ({client.player_number})!\n".encode()
            client.socket.send(welcome_msg)
            
            while self.running:
                data = client.socket.recv(1024)
                if not data:
                    break
                    
                message = data.decode().strip()
                if message.lower() == 'quit':
                    break
                
                if client.player_number == 2:  # Player 2 enters the decoded password
                    if message.lower() == self.password.lower():
                        success_msg = "\nCongratulations! You successfully decoded the password!\n"
                        client.socket.send(success_msg.encode())
                        
                        # Check if the file exists, if so, send it to Player 1
                        self.send_file_to_player_1()
                        self.broadcast(f"Player (2) has successfully decoded the password!", exclude_client=client)
                        break  # End the game
                    else:
                        client.socket.send("Incorrect. Try again!\n".encode())

                # Add message to queue for processing
                self.message_queue.put((client, message))
                
        except socket.error as e:
            logging.error(f"Error handling Player ({client.player_number}): {e}")
        finally:
            ##Added code
            disconnection_msg = f"Player ({client.player_number}) has disconnected. Exiting program...\n"
            self.broadcast(disconnection_msg, exclude_client=client)

            for client in self.clients:
                client.socket.close()
            self.remove_client(client)
            ##Added code
            self.server_socket.close()

    def send_file_to_player_1(self):
        """Send the contents of the flag file to Player 1 if it exists"""
        try:
            file_path = "flag.txt"
            if os.path.exists(file_path):
                with open(file_path, "r") as file:
                    flag_content = file.read()
                
                for c in self.clients:
                    if c.player_number == 1:
                        c.socket.send(f"\nHere is your flag: {flag_content}\n".encode())
            else:
                logging.error(f"Flag file {file_path} not found!")
                
        except FileNotFoundError:
            logging.error("Flag file not found!")

    def handle_messages(self):
        """Process messages from the message queue"""
        while self.running:
            try:
                client, message = self.message_queue.get(timeout=1)
                logging.info(f"Message from Player ({client.player_number}): {message}")
                
                # Broadcast message to all clients
                self.broadcast(f"Player ({client.player_number}): {message}", exclude_client=client)
                
            except Exception:
                continue

    def broadcast(self, message: str, exclude_client: Optional[Client] = None):
        """Send message to all connected clients"""
        with self.client_lock:
            for client in self.clients:
                if exclude_client and client.id == exclude_client.id:
                    continue
                try:
                    client.socket.send(f"{message}\n".encode())
                except socket.error as e:
                    logging.error(f"Error broadcasting to Player ({client.player_number}): {e}")
                    self.remove_client(client)

    def remove_client(self, client: Client):
        """Remove a client from the server"""
        with self.client_lock:
            if client in self.clients:
                self.clients.remove(client)
                client.socket.close()
                self.broadcast(f"Player ({client.player_number}) has disconnected.", exclude_client=client)
                logging.info(f"Player ({client.player_number}) disconnected.")

    def shutdown(self):
        """Shutdown the server gracefully"""
        self.running = False
        for client in self.clients:
            client.socket.close()
        if self.server_socket:
            self.server_socket.close()
        logging.info("Server shutdown complete")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logging.info(f"Received signal {signum}")
        self.shutdown()
        sys.exit(0)

if __name__ == "__main__":
    # Create and start server
    server = SocketServer()
    server.start()


#Added Lines of 192-200
#If player 1 disconnects, the server will not send a message to player 2 and exit the program
#But if player 2 disconnects, the server will send a message to player 1 and exit the program