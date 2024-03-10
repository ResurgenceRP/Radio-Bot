# RADIO BOT FOR ROLEPLAY SERVERS

## Introduction

This Discord bot is specifically designed for DayZ Roleplay (RP) communities, aiming to enhance the immersive experience within Discord servers dedicated to role-playing within the DayZ universe. It facilitates role-play by handling in-character radio communications and automating message management to maintain a clean and focused role-play environment.

## Features

- **In-Character Radio Communication:** The bot captures messages sent to a specific channel (designated as the in-game radio channel) and reposts them embedded in a format that simulates radio communication, thereby enhancing the role-play immersion. Each message is clearly labeled as a radio transmission, making it distinct from out-of-character communication.

- **Administration Log:** Each radio message sent through the bot is also reposted to an admin-specific channel. This copy includes the author's Discord tag and ID, aiding moderators and administrators in monitoring and managing in-character communication.

- **Automated Message Deletion:** To prevent clutter and maintain a clean channel, the bot automatically deletes the reposted radio messages after a set period (default is 24 hours). This feature helps in managing the flow of messages, ensuring that the radio channel remains relevant and easy to follow.

- **Persistence:** The bot maintains a schedule of message deletions, saving this information between restarts to ensure that message management remains consistent, even after downtime.

## Setup Instructions

1. **Prepare Your Discord Bot Token and Channel IDs:**
   - You must have a Discord bot token and the IDs for the channels you wish to use. The `TOKEN` variable is your bot's token (Get it from [Discord Developer Panel](https://discord.com/developers/applications) ). `CHANNEL_ID` is for the channel where users will send their in-character radio messages, and `ADMIN_CHANNEL_ID` is for the channel where copies of these messages will be sent for administrative purposes.

2. **Install Python and discord.py:**
   - Ensure Python 3 is installed on your system.
   - Install the `discord.py` library using pip:
     ```
     pip install -U discord.py
     ```

3. **Place the Script in Your Environment:**
   - Save the provided Python script to a directory of your choice on the host machine.

4. **Running the Bot:**
   - Navigate to the directory where you saved the script.
   - Run the bot using the following command:
     ```
     python <script_name>.py
     ```
     Replace `<script_name>` with the name of your Python script file.

     Alternatively you can setup bot as service using something similar to:
     ```
     [Unit]
     Description=SERVICE_NAME

     [Service]
     ExecStart=python3 main.py
     WorkingDirectory=PATH_TO_MAIN.PY
     Restart=always

     [Install]
     WantedBy=multi-user.target
     ```
     
5. **Bot Permissions:**
   - Make sure your bot has the necessary permissions on your Discord server to read and send messages, manage messages, and embed links in both the radio and admin channels.

## Usage

Once set up, the bot will automatically handle messages sent to the designated radio channel, reposting them in an immersive format and logging them for administrative purposes. Messages will be scheduled for automatic deletion 24 hours after being reposted, maintaining channel hygiene without manual intervention.


## Disclaimer:
This code is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability, whether in an action of contract, tort or otherwise, arising from, out of, or in connection with the code or the use or other dealings in the code.

