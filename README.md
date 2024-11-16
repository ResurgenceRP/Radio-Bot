# RADIO BOT FOR ROLEPLAY SERVERS

## Introduction

This Discord bot is specifically designed for DayZ Roleplay (RP) communities, aiming to enhance the immersive experience within Discord servers dedicated to role-playing within the DayZ universe. It facilitates role-play by handling in-character radio communications and automating message management to maintain a clean and focused role-play environment.

## Features

- **In-Character Radio Communication:**
  - Captures messages sent to a designated channel (the in-game radio channel) and reposts them embedded in a format simulating radio communication, enhancing role-play immersion.

- **Administration Log:**
  - Each radio message is reposted to an admin-specific channel with detailed metadata, including the author's Discord tag and ID. This feature aids administrators in monitoring in-character communication for moderation.

- **Automated Message Deletion:**
  - Reposted radio messages are automatically deleted after 24 hours (configurable). This ensures that the channel remains clutter-free and focused on relevant role-play communication.

- **Scheduled Cleanup:**
  - Uses a periodic (each 30 seconds) cleanup task to handle expired messages efficiently, ensuring performance and scalability.

## Setup Instructions

### 1. **Get Your Bot Token**
   - Visit the [Discord Developer Portal](https://discord.com/developers/applications).
   - Log in with your Discord account.
   - Click the "New Application" button at the top-right.
   - Enter a name for your bot (e.g., "Radio Bot") and click "Create."
   - In the application's settings menu on the left, select the **Bot** tab and click "Add Bot."
   - Confirm by clicking "Yes, do it!"
   - Under the **Bot** tab, scroll down to "Token" and click the "Copy" button to copy your bot token.
   - While in the **Bot** tab, enable the following intents: **Presence Intent**, **Server Members Intent**, **Message Content Intent**
   > [!CAUTION]
   > Keep your token secret! Do not share it publicly.

### 2. **Get Your Channel IDs**
   - Open your Discord application.
   - Enable Developer Mode:
     - Go to **User Settings** (click the gear icon in the bottom-left).
     - Under **Advanced**, toggle on **Developer Mode**.
   - Right-click on the desired channel and select **Copy ID**:
     - **Radio Channel ID:** Right-click the channel where users will send in-character radio messages.
     - **Admin Channel ID:** Right-click the channel where administrative logs will be sent.
   - Paste the copied IDs into a text file for safekeeping.

### 3. **Install Python and Required Libraries**
   - Ensure Python 3.9+ is installed on your system.
   - Install the required libraries:
     ```bash
     pip install -U discord.py aiomysql pydantic PyYAML
     ```

### 4. **Configure the Bot**
   - Edit `config.yaml` file in the same directory as the script with the following structure:
     ```yaml
        TOKEN: "TOKEN"                                          # Discord bot token, string
        CHANNEL_ID: 1307016491677519943                         # Channel ID for bot to listen in, integer
        ADMIN_CHANNEL_ID: 1307016506739130400                   # Channel ID of channel for administrator login (Player name, Message, no autodeletion), integer
        STAFF_ROLE_ID: 1307026532895817829                      # Role ID of staff member group to ping on critical errors, integer
        FOOTER_PUBLIC: "Embeed Footer for Public Reposts."      # Footer used in public channels, should not be empty | String
        FOOTER_ADMIN: "Message Footer used in Admin channels"   # Footer used in Admin Channel, should not be empty | String

        # OPTIONAL !!!! Change flatfile storage to SQL based database:
        USE_DATABASE: false                                     # Change to "true" to enable Database Storage, set to "false" to switch to flatfile storage. Default value: false, Boolean
        DATABASE:
          HOST: "localhost"                                     # Location of database server, string
          PORT: 3306                                            # Port database is listening on, integer
          USER: "USERNAME"                                      # username in database with access to database defined in DATABASE_NAME, string
          PASSWORD: "PASSWORD"                                  # Password to USER account, string
          DATABASE_NAME: "DATABASE_NAME"                        # Database name, default: RADIO_BOT, string
     ``` 
   > [!IMPORTANT]  
   > If you decide to use database storage, it is important to create a new dedicated database user for the bot following your flavor of database instructions. Avoid using admin accounts with broad access ranges for security reasons. If you are unsure which is a better choice for you, flatfile storage is a safer bet albeit might be slower on servers with a lot of messages being sent.

### 5. **Run the Bot**
   - Navigate to the directory containing the script and `config.yaml`.
   - Start the bot:
     ```bash
     python main.py
     ```
   - Alternatively, set up the bot as a service [Linux]:
     ```ini
     [Unit]
     Description=Radio Bot Service

     [Service]
     ExecStart=python3 main.py
     WorkingDirectory=/path/to/script
     Restart=always

     [Install]
     WantedBy=multi-user.target
     ```
   > [!TIP]  
   > Setting the bot to run as a service will allow it to automatically start after a crash or server reboot.

### 6. **MySQL Database Setup**
   - If using a database, ensure MySQL is running and accessible.
   - The bot will automatically create the required `deletion_schedule` table if it doesn’t exist.

### 7. **Bot Permissions**
   - Make sure your bot has the following permissions in appropriate channels:
     - Read Messages
     - Send Messages
     - Manage Messages
     - Embed Links

## Usage

Once set up, the bot will automatically:
- Handle messages sent to the designated radio channel.
- Repost messages in an immersive, in-character radio format.
- Log messages in the admin channel for moderation purposes.
- Delete reposted messages after the specified duration (default: 24 hours).
- Notify administrators in case of critical errors (e.g., database failures).
- Shutdown gracefully when a critical error is encountered.

### Example Configuration Validation Errors
If your `config.yaml` file is missing required keys or has invalid types, the bot will display detailed validation errors to help you fix the configuration.

## Advanced Features

- **Periodic Cleanup:**
  - The bot uses a periodic task to delete expired messages efficiently, ensuring smooth operation even under high usage.

- **Retry Mechanisms:**
  - Automatically retries Discord API calls when encountering rate limits or transient errors.


This code is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability, whether in an action of contract, tort or otherwise, arising from, out of, or in connection with the code or the use or other dealings in the code.
