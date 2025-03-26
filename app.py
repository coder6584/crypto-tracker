from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
import requests
import json
from datetime import datetime
import os
from dotenv import load_dotenv
import threading
import time
import logging
import aiohttp
import asyncio
from pycoingecko import CoinGeckoAPI
import ssl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize API clients
cg = CoinGeckoAPI()

# Global data storage
crypto_data = {
    'solana_token': {
        'price': 0,
        'volume_24h': 0,
        'market_cap': 0,
        'last_update': None,
        'name': 'Loading...',
        'symbol': 'Loading...',
        'change_24h': 0
    },
    'btc': {
        'price': 0,
        'volume_24h': 0,
        'market_cap': 0,
        'change_24h': 0,
        'last_update': None
    }
}

async def fetch_solana_token_data():
    """Fetch token data from CoinGecko"""
    try:
        # Get Solana data from CoinGecko
        cg_data = cg.get_coins_markets(
            vs_currency='usd',
            ids=['solana'],
            order='market_cap_desc',
            per_page=1,
            page=1,
            sparkline=False,
            price_change_percentage='24h'
        )
        
        if cg_data and len(cg_data) > 0:
            sol_data = cg_data[0]
            return {
                'price': sol_data['current_price'],
                'volume_24h': sol_data['total_volume'],
                'market_cap': sol_data['market_cap'],
                'name': sol_data['name'],
                'symbol': sol_data['symbol'].upper(),
                'change_24h': sol_data['price_change_percentage_24h'],
                'last_update': datetime.now().isoformat()
            }
        
        return None
                    
    except Exception as e:
        logging.error(f"Error fetching Solana data: {str(e)}")
        return None

async def fetch_btc_data():
    """Fetch BTC data from CoinGecko"""
    try:
        # Get Bitcoin data from CoinGecko
        cg_data = cg.get_coins_markets(
            vs_currency='usd',
            ids=['bitcoin'],
            order='market_cap_desc',
            per_page=1,
            page=1,
            sparkline=False,
            price_change_percentage='24h'
        )
        
        if cg_data and len(cg_data) > 0:
            btc_data = cg_data[0]
            return {
                'price': btc_data['current_price'],
                'volume_24h': btc_data['total_volume'],
                'market_cap': btc_data['market_cap'],
                'change_24h': btc_data['price_change_percentage_24h'],
                'last_update': datetime.now().isoformat()
            }
        
        return None
                    
    except Exception as e:
        logging.error(f"Error fetching BTC data: {str(e)}")
        return None

async def update_data_async():
    """Asynchronous data update function"""
    while True:
        try:
            # Update Solana token data
            solana_data = await fetch_solana_token_data()
            if solana_data:
                crypto_data['solana_token'].update(solana_data)
                logging.info(f"Updated Solana data: {json.dumps(solana_data, indent=2)}")
            
            # Update BTC data
            btc_data = await fetch_btc_data()
            if btc_data:
                crypto_data['btc'].update(btc_data)
                logging.info(f"Updated BTC data: {json.dumps(btc_data, indent=2)}")
            
            # Emit updated data to all connected clients
            socketio.emit('data_update', crypto_data)
            
        except Exception as e:
            logging.error(f"Error in update loop: {str(e)}")
        
        await asyncio.sleep(30)  # Update every 30 seconds

def run_async_loop():
    """Run the async event loop in a separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(update_data_async())

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    return jsonify(crypto_data)

if __name__ == '__main__':
    # Start the background update thread with async support
    update_thread = threading.Thread(target=run_async_loop, daemon=True)
    update_thread.start()
    
    # Get port from environment variable or use 5000
    port = int(os.getenv('PORT', 5000))
    
    # Run the Flask app
    socketio.run(app, host='0.0.0.0', port=port) 