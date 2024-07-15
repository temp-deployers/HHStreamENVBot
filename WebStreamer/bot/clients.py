import asyncio
import logging
import os
import base64
import requests
from ..vars import Var
from pyrogram import Client
from WebStreamer.utils import TokenParser
from . import multi_clients, work_loads, StreamBot

parser = TokenParser()
GITHUB_TOKEN = parser.get_github_token()
GITHUB_USERNAME = parser.get_github_username()
GITHUB_REPO = parser.get_github_repo()
GITHUB_API_URL = "https://api.github.com"

def upload_to_github(file_path, repo_path):
    try:
        if not os.path.exists(file_path):
            print(f"File {file_path} does not exist, skipping upload")
            return
        
        # Construct the API URL for the file in the repository
        url = f"{GITHUB_API_URL}/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{repo_path}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            # File exists, extract current content details
            print(f"File Found: {repo_path}")
            current_content = response.json()
            sha = current_content.get('sha', '')
            print(f"SHA: {sha}")
        elif response.status_code == 404:
            # File does not exist, initialize sha as empty string
            print(f"File Not Found: {repo_path}")
            sha = ''
        else:
            # Handle other response codes
            print(f"Failed to check {repo_path} on GitHub. Status code: {response.status_code}")
            response.raise_for_status()
        
        # Read the file content to upload
        with open(file_path, "rb") as file:
            content = base64.b64encode(file.read()).decode()
        
        # Prepare data for updating or creating the file
        data = {
            "message": f"Update {repo_path}",
            "content": content,
            "branch": "main"  # Adjust the branch as needed
        }

        if sha != '':
            data["sha"] = sha
        
        # Send PUT request to update the file if sha is provided; otherwise, POST to create new file
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        print(f"Trying to Upload {file_path} to GitHub")
        response = requests.put(url, json=data, headers=headers)
        
        response.raise_for_status()
        
        if response.status_code == 200 or response.status_code == 201:
            print(f"Updated {repo_path} on GitHub")
        else:
            print(f"Failed to update {repo_path} on GitHub. Status code: {response.status_code}")
    
    except Exception as e:
        print(f"Failed to upload {file_path} to GitHub")
        print(e)

def download_from_github(repo_path):
    try:
        print(f"Downloading {repo_path} from GitHub")
        print(f"Current directory: {os.getcwd()}")  # Print current working directory
        
        url = f"{GITHUB_API_URL}/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{repo_path}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            content = base64.b64decode(response.json()["content"])
            
            # Extract file name from repo_path
            file_name = os.path.basename(repo_path)
            file_path = os.path.join(os.getcwd(), file_name)
            
            # Write content to file
            with open(file_path, "wb") as file:
                file.write(content)
            
            print(f"Downloaded {repo_path} from GitHub to {file_path}")
        
        elif response.status_code == 404:
            print(f"{repo_path} not found in GitHub, proceeding without session file")
        else:
            response.raise_for_status()
    
    except Exception as e:
        print(f"Failed to download {repo_path} from GitHub, proceeding without session file")
        print(e)

async def initialize_clients():
    multi_clients[0] = StreamBot
    work_loads[0] = 0
    all_tokens = parser.parse_from_env()
    if not all_tokens:
        print("No additional clients found, using default client")
        return

    async def start_client(client_id, token):
        try:
            print(f"Starting - Client {client_id}")
            if client_id == len(all_tokens):
                await asyncio.sleep(2)
                print("This will take some time, please wait...")
            session_name = f"client_{client_id}_session"
            session_file = f"{session_name}.session"

            # Download session file from GitHub
            download_from_github(session_file)

            client = await Client(
                name=session_name,
                api_id=Var.API_ID,
                api_hash=Var.API_HASH,
                bot_token=token,
                sleep_threshold=Var.SLEEP_THRESHOLD,
                no_updates=True,
                in_memory=False
            ).start()
            work_loads[client_id] = 0

            # Upload session file to GitHub
            upload_to_github(session_file, session_file)

            return client_id, client
        except Exception:
            logging.error(f"Failed starting Client - {client_id} Error:", exc_info=True)

    clients = await asyncio.gather(*[start_client(i, token) for i, token in all_tokens.items()])
    multi_clients.update(dict(clients))
    if len(multi_clients) != 1:
        Var.MULTI_CLIENT = True
        print("Multi-Client Mode Enabled")
    else:
        print("No additional clients were initialized, using default client")
