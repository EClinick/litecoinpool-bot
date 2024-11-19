import os
import logging
from dotenv import load_dotenv
import requests

# Configure logging (console only, no file)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables with defaults
API_KEY = os.getenv('LITECOINPOOL_API_KEY')
URL = f'https://www.litecoinpool.org/api?api_key={API_KEY}'
POWER_USAGE = int(os.getenv('POWER_USAGE', '1392'))  # Default: 1392W
ENERGY_COST_PER_KWH = float(os.getenv('ENERGY_COST_PER_KWH', '0.034'))  # Default: $0.034/kWh
HOURS_PER_DAY = int(os.getenv('HOURS_PER_DAY', '24'))  # Default: 24 hours

def get_data(url):
    try:
        logger.info(f"Fetching data from {url}")
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        data = response.json()
        logger.debug(f"Received data: {data}")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data: {e}", exc_info=True)
        raise

def filtering_data(data):
    total_rewards_LTC = data["user"]["total_rewards"]
    ltc_usd_rate = data["market"]["ltc_usd"]
    total_rewards_DOGE = data["user"]["total_rewards_doge"]
    doge_usd_rate = data["market"]["doge_usd"]

    total_usd_LTC = total_rewards_LTC * ltc_usd_rate
    total_usd_DOGE = total_rewards_DOGE * doge_usd_rate
    total_usd = total_usd_LTC + total_usd_DOGE

    return total_usd_LTC, total_usd_DOGE, total_usd

def calculate_profitability(data, power_usage, energy_cost_per_kWh, hours_per_day):
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

def get_responses(user_input: str):
    try:
        lowered = user_input.lower()
        logger.info(f"Processing command: {lowered}")

        help_response = """```
📋 Available Commands

💰 Mining & Profitability
?total    - 💵 View total rewards in USD (LTC + DOGE combined)
?profit   - 📊 Check expected daily profit/loss
?ltc      - 🪙 Show current Litecoin (LTC) price
?doge     - 🐕 Show current Dogecoin (DOGE) price

ℹ️ Help & Information
?help     - 📚 Show this help message

⚡ Updates:
• Worker status: Every 30s
• Daily totals: Every 24h
• All values in USD```"""

        if lowered == 'help':
            return [help_response]
        if lowered == 'total':
            data = get_data(URL)
            total_usd_LTC, total_usd_DOGE, total_usd = filtering_data(data)
            logger.info(f"Calculated totals - LTC: ${total_usd_LTC}, DOGE: ${total_usd_DOGE}, Total: ${total_usd}")
            return [f"""```
💰 Total Mining Rewards

📈 Current Earnings:
└─ 🪙 LTC:  ${total_usd_LTC:.2f}
└─ 🐕 DOGE: ${total_usd_DOGE:.2f}
═══════════════════
💵 Total: ${total_usd:.2f} USD```"""]
        if lowered in ['day profit', 'profit']:
            json_data = get_data(URL)
            profit = calculate_profitability(json_data, POWER_USAGE, ENERGY_COST_PER_KWH, HOURS_PER_DAY)
            status = "📈 PROFITABLE" if profit > 0 else "📉 NOT PROFITABLE"
            return [f"""```
📊 Daily Mining Analysis

💰 Profit Details:
└─ 💵 Expected: ${profit:.2f} USD
└─ 📊 Status: {status}

⚡ Power Details:
└─ 🔌 Usage: {POWER_USAGE}W
└─ 💸 Cost: ${ENERGY_COST_PER_KWH}/kWh```"""]
        if lowered == 'ltc':
            data = get_data(URL)
            ltc_usd_price = data['market']['ltc_usd']
            return [f"""```
🪙 Litecoin (LTC)
💎 Current Price: ${ltc_usd_price:.2f} USD```"""]
        if lowered == 'doge':
            data = get_data(URL)
            doge_usd_rate = data["market"]["doge_usd"]
            return [f"""```
🐕 Dogecoin (DOGE)
💎 Current Price: ${doge_usd_rate:.4f} USD```"""]
        return ["""```
❌ Unknown command
Type ?help for available commands```"""]
    except Exception as e:
        logger.error(f"Error processing command: {e}", exc_info=True)
        return ["""```
⚠️ Error!
An error occurred while processing your request.
Please try again later.```"""]