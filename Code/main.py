import discord
import asyncio
import yaml
import json
import logging
from datetime import datetime, timedelta, timezone
from discord.ext import tasks
from pydantic import BaseModel, ValidationError
from typing import Optional
from aiomysql import create_pool, OperationalError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] - %(message)s')
logger = logging.getLogger("DiscordBot")

# Pydantic configuration validation
class Config(BaseModel):
    TOKEN: str
    CHANNEL_ID: int
    ADMIN_CHANNEL_ID: int
    STAFF_ROLE_ID: int
    USE_DATABASE: bool = False
    DATABASE: Optional[dict]
    FOOTER_PUBLIC: str
    FOOTER_ADMIN: str

# Load configuration from YAML
def load_config(config_file='config.yaml') -> Config:
    with open(config_file, 'r') as file:
        raw_config = yaml.safe_load(file)
    return Config(**raw_config)

try:
    config = load_config()
except (FileNotFoundError, ValidationError) as e:
    logger.critical("Invalid configuration file: %s", e)
    exit(1)

TOKEN = config.TOKEN
CHANNEL_ID = config.CHANNEL_ID
ADMIN_CHANNEL_ID = config.ADMIN_CHANNEL_ID
USE_DATABASE = config.USE_DATABASE
DB_CONFIG = config.DATABASE
STAFF_ROLE_ID = config.STAFF_ROLE_ID
TEXT_FOOTER_PUBLIC = config.FOOTER_PUBLIC
TEXT_FOOTER_ADMIN = config.FOOTER_ADMIN

# Database connection pool
db_pool = None
notification_sent = False  # Track if the error notification has already been sent

def is_db_pool_ready():
    return db_pool is not None and not db_pool._closed

async def init_db_pool():
    global db_pool
    if USE_DATABASE:
        try:
            if db_pool and db_pool._closed:
                db_pool = None

            if db_pool is None:
                db_pool = await create_pool(
                    host=DB_CONFIG['HOST'],
                    port=DB_CONFIG['PORT'],
                    user=DB_CONFIG['USER'],
                    password=DB_CONFIG['PASSWORD'],
                    db=DB_CONFIG['DATABASE_NAME'],
                    maxsize=5
                )
                logger.info("Database connection pool created successfully.")

            async with db_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        CREATE TABLE IF NOT EXISTS deletion_schedule (
                            message_id BIGINT NOT NULL,
                            channel_id BIGINT NOT NULL,
                            delete_time DATETIME NOT NULL,
                            PRIMARY KEY (message_id, channel_id)
                        )
                    """)
                    logger.info("Table `deletion_schedule` ensured.")
        except OperationalError as e:
            logger.critical("Database connection failed: %s", e)
            await send_error_notification("Database initialization", repr(e))
            await shutdown_bot("Database initialization failed due to OperationalError.")

# JSON file fallback functions
deletion_schedule_file = 'deletion_schedule.json'

def save_deletion_schedule_to_file(schedule):
    with open(deletion_schedule_file, 'w') as file:
        json.dump(schedule, file)

def load_deletion_schedule_from_file():
    try:
        with open(deletion_schedule_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    
async def save_deletion_to_db(message_id, channel_id, delete_time, channel):
    if not is_db_pool_ready():
        logger.error("Database pool is not ready. Cannot save to database.")

async def save_deletion_schedule(schedule_key, delete_time, channel):
    """Save a message to the deletion schedule, either in the database or JSON file."""
    if USE_DATABASE:
        # Extract message_id and channel_id from the schedule key.
        message_id, channel_id = map(int, schedule_key.split('_'))
        await save_deletion_to_db(message_id, channel_id, delete_time, channel)
    else:
        schedule = load_deletion_schedule_from_file()
        schedule[schedule_key] = delete_time.isoformat()
        save_deletion_schedule_to_file(schedule)

async def load_deletion_schedule(channel):
    """Load the deletion schedule from the database or JSON file."""
    if USE_DATABASE:
        return await load_deletion_schedule_from_db(channel)
    else:
        return load_deletion_schedule_from_file()

async def delete_deletion_schedule(schedule_key, channel):
    """Delete a message from the deletion schedule."""
    if USE_DATABASE:
        # Extract message_id and channel_id from the schedule key.
        message_id, channel_id = map(int, schedule_key.split('_'))
        await delete_deletion_from_db(message_id, channel_id, channel)
    else:
        schedule = load_deletion_schedule_from_file()
        if schedule_key in schedule:
            del schedule[schedule_key]
            save_deletion_schedule_to_file(schedule)

async def save_deletion_to_db(message_id, channel_id, delete_time, channel):
    if not is_db_pool_ready():
        logger.error("Database pool is not ready. Cannot save to database.")
        return
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO deletion_schedule (message_id, channel_id, delete_time) "
                    "VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE delete_time = VALUES(delete_time)",
                    (message_id, channel_id, delete_time)
                )
                await conn.commit()
    except (OperationalError, Exception) as e:
        logger.error("Error saving to database: %s", repr(e))
        await notify_runtime_error("Error saving to database", repr(e))

async def load_deletion_schedule_from_db(channel):
    schedule = {}
    if is_db_pool_ready():
        try:
            async with db_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT message_id, channel_id, delete_time FROM deletion_schedule")
                    rows = await cursor.fetchall()
                    for row in rows:
                        schedule[f"{row[0]}_{row[1]}"] = row[2].isoformat()
        except (OperationalError, Exception) as e:
            logger.error("Error loading from database: %s", repr(e))
            await notify_runtime_error("Error loading from database", repr(e))
    return schedule

async def delete_deletion_from_db(message_id, channel_id, channel):
    if is_db_pool_ready():
        try:
            async with db_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "DELETE FROM deletion_schedule WHERE message_id = %s AND channel_id = %s",
                        (message_id, channel_id)
                    )
                    await conn.commit()
        except (OperationalError, Exception) as e:
            logger.error("Error deleting from database: %s", repr(e))
            await notify_runtime_error("Error deleting from database", repr(e))

async def notify_runtime_error(context, error_message):
    """Notify user and staff of a runtime error and post warning to admin channel."""
    global notification_sent
    if notification_sent:
        return
    notification_sent = True  # Prevent sending duplicate notifications

    try:
        # Notify the user in the public channel
        channel = client.get_channel(CHANNEL_ID)
        if channel:
            await channel.send("RUNTIME ERROR: If this persists, please contact staff for assistance.")

        # Notify staff about the runtime issue
        admin_channel = client.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            await admin_channel.send(f"<@&{STAFF_ROLE_ID}>: A runtime error occurred during '{context}'. Error details: {error_message}")

    except Exception as e:
        logger.critical("Failed to send runtime error notification: %s", repr(e))

async def delete_message(message_id, channel_id):
    """Deletes a specific message by its ID from a channel."""
    try:
        channel = client.get_channel(channel_id)
        if not channel:
            logger.error("Channel ID %s is invalid or inaccessible.", channel_id)
            return

        try:
            message = await channel.fetch_message(message_id)
            await message.delete()

            # If runtime error message, clear runtime_error_message_id
            global runtime_error_message_id
            if message_id == runtime_error_message_id:
                runtime_error_message_id = None

            await delete_deletion_schedule(f"{message_id}_{channel_id}", channel)
        except discord.NotFound:
            logger.warning("Message %s not found for deletion.", message_id)
        except discord.Forbidden:
            logger.warning("Permission denied for deleting message %s.", message_id)
    except discord.HTTPException as e:
        logger.error("Unexpected error during message deletion: %s", repr(e))



# Helper function to split message into chunks without breaking words
def split_message_into_chunks(message, chunk_size=1024):
    """Splits a message into smaller chunks, preserving words and periods to avoid abrupt cuts."""
    words = message.split()
    chunks = []
    current_chunk = ""

    for word in words:
        # If adding the next word would exceed the chunk size, finalize the current chunk.
        if len(current_chunk) + len(word) + 1 > chunk_size:
            if '.' in current_chunk:
                # Try to split at the last period within the limit.
                split_pos = current_chunk.rfind('.')
                chunks.append(current_chunk[:split_pos + 1])
                current_chunk = current_chunk[split_pos + 1:].strip() + " " + word
            else:
                chunks.append(current_chunk)
                current_chunk = word
        else:
            if current_chunk:
                current_chunk += " " + word
            else:
                current_chunk = word

    # Add the last chunk if any content remains.
    if current_chunk:
        chunks.append(current_chunk)

    return chunks

# Notify database error to staff and users
async def send_error_notification(context, error_message):
    """Notify user of a database error and post a warning to the admin channel."""
    global notification_sent
    if notification_sent:
        return
    notification_sent = True  # Prevent sending duplicate notifications

    try:
        # Notify the user in the public channel
        channel = client.get_channel(CHANNEL_ID)
        if channel:
            await channel.send("Error: Please contact staff to investigate")

        # Notify staff about the database issue
        admin_channel = client.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            await admin_channel.send(f"<@&{STAFF_ROLE_ID}>: An error occurred during '{context}'. Error details: {error_message}")

    except Exception as e:
        logger.critical("Failed to send error notification: %s", repr(e))

# Shutdown function to gracefully stop the bot
async def shutdown_bot(reason, notify=True):
    logger.critical(f"Shutting down bot: {reason}")

    # Send the error notification before shutting down, only if notify is True
    if notify:
        await send_error_notification("shutdown", reason)

    # Stop deletion cleanup task if it's running
    if deletion_cleanup_task.is_running():
        deletion_cleanup_task.stop()

    # Close the database connection pool
    if db_pool and not db_pool._closed:
        db_pool.close()
        await db_pool.wait_closed()

    # Log shutdown and close the bot
    logger.info("Bot is shutting down.")
    await client.close()

# Load the deletion schedule (updated missing function)
async def load_deletion_schedule(channel):
    if USE_DATABASE:
        return await load_deletion_schedule_from_db(channel)
    else:
        return load_deletion_schedule_from_file()

# Load deletion schedule from the database
async def load_deletion_schedule_from_db(channel):
    schedule = {}
    if is_db_pool_ready():
        try:
            async with db_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT message_id, channel_id, delete_time FROM deletion_schedule")
                    rows = await cursor.fetchall()
                    for row in rows:
                        schedule[f"{row[0]}_{row[1]}"] = row[2].isoformat()
        except (OperationalError, Exception) as e:
            logger.error("Error loading from database: %s", repr(e))
            await send_error_notification("Error loading from database", repr(e))
            await shutdown_bot("Error occurred while loading from the database.")
    return schedule

# Delete a message (updated missing function)
async def delete_message(message_id, channel_id):
    try:
        channel = client.get_channel(channel_id)
        if not channel:
            logger.error("Channel ID %s is invalid or inaccessible.", channel_id)
            return

        try:
            message = await channel.fetch_message(message_id)
            await message.delete()
            # If runtime error message, clear runtime_error_message_id
            global runtime_error_message_id
            if message_id == runtime_error_message_id:
                runtime_error_message_id = None
            await delete_deletion_schedule(f"{message_id}_{channel_id}", channel)
        except discord.NotFound:
            logger.warning("Message %s not found for deletion.", message_id)
        except discord.Forbidden:
            logger.warning("Permission denied for deleting message %s.", message_id)
    except discord.HTTPException as e:
        logger.error("Unexpected error during message deletion: %s", repr(e))

# Delete from the deletion schedule (updated missing function)
async def delete_deletion_schedule(schedule_key, channel):
    if USE_DATABASE:
        message_id, channel_id = map(int, schedule_key.split('_'))
        await delete_deletion_from_db(message_id, channel_id, channel)
    else:
        schedule = load_deletion_schedule_from_file()
        if schedule_key in schedule:
            del schedule[schedule_key]
            save_deletion_schedule_to_file(schedule)

# Delete deletion record from the database
async def delete_deletion_from_db(message_id, channel_id, channel):
    if is_db_pool_ready():
        try:
            async with db_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "DELETE FROM deletion_schedule WHERE message_id = %s AND channel_id = %s",
                        (message_id, channel_id)
                    )
                    await conn.commit()
        except (OperationalError, Exception) as e:
            logger.error("Error deleting from database: %s", repr(e))
            await send_error_notification("Error deleting from database", repr(e))
            await shutdown_bot("Error occurred while deleting from the database.")

# Discord bot setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True 

client = discord.Client(intents=intents)

runtime_error_message_id = None  # To track the error message

@client.event
async def on_ready():
    logger.info('Logged in as %s', client.user)
    await init_db_pool()
    deletion_cleanup_task.start()

@client.event
async def on_message(message):
    if message.author == client.user or message.channel.id != CHANNEL_ID:
        return

    try:
        # Split the message content into chunks without breaking words
        message_content = message.content or "(Empty message)"
        message_chunks = split_message_into_chunks(message_content)

        # Create an anonymized embed to replace the sent message
        embed = discord.Embed(color=discord.Color.blue())
        embed.add_field(name="The radio crackles to life and you hear a voice...:", value=message_chunks[0], inline=False)
        for chunk in message_chunks[1:]:
            embed.add_field(name="\u200b", value=chunk, inline=False)
        embed.set_footer(text=TEXT_FOOTER_PUBLIC)

        # Create Staff Log embed with user name, user ID, and a ping to the sender
        sender_id = message.author.id
        embed_admin = discord.Embed(color=discord.Color.blue())
        embed_admin.add_field(name=f"User: {message.author} ID: {sender_id} | Sent a radio message: ", value=message_chunks[0], inline=False)
        for chunk in message_chunks[1:]:
            embed_admin.add_field(name="\u200b", value=chunk, inline=False)
        embed_admin.set_footer(text=TEXT_FOOTER_ADMIN)

        # First, delete the original message.
        await message.delete()

        # Attempt to save the deletion schedule for the original message in the database.
        delete_time = datetime.now(timezone.utc) + timedelta(hours=24)
        schedule_key = f"{message.id}_{message.channel.id}"

        # Save the deletion schedule. If this fails, no message should be reposted.
        #await save_deletion_schedule(schedule_key, delete_time, message.channel)

        # If the database save was successful, repost the anonymized message.
        reposted_message = await message.channel.send(embed=embed)

        # Send a copy of the original message to the administration channel.
        mod_channel = client.get_channel(ADMIN_CHANNEL_ID)
        if mod_channel:
            await mod_channel.send(embed=embed_admin)

        # Update the schedule key for the reposted message.
        repost_schedule_key = f"{reposted_message.id}_{reposted_message.channel.id}"
        await save_deletion_schedule(repost_schedule_key, delete_time, message.channel)

    except OperationalError as oe:
        # If there's an operational error with the database, notify the staff but do not repost the message.
        logger.error("Database error during message handling: %s", repr(oe))
        await send_error_notification("processing message", repr(oe))
        await shutdown_bot("Database error during message handling.")

    except Exception as e:
        # Handle any other unexpected exceptions, notifying the staff but not reposting the message.
        logger.error("Unexpected error processing message: %s", repr(e))
        await send_error_notification("processing message", repr(e))
        await shutdown_bot("Unexpected error during message handling.")

@tasks.loop(seconds=30)
async def deletion_cleanup_task():
    try:
        now = datetime.now(timezone.utc)  # Ensure that now is timezone-aware
        channel = client.get_channel(CHANNEL_ID)  # Assuming it's okay to use this channel for typing during cleanup
        schedule = await load_deletion_schedule(channel)
        for msg_info, delete_time_str in schedule.items():
            delete_time = datetime.fromisoformat(delete_time_str).replace(tzinfo=timezone.utc)  # Ensure delete_time is also timezone-aware
            if delete_time <= now:
                message_id, channel_id = map(int, msg_info.split('_'))
                await delete_message(message_id, channel_id)
    except Exception as e:
        logger.error("Unhandled exception in deletion_cleanup_task: %s", repr(e))
        await send_error_notification("deletion_cleanup_task", repr(e))
        await shutdown_bot("Unhandled exception in deletion_cleanup_task.")

async def main():
    try:
        await client.start(TOKEN)
    except RuntimeError as e:
        logger.critical("Bot startup failed: %s", e)
        await send_error_notification("Bot startup", repr(e))
    except KeyboardInterrupt:
        # Catch manual shutdown and exit gracefully without notifying users or admins
        logger.info("Bot shutdown requested by KeyboardInterrupt.")
    finally:
        await shutdown_bot("KeyboardInterrupt - manual shutdown", notify=False)

asyncio.run(main())