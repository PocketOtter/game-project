import socket
import threading
import json
import pygame
import requests
import random
import time

# Initialize Pygame
pygame.init()
screen = pygame.display.set_mode((1680, 1050))
clock = pygame.time.Clock()
font = pygame.font.Font(None, 36)

# Game state
players = {0: {"x": 400, "y": 300}}  # Player 0 is local player
local_player_id = 0
server_running = False
clients = []
server_socket = None
client_socket = None
server_port = None  # Will be set dynamically
lan_games = []  # List of discovered LAN games (IP, port)
in_game_menu = False  # For in-game menu
selected_option = 0  # For menu navigation

# Networking functions
def start_server(is_lan=True):
    global server_socket, server_running, clients, server_port
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Try random ports until one is available
    for port in range(5000, 6000):
        try:
            server_socket.bind(("0.0.0.0", port))
            server_port = port
            break
        except:
            continue
    else:
        raise Exception("No available ports between 5000 and 6000")

    server_socket.listen(5)
    server_socket.settimeout(1.0)  # Non-blocking
    server_running = True
    ip = get_local_ip() if is_lan else get_public_ip()
    print(f"Server started on {ip}:{server_port}")
    return ip, server_port

def handle_client(client, player_id):
    while server_running:
        try:
            data = client.recv(1024).decode()
            if data:
                update = json.loads(data)
                players[player_id] = update
                for c in clients:
                    c.send(json.dumps(players).encode())
        except:
            clients.remove(client)
            del players[player_id]
            client.close()
            break

def server_thread(is_lan):
    global server_running
    try:
        ip, port = start_server(is_lan)
        if is_lan:
            # Start broadcasting for LAN discovery
            threading.Thread(target=broadcast_lan_game, args=(ip, port), daemon=True).start()
        
        while server_running:
            try:
                client, addr = server_socket.accept()
                print(f"Player joined from {addr[0]}")
                clients.append(client)
                player_id = len(clients)
                players[player_id] = {"x": 400, "y": 300}
                threading.Thread(target=handle_client, args=(client, player_id), daemon=True).start()
            except socket.timeout:
                continue  # Non-blocking accept
            except:
                break
        return ip, port
    except Exception as e:
        print(f"Server error: {e}")
        server_running = False
        return None, None

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_public_ip():
    try:
        return requests.get("https://api.ipify.org").text
    except:
        return "Unknown (check internet)"

def broadcast_lan_game(ip, port):
    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    message = f"GAME:{ip}:{port}".encode()
    
    while server_running:
        try:
            broadcast_socket.sendto(message, ("255.255.255.255", 55555))
            time.sleep(1)  # Broadcast every second
        except:
            break
    broadcast_socket.close()

def discover_lan_games():
    global lan_games
    discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    discovery_socket.bind(("0.0.0.0", 55555))
    discovery_socket.settimeout(0.1)  # Non-blocking

    while True:
        try:
            data, addr = discovery_socket.recvfrom(1024)
            if data.startswith(b"GAME:"):
                game_info = data.decode().split(":")
                ip, port = game_info[1], int(game_info[2])
                if (ip, port) not in lan_games:
                    lan_games.append((ip, port))
        except socket.timeout:
            break
    discovery_socket.close()

def connect_to_server(ip, port):
    global client_socket, local_player_id, players
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((ip, port))
        threading.Thread(target=receive_data, daemon=True).start()
        local_player_id = None
        return True
    except:
        return False

def receive_data():
    global players, local_player_id
    while client_socket:
        try:
            data = client_socket.recv(1024).decode()
            if data:
                players = json.loads(data)
                if local_player_id is None:
                    local_player_id = min(players.keys())
        except:
            client_socket.close()
            break

# Function to draw the custom cursor
def draw_cursor(x, y):
    pygame.draw.polygon(screen, (0, 255, 255, 50), [
        (x, y), (x, y + 40), (x + 30, y + 20)
    ])
    pygame.draw.polygon(screen, (0, 255, 255), [
        (x, y), (x, y + 40), (x + 30, y + 20)
    ], 2)
    pygame.draw.polygon(screen, (0, 0, 0), [
        (x + 2, y + 2), (x + 2, y + 38), (x + 28, y + 20)
    ])

# Menu and game loop
running = True
mode = "main_menu"
port_input = ""
message = ""
selected_option = 0
in_game_menu_options = [
    "Exit To Main Menu (E)",
    "Open To LAN (O)",
    "Host Game (H)"
]

# Start LAN discovery in a separate thread
threading.Thread(target=discover_lan_games, daemon=True).start()

main_menu_options = [
    "Single-Player (S)",
    "Multiplayer (M)",
    "Controls (C)",
    "Quit (Q)"
]
multiplayer_menu_options = [
    "Host LAN (H)",
    "Host Online (O)",
    "Join Game (J)",
    "Back (B)"
]

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if mode in ["single", "lan_host", "online_host"] and not in_game_menu:
                if event.key == pygame.K_ESCAPE:
                    in_game_menu = True
                    selected_option = 0
            elif in_game_menu:
                if event.key == pygame.K_e:  # Exit To Main Menu
                    selected_option = 0
                    in_game_menu = False
                    mode = "main_menu"
                    selected_option = 0
                    if server_running:
                        server_running = False
                        server_socket.close()
                        clients.clear()
                    if client_socket:
                        client_socket.close()
                        client_socket = None
                    players.clear()
                    players[0] = {"x": 400, "y": 300}
                elif event.key == pygame.K_o and mode != "lan_host" and mode != "online_host":  # Open To LAN
                    selected_option = 1
                    in_game_menu = False
                    mode = "lan_host"
                    threading.Thread(target=server_thread, args=(True,), daemon=True).start()
                elif event.key == pygame.K_h and mode != "lan_host" and mode != "online_host":  # Host Game
                    selected_option = 2
                    in_game_menu = False
                    mode = "online_host"
                    threading.Thread(target=server_thread, args=(False,), daemon=True).start()
                elif event.key == pygame.K_ESCAPE:
                    in_game_menu = False
            elif mode == "main_menu":
                if event.key == pygame.K_s:  # Single-Player
                    selected_option = 0
                    mode = "single"
                elif event.key == pygame.K_m:  # Multiplayer
                    selected_option = 1
                    mode = "multiplayer_menu"
                    lan_games.clear()
                    threading.Thread(target=discover_lan_games, daemon=True).start()
                elif event.key == pygame.K_c:  # Controls
                    selected_option = 2
                    mode = "controls_menu"
                elif event.key == pygame.K_q:  # Quit
                    selected_option = 3
                    running = False
            elif mode == "multiplayer_menu":
                if event.key == pygame.K_h:  # Host LAN
                    selected_option = 0
                    mode = "lan_host"
                    threading.Thread(target=server_thread, args=(True,), daemon=True).start()
                elif event.key == pygame.K_o:  # Host Online
                    selected_option = 1
                    mode = "online_host"
                    threading.Thread(target=server_thread, args=(False,), daemon=True).start()
                elif event.key == pygame.K_j:  # Join Game
                    selected_option = 2
                    mode = "join_prompt"
                    port_input = ""
                elif event.key == pygame.K_b:  # Back
                    selected_option = 3
                    mode = "main_menu"
                    selected_option = 0
            elif mode == "controls_menu":
                if event.key == pygame.K_b or event.key == pygame.K_RETURN:
                    mode = "main_menu"
                    selected_option = 0
            elif mode == "join_prompt":
                if event.key == pygame.K_RETURN:
                    if port_input:
                        port = int(port_input)
                        for ip, lan_port in lan_games:
                            if lan_port == port:
                                if connect_to_server(ip, port):
                                    mode = "lan_client"
                                    message = f"Connected to port {port}"
                                    break
                        else:
                            ip = get_public_ip()
                            if connect_to_server(ip, port):
                                mode = "online_client"
                                message = f"Connected to port {port}"
                            else:
                                message = "Failed to connect"
                                mode = "multiplayer_menu"
                elif event.key == pygame.K_BACKSPACE:
                    port_input = port_input[:-1]
                elif event.key == pygame.K_b:
                    mode = "multiplayer_menu"
                    selected_option = 0
                else:
                    port_input += event.unicode

    # Player movement
    if mode in ["single", "lan_host", "online_host"] and not in_game_menu:
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            players[0]["x"] -= 5
        if keys[pygame.K_RIGHT]:
            players[0]["x"] += 5
        if keys[pygame.K_UP]:
            players[0]["y"] -= 5
        if keys[pygame.K_DOWN]:
            players[0]["y"] += 5

    # Send data if client
    if mode in ["lan_client", "online_client"] and client_socket:
        client_socket.send(json.dumps(players[local_player_id]).encode())

    # Render
    screen.fill((0, 0, 0))
    if mode == "main_menu":
        for i, text in enumerate(main_menu_options):
            color = (255, 255, 255)
            render = font.render(text, True, color)
            y_pos = 200 + i * 40
            screen.blit(render, (250, y_pos))
            if i == selected_option:
                draw_cursor(210, y_pos)
    elif mode == "multiplayer_menu":
        for i, text in enumerate(multiplayer_menu_options):
            color = (255, 255, 255)
            render = font.render(text, True, color)
            y_pos = 200 + i * 40
            screen.blit(render, (250, y_pos))
            if i == selected_option:
                draw_cursor(210, y_pos)
        if lan_games:
            y_pos = 400
            render = font.render("Discovered LAN Games:", True, (255, 255, 255))
            screen.blit(render, (100, y_pos))
            for i, (ip, port) in enumerate(lan_games):
                render = font.render(f"Port: {port}", True, (255, 255, 255))
                screen.blit(render, (100, y_pos + (i + 1) * 30))
    elif mode == "controls_menu":
        controls = [
            "Controls:",
            "Arrow Keys - Move",
            "Escape - Open In-Game Menu",
            "Main Menu:",
            "S - Single-Player",
            "M - Multiplayer",
            "C - Controls",
            "Q - Quit",
            "Multiplayer Menu:",
            "H - Host LAN",
            "O - Host Online",
            "J - Join Game",
            "B - Back",
            "In-Game Menu:",
            "E - Exit To Main Menu",
            "O - Open To LAN",
            "H - Host Game"
        ]
        for i, text in enumerate(controls):
            render = font.render(text, True, (255, 255, 255))
            screen.blit(render, (100, 100 + i * 30))
        back_text = font.render("Press B or Enter to go back", True, (255, 255, 255))
        screen.blit(back_text, (100, 620))
    elif mode == "join_prompt":
        prompt = font.render("Enter port to join (e.g., 54321):", True, (255, 255, 255))
        port_text = font.render(port_input, True, (255, 255, 255))
        back_text = font.render("Press B to go back", True, (255, 255, 255))
        screen.blit(prompt, (100, 200))
        screen.blit(port_text, (100, 240))
        screen.blit(back_text, (100, 280))
    else:  # Game modes
        for pid, pos in players.items():
            color = (255, 0, 0) if pid == local_player_id else (0, 0, 255)
            pygame.draw.rect(screen, color, (pos["x"], pos["y"], 20, 20))

        if in_game_menu:
            for i, text in enumerate(in_game_menu_options):
                color = (255, 255, 255)
                render = font.render(text, True, color)
                y_pos = 200 + i * 40
                screen.blit(render, (250, y_pos))
                if i == selected_option:
                    draw_cursor(210, y_pos)

    if message and mode not in ["main_menu", "multiplayer_menu", "controls_menu"]:
        msg_text = font.render(message, True, (255, 255, 255))
        screen.blit(msg_text, (10, 10))

    pygame.display.flip()
    clock.tick(60)

# Cleanup
if server_running:
    server_running = False
    server_socket.close()
if client_socket:
    client_socket.close()
pygame.quit()