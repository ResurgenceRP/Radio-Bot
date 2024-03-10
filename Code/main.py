import discord
import asyncio
import json
from datetime import datetime, timedelta

# Setup for administration, processing and bot startup
TOKEN = 'YOUR_TOKEN_HERE'
CHANNEL_ID = MESSAGE_CHANNEL
ADMIN_CHANNEL_ID = ADMINISTRATOR_LOGS_CHANNEL

# Declaring intents to access messages and guilds
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True 

# Setting our intents as active
client = discord.Client(intents=intents)
deletion_schedule_file = 'deletion_schedule.json'

# Persistence Setup/Load

def save_deletion_schedule(schedule):
    """Saves the message deletion schedule to a file."""
    with open(deletion_schedule_file, 'w') as file:
        json.dump(schedule, file)

def load_deletion_schedule():
    """Loads the message deletion schedule from a file."""
    try:
        with open(deletion_schedule_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

async def delete_message_after_delay(message_id, channel_id, delay):
    """Deletes a message after a specified delay."""
    await asyncio.sleep(delay)
    channel = client.get_channel(channel_id)
    if channel:
        try:
            message = await channel.fetch_message(message_id)
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

async def schedule_deletions():
    """Schedules message deletions based on saved schedule."""
    schedule = load_deletion_schedule()
    now = datetime.utcnow()
    for msg_info, delete_time_str in schedule.items():
        delete_time = datetime.fromisoformat(delete_time_str)
        delay = (delete_time - now).total_seconds()
        if delay > 0:
            message_id, channel_id = map(int, msg_info.split('_'))
            asyncio.create_task(delete_message_after_delay(message_id, channel_id, delay))

# Logging purposes, confirming bot correctly loaded into discord gateway
@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    await schedule_deletions()


# Intercepting messages to repost
@client.event
async def on_message(message):
    if message.author == client.user or message.channel.id != CHANNEL_ID:
        return

# Setting "Empty message" as string if for some reason message is empty. Shouldnt happen but better safe than sorry
    message_content = message.content
    if not message_content:
        message_content = "(Empty message)"
    
    # Create an anonymized embed to replace sent message
    embed = discord.Embed(color=discord.Color.blue())
    embed.add_field(name="The radio crackles to life and you hear a voice...:", value=message_content, inline=False)
    embed.set_footer(text="ResurgenceRP Radio")
  
    # Create Staff Log embed with user name and user ID
    sender_id = message.author.id
    embed_admin = discord.Embed(color=discord.Color.blue())
    embed_admin.add_field(name=f"User: {message.author} ID: {sender_id} | Send a radio message: ", value=message_content, inline=False)
    embed_admin.set_footer(text="ResurgenceRP Radio Admin Log")

    # Send anonymized message
    reposted_message = await message.channel.send(embed=embed)
    await message.delete()

    # Send copy of original message including author to Administration Channel
    mod_channel = client.get_channel(ADMIN_CHANNEL_ID)
    await mod_channel.send(embed=embed_admin)

    # Schedule deletion of reposted message after 24 hours
    delete_time = datetime.utcnow() + timedelta(hours=24)
    schedule = load_deletion_schedule()
    schedule_key = f"{reposted_message.id}_{reposted_message.channel.id}"
    schedule[schedule_key] = delete_time.isoformat()
    save_deletion_schedule(schedule)

    # Calculate delay for deletion in seconds
    delay = (delete_time - datetime.utcnow()).total_seconds()
    asyncio.create_task(delete_message_after_delay(reposted_message.id, reposted_message.channel.id, delay))

# Actually start the bot
client.run(TOKEN)
