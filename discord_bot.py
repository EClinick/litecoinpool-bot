import os
import logging
from dotenv import load_dotenv
from discord import Intents, Client, Message, Forbidden, HTTPException, NotFound
from crypto_utils import get_responses, get_data, filtering_data
import requests
import aiohttp
import asyncio
import json

# Configure logging (console only, no file)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

#Step 1: Bot SETUP

intents: Intents=Intents.default()
intents.guilds=True
intents.messages=True

intents.message_content=True #NOQA
client: Client= Client(intents=intents)
#If starts with !

# Load environment variables from .env file
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
POWER_USAGE = int(os.getenv('POWER_USAGE'))
ENERGY_COST_PER_KWH = float(os.getenv('ENERGY_COST_PER_KWH'))
HOURS_PER_DAY = int(os.getenv('HOURS_PER_DAY'))
API_KEY = os.getenv('LITECOINPOOL_API_KEY')
URL = f'https://www.litecoinpool.org/api?api_key={API_KEY}'

power_usage = POWER_USAGE  # in Watts
energy_cost_per_kWh = ENERGY_COST_PER_KWH  # in USD
hours_per_day = HOURS_PER_DAY

# At the top of the file with other global variables
offline_workers = set()  # Track offline workers
announced_offline = set()  # Track workers we've already announced as offline

#step 2: MESSAGE FUNCTINALITY
async def send_message(message: Message, user_message: str) -> None:
    if not user_message:
        logger.warning("Message was empty because intents weren't enabled")
        return
    
    try:
        is_private = user_message.startswith('?')
        user_message = user_message[1:] if is_private else user_message
        
        logger.info(f"Processing command: {user_message} from user: {message.author}")
        
        message_chunks = get_responses(user_message)
        for chunk in message_chunks:
            if is_private:
                await message.author.send(chunk)
                logger.info(f"Sent private message to {message.author}: {chunk}")
            else:
                await message.channel.send(chunk)
                logger.info(f"Sent message to channel {message.channel}: {chunk}")
                
    except Exception as e:
        logger.error(f"Error sending message: {e}", exc_info=True)

def calculate_profitability(data, power_usage, energy_cost_per_kWh):
    # Extracting data from the JSON
    expected_rewards_ltc = data['user']['expected_24h_rewards']
    expected_rewards_doge = data['user']['expected_24h_rewards_doge']
    
    ltc_usd_price = data['market']['ltc_usd']
    doge_usd_price = data['market']['doge_usd']
    
    # Calculating the expected rewards in USD
    expected_earnings_ltc = expected_rewards_ltc * ltc_usd_price
    expected_earnings_doge = expected_rewards_doge * doge_usd_price
    total_expected_earnings = expected_earnings_ltc + expected_earnings_doge
    
    # Calculating the electricity costs
    daily_energy_consumption_kWh = (power_usage * hours_per_day) / 1000
    daily_electricity_cost = daily_energy_consumption_kWh * energy_cost_per_kWh
    
    # Calculating profit
    profit = total_expected_earnings - daily_electricity_cost
    
    return profit

async def check_profit():
    global was_profitable
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(URL) as response:
                    profit=calculate_profitability(response, power_usage, energy_cost_per_kWh)
                    if profit<=0 and was_profitable:
                        channel=await client.fetch_channel(CHANNEL_ID)
                        await channel.send("Mining is not profitable. PLEASE STOP miners.")
                        was_profitable=False
                    elif profit>0 and not was_profitable:
                        channel=await client.fetch_channel(CHANNEL_ID)
                        await channel.send("Mining is profitable. Continue mining.")
                        was_profitable=True
        except Exception as e:
            print(f"An error occured while checking profitability: {e}")
        await asyncio.sleep(30)

async def check_worker_hashrates_and_notify():
    while True:
        try:
            data = get_data(URL)
            logger.info("Retrieved worker data from API")
            workers = data['workers']
            for worker_name, worker_info in workers.items():
                logger.info(f"Checking worker: {worker_name}, hash rate: {worker_info['hash_rate']}")
                
                if worker_info['hash_rate'] == 0:
                    offline_workers.add(worker_name)
                    # Only announce if we haven't announced this worker yet
                    if worker_name not in announced_offline:
                        logger.warning(f"Worker {worker_name} has zero hash rate!")
                        channel = await client.fetch_channel(CHANNEL_ID)
                        await channel.send(f"""```
🚨 Worker Alert!

📡 Worker Details:
└─ 🖥️ Name: {worker_name}
└─ ⚠️ Status: OFFLINE
└─ ⚡ Hash Rate: 0 kH/s```""")
                        announced_offline.add(worker_name)  # Mark as announced
                
                elif worker_name in offline_workers:
                    # Worker is back online
                    channel = await client.fetch_channel(CHANNEL_ID)
                    await channel.send(f"""```
✅ Worker Recovery!

📡 Worker Details:
└─ 🖥️ Name: {worker_name}
└─ 🟢 Status: ONLINE
└─ ⚡ Hash Rate: {worker_info["hash_rate"]:.2f} kH/s```""")
                    offline_workers.remove(worker_name)
                    announced_offline.remove(worker_name)  # Remove from announced list
                    
        except Exception as e:
            logger.error(f"Error checking worker hash rates: {e}", exc_info=True)
        await asyncio.sleep(30)

async def fetch_total_per_day():
    while True:
        try:
            data = get_data(URL)
            total_usd_LTC, total_usd_DOGE, total_usd = filtering_data(data)
            profit_day = calculate_profitability(data, power_usage, energy_cost_per_kWh)
            channel = await client.fetch_channel(CHANNEL_ID)
            
            worker_status = """```
📊 Daily Mining Report

🖥️ Worker Status:"""
            workers = data['workers']
            for worker_name, worker_info in workers.items():
                status = "🟢 ONLINE" if worker_info['hash_rate'] > 0 else "🔴 OFFLINE"
                worker_status += f"\n└─ 📡 {worker_name}: {status} (⚡ {worker_info['hash_rate']:.2f} kH/s)"
            
            profit_status = "📈 PROFITABLE" if profit_day > 0 else "📉 NOT PROFITABLE"
            worker_status += f"""

💰 Financial Summary:
└─ 💸 LTC Rewards: ${total_usd_LTC:.2f}
└─ 🐕 DOGE Rewards: ${total_usd_DOGE:.2f}
└─ 💵 Total Rewards: ${total_usd:.2f}
└─ 📊 Daily Profit: ${profit_day:.2f}
└─ 📈 Status: {profit_status}```"""
            
            await channel.send(worker_status)
        except Exception as e:
            logger.error(f"Error fetching total rewards: {e}")
        await asyncio.sleep(86400)

@client.event
async def on_ready():
    logger.info(f'{client.user} is now running and ready.')
    logger.info(f"Using CHANNEL_ID: {CHANNEL_ID}")
    
    try:
        channel = await client.fetch_channel(CHANNEL_ID)
        if channel:
            logger.info(f"Channel found: {channel.name}")
            client.loop.create_task(check_worker_hashrates_and_notify())
            client.loop.create_task(fetch_total_per_day())
        else:
            logger.error(f"Failed to find channel with ID: {CHANNEL_ID}")
    except Exception as e:
        logger.error(f"Error in on_ready: {e}", exc_info=True)

#step 4: handling the messages for our bot
@client.event
async def on_message(message: Message) -> None:
    if message.author == client.user:
        return

    if not message.content.startswith('?'):
        return

    user_message: str = message.content
    username: str = str(message.author)
    channel: str = str(message.channel)

    logger.info(f'Command received - Channel: [{channel}] User: {username} Message: {user_message}')
    await send_message(message, user_message)


#step 5: Run the bot

def main() -> None:
    logger.info("Starting bot...")
    client.run(TOKEN)

if __name__ == '__main__':
    main()