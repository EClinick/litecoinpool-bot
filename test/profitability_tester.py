import os
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
API_KEY = os.getenv('LITECOINPOOL_API_KEY')
json_api_url = f'https://www.litecoinpool.org/api?api_key={API_KEY}'
POWER_USAGE = int(os.getenv('POWER_USAGE'))
ENERGY_COST_PER_KWH = float(os.getenv('ENERGY_COST_PER_KWH'))
HOURS_PER_DAY = int(os.getenv('HOURS_PER_DAY'))

# Function to fetch the JSON data
def get_json_data(api_url):
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception('Failed to retrieve data')

# Function to calculate the profitability
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
    daily_energy_consumption_kWh = (power_usage * HOURS_PER_DAY) / 1000
    daily_electricity_cost = daily_energy_consumption_kWh * energy_cost_per_kWh
    
    # Calculating profit
    profit = total_expected_earnings - daily_electricity_cost
    
    return profit

# Function to decide whether to stop the miners
def should_stop_mining(profit):
    return profit <= 0

# Main function to orchestrate the logic
def main():
    json_data = get_json_data(json_api_url)
    profit = calculate_profitability(json_data, POWER_USAGE, ENERGY_COST_PER_KWH)
    print(f"Expected daily profit: {profit} USD")
    
    if should_stop_mining(profit):
        print("Mining is not profitable. PLEASE STOP miners.")
        # Add your logic to stop the miners here
    else:
        print("Mining is profitable. Continue mining.")

if __name__ == "__main__":
    main()
