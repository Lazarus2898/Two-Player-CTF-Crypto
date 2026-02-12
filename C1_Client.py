import socket
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class Client:
    def __init__(self, host: str = 'localhost', port: int = 8089):
        self.host = host
        self.port = port
        self.client_socket = None
        self.player_number = None

    def start(self):
        """Connect to the server and handle communication."""
        try:
            # Create a socket and connect to the server
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))
            logging.info(f"Connected to the server at {self.host}:{self.port}")

            # Receive and display the welcome message from the server
            welcome_msg = self.client_socket.recv(1024).decode()
            print(welcome_msg)

            # Receive the game prompt and handle the game
            while True:
                message = self.client_socket.recv(1024).decode()
                print(message)

                if "encoded password" in message:
                    # Player 1 received the encoded password
                    print(message)
                    self.decode_password()
                elif "decode the password" in message:
                    # Player 2 is prompted to decode the password
                    print(message)
                    self.decode_password()
                elif "The game is over" in message:
                    # The game is over, exit
                    print(message)
                    break  # Game over, exit the loop
                else:
                    print(message)

        except Exception as e:
            logging.error(f"Error occurred: {e}")
        finally:
            print("Player has disconnected....closing connections. . . .")
            if self.client_socket:
                self.client_socket.close()

    def decode_password(self):
        """Allow Player 2 to input the decoded password."""
        # Wait for player 2 to input the decoded password
        decoded_password = input("Enter the decoded password: ").strip()

        # Send the decoded password to the server
        self.client_socket.send(decoded_password.encode())

if __name__ == "__main__":
    client = Client()
    client.start()
    print("Player has disconnected....closing connections. . . .")