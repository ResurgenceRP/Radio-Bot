import discord
import asyncio
import yaml
import json
import logging
from datetime import datetime, timedelta
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
    USE_DATABASE: bool = False
    DATABASE: Optional[dict]

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

# Database connection pool
db_pool = None

async def init_db_pool():
    global db_pool
    if USE_DATABASE:
        try:
            db_pool = await create_pool(
                host=DB_CONFIG['HOST'],
                port=DB_CONFIG['PORT'],
                user=DB_CONFIG['USER'],
                password=DB_CONFIG['PASSWORD'],
                db=DB_CONFIG['DATABASE_NAME'],
                maxsize=5
            )
            logger.info("Database connection pool created successfully.")

            # Initialize tables
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
            raise RuntimeError("RUNTIME ERROR PLEASE CONTACT ADMINISTRATOR")

# Database interaction functions
async def save_deletion_to_db(message_id, channel_id, delete_time):
    if db_pool:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute(
                        "INSERT INTO deletion_schedule (message_id, channel_id, delete_time) "
                        "VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE delete_time = VALUES(delete_time)",
                        (message_id, channel_id, delete_time)
                    )
                    await conn.commit()
                except OperationalError as e:
                    logger.error("Error saving to database: %s", e)

async def load_deletion_schedule_from_db():
    schedule = {}
    if db_pool:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute("SELECT message_id, channel_id, delete_time FROM deletion_schedule")
                    rows = await cursor.fetchall()
                    for row in rows:
                        schedule[f"{row[0]}_{row[1]}"] = row[2].isoformat()
                except OperationalError as e:
                    logger.error("Error loading from database: %s", e)
    return schedule

async def delete_deletion_from_db(message_id, channel_id):
    if db_pool:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute(
                        "DELETE FROM deletion_schedule WHERE message_id = %s AND channel_id = %s",
                        (message_id, channel_id)
                    )
                    await conn.commit()
                except OperationalError as e:
                    logger.error("Error deleting from database: %s", e)

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

# Unified functions
async def save_deletion_schedule(schedule_key, delete_time):
    if USE_DATABASE:
        message_id, channel_id = map(int, schedule_key.split('_'))
        await save_deletion_to_db(message_id, channel_id, delete_time)
    else:
        schedule = load_deletion_schedule_from_file()
        schedule[schedule_key] = delete_time.isoformat()
        save_deletion_schedule_to_file(schedule)

async def load_deletion_schedule():
    if USE_DATABASE:
        return await load_deletion_schedule_from_db()
    else:
        return load_deletion_schedule_from_file()

async def delete_deletion_schedule(schedule_key):
    if USE_DATABASE:
        message_id, channel_id = map(int, schedule_key.split('_'))
        await delete_deletion_from_db(message_id, channel_id)
    else:
        schedule = load_deletion_schedule_from_file()
        if schedule_key in schedule:
            del schedule[schedule_key]
            save_deletion_schedule_to_file(schedule)

# Discord bot setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True 

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    logger.info('Logged in as %s', client.user)
    deletion_cleanup_task.start()

# Periodic cleanup task
@tasks.loop(minutes=10)
async def deletion_cleanup_task():
    now = datetime.utcnow()
    schedule = await load_deletion_schedule()
    for msg_info, delete_time_str in schedule.items():
        delete_time = datetime.fromisoformat(delete_time_str)
        if delete_time <= now:
            message_id, channel_id = map(int, msg_info.split('_'))
            asyncio.create_task(delete_message(message_id, channel_id))

@deletion_cleanup_task.before_loop
async def before_deletion_cleanup_task():
    await client.wait_until_ready()

# Message handling
@client.event
async def on_message(message):
    if message.author == client.user or message.channel.id != CHANNEL_ID:
        return

    try:
        # Split and embed message
        chunks = message.content.split()
        reposted_message = await message.channel.send(content=" ".join(chunks[:50]))
        await message.delete()

        # Schedule deletion
        delete_time = datetime.utcnow() + timedelta(hours=24)
        schedule_key = f"{reposted_message.id}_{reposted_message.channel.id}"
        await save_deletion_schedule(schedule_key, delete_time)

    except discord.HTTPException as e:
        logger.error("Failed to handle message: %s", e)

async def delete_message(message_id, channel_id):
    try:
        channel = client.get_channel(channel_id)
        if channel:
            message = await channel.fetch_message(message_id)
            await message.delete()
            await delete_deletion_schedule(f"{message_id}_{channel_id}")
    except discord.NotFound:
        logger.warning("Message %s not found for deletion.", message_id)
    except discord.Forbidden:
        logger.warning("Permission denied for deleting message %s.", message_id)
    except discord.HTTPException as e:
        logger.error("Unexpected error during message deletion: %s", e)

# Main bot entry
try:
    asyncio.run(init_db_pool())
    client.run(TOKEN)
except RuntimeError as e:
    logger.critical("Bot startup failed: %s", e)