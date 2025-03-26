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
from pycoingecko import CoinGeckoAPI
import ccxt
import eventlet
eventlet.monkey_patch()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')

# Configure SocketIO with production settings
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    ping_timeout=30,
    ping_interval=15,
    reconnection=True,
    reconnection_attempts=3,
    reconnection_delay=500,
    reconnection_delay_max=2000,
    logger=True,
    engineio_logger=True,
    max_http_buffer_size=1e8
)

# Initialize API clients with rate limiting
cg = CoinGeckoAPI()
binance = ccxt.binance({
    'enableRateLimit': True,
    'options': {
        'defaultType': 'spot'
    }
})

# Solana API endpoints
SOLANA_APIS = {
    'solanafn': "https://api.solanafn.com/v1",
    'solscan': "https://public-api.solscan.io",
    'solana': "https://api.mainnet-beta.solana.com",
    'coingecko': "https://api.coingecko.com/api/v3"
}

# Global data storage with default values
crypto_data = {
    'solana_token': {
        'price': 0,
        'volume_24h': 0,
        'market_cap': 0,
        'last_update': None,
        'name': 'Solana',
        'symbol': 'SOL',
        'change_24h': 0,
        'network_stats': {
            'active_validators': 0,
            'total_supply': 0,
            'circulating_supply': 0,
            'block_time': 0,
            'tps': 0
        }
    },
    'btc': {
        'price': 0,
        'volume_24h': 0,
        'market_cap': 0,
        'change_24h': 0,
        'last_update': None
    },
    'top_100': []
}

def fetch_from_solanafn():
    """Fetch Solana data from SolanaFN API"""
    try:
        logging.info("Attempting to fetch Solana data from SolanaFN API...")
        response = requests.get(f"{SOLANA_APIS['solanafn']}/price")
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Successfully fetched Solana data from SolanaFN: {data}")
            return {
                'price': data.get('price', 0),
                'volume_24h': data.get('volume24h', 0),
                'market_cap': data.get('marketCap', 0),
                'change_24h': data.get('priceChange24h', 0)
            }
        return None
    except Exception as e:
        logging.error(f"Error fetching from SolanaFN API: {str(e)}")
        return None

def fetch_from_solscan():
    """Fetch Solana network stats from Solscan API"""
    try:
        logging.info("Attempting to fetch Solana network stats from Solscan...")
        response = requests.get(f"{SOLANA_APIS['solscan']}/chain/stat")
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Successfully fetched Solana network stats from Solscan: {data}")
            return {
                'active_validators': data.get('activeValidators', 0),
                'total_supply': data.get('totalSupply', 0),
                'circulating_supply': data.get('circulatingSupply', 0),
                'block_time': data.get('blockTime', 0),
                'tps': data.get('tps', 0)
            }
        return None
    except Exception as e:
        logging.error(f"Error fetching from Solscan API: {str(e)}")
        return None

def fetch_from_binance(symbol):
    try:
        logging.info(f"Attempting to fetch {symbol} from Binance...")
        ticker = binance.fetch_ticker(f"{symbol}/USDT")
        logging.info(f"Successfully fetched {symbol} data from Binance")
        return {
            'price': ticker['last'],
            'volume_24h': ticker['quoteVolume'],
            'change_24h': ticker['percentage']
        }
    except Exception as e:
        logging.error(f"Error fetching {symbol} from Binance: {str(e)}")
        return None

def fetch_from_coingecko(symbol):
    try:
        logging.info(f"Attempting to fetch {symbol} from CoinGecko...")
        if symbol.lower() == 'btc':
            symbol = 'bitcoin'
        data = cg.get_price(ids=[symbol.lower()], vs_currencies='usd', include_24hr_change=True, include_24hr_vol=True, include_market_cap=True)
        logging.info(f"Successfully fetched {symbol} data from CoinGecko")
        if symbol.lower() in data:
            return data[symbol.lower()]
        return None
    except Exception as e:
        logging.error(f"Error fetching {symbol} from CoinGecko: {str(e)}")
        return None

def fetch_top_100_coins():
    try:
        # Try CoinGecko first
        coins = cg.get_coins_markets(vs_currency='usd', order='market_cap_desc', per_page=100, sparkline=False)
        
        # Format the data
        formatted_coins = []
        for coin in coins:
            formatted_coins.append({
                'id': coin['id'],
                'symbol': coin['symbol'].upper(),
                'name': coin['name'],
                'image': coin['image'],
                'current_price': coin['current_price'],
                'market_cap': coin['market_cap'],
                'market_cap_rank': coin['market_cap_rank'],
                'price_change_percentage_24h': coin['price_change_percentage_24h'],
                'total_volume': coin['total_volume']
            })
        
        crypto_data['top_100'] = formatted_coins
        logging.info("Updated top 100 coins data")
    except Exception as e:
        logging.error(f"Error fetching top 100 coins: {str(e)}")
        # Keep existing data if there's an error

def fetch_solana_token_data():
    """Fetch token data from multiple sources"""
    try:
        logging.info("Starting Solana data fetch...")
        
        # Try SolanaFN API first
        solanafn_data = fetch_from_solanafn()
        if solanafn_data:
            crypto_data['solana_token'].update({
                'price': solanafn_data['price'],
                'volume_24h': solanafn_data['volume_24h'],
                'market_cap': solanafn_data['market_cap'],
                'change_24h': solanafn_data['change_24h'],
                'last_update': datetime.now().isoformat()
            })
            logging.info(f"Updated Solana data from SolanaFN: {solanafn_data}")

        # Fetch network stats from Solscan
        solscan_data = fetch_from_solscan()
        if solscan_data:
            crypto_data['solana_token']['network_stats'].update(solscan_data)
            logging.info(f"Updated Solana network stats from Solscan: {solscan_data}")

        # Try Binance as backup for price data
        binance_data = fetch_from_binance('SOL')
        if binance_data and not solanafn_data:
            crypto_data['solana_token'].update({
                'price': binance_data['price'],
                'volume_24h': binance_data['volume_24h'],
                'change_24h': binance_data['change_24h'],
                'last_update': datetime.now().isoformat()
            })
            logging.info(f"Updated Solana data from Binance: {binance_data}")

        # Fallback to CoinGecko if needed
        if not solanafn_data and not binance_data:
            cg_data = fetch_from_coingecko('solana')
            if cg_data:
                crypto_data['solana_token'].update({
                    'price': cg_data['usd'],
                    'volume_24h': cg_data['usd_24h_vol'],
                    'market_cap': cg_data['usd_market_cap'],
                    'change_24h': cg_data['usd_24h_change'],
                    'last_update': datetime.now().isoformat()
                })
                logging.info(f"Updated Solana data from CoinGecko: {cg_data}")
            
        return crypto_data['solana_token']
                    
    except Exception as e:
        logging.error(f"Error fetching Solana data: {str(e)}")
        return crypto_data['solana_token']

def fetch_btc_data():
    """Fetch BTC data from multiple sources"""
    try:
        logging.info("Starting BTC data fetch...")
        # Try Binance first
        binance_data = fetch_from_binance('BTC')
        if binance_data:
            crypto_data['btc'].update({
                'price': binance_data['price'],
                'volume_24h': binance_data['volume_24h'],
                'change_24h': binance_data['change_24h'],
                'last_update': datetime.now().isoformat()
            })
            logging.info(f"Updated BTC data from Binance: {binance_data}")
            return crypto_data['btc']

        # Fallback to CoinGecko
        cg_data = fetch_from_coingecko('btc')
        if cg_data:
            crypto_data['btc'].update({
                'price': cg_data['usd'],
                'volume_24h': cg_data['usd_24h_vol'],
                'market_cap': cg_data['usd_market_cap'],
                'change_24h': cg_data['usd_24h_change'],
                'last_update': datetime.now().isoformat()
            })
            logging.info(f"Updated BTC data from CoinGecko: {cg_data}")
            
        return crypto_data['btc']
                    
    except Exception as e:
        logging.error(f"Error fetching BTC data: {str(e)}")
        return crypto_data['btc']

def update_data():
    """Update data function"""
    logging.info("Starting data update thread...")
    while True:
        try:
            with app.app_context():
                logging.info("Fetching new data...")
                fetch_solana_token_data()
                fetch_btc_data()
                fetch_top_100_coins()
                logging.info(f"Current crypto data: {crypto_data}")
                socketio.emit('data_update', crypto_data, namespace='/')
                logging.info("Emitted data update")
        except Exception as e:
            logging.error(f"Error in update_data: {str(e)}")
        time.sleep(30)  # Update every 30 seconds

@app.route('/')
def index():
    logging.info("Rendering index page")
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    logging.info("API data request received")
    return jsonify(crypto_data)

@socketio.on('connect', namespace='/')
def handle_connect():
    logging.info('Client connected')
    socketio.emit('data_update', crypto_data, namespace='/')
    logging.info('Sent initial data to client')

@socketio.on('disconnect', namespace='/')
def handle_disconnect():
    logging.info('Client disconnected')

@socketio.on_error(namespace='/')
def error_handler(e):
    logging.error(f'SocketIO error: {str(e)}')

if __name__ == '__main__':
    # Start the data update loop in a separate thread
    update_thread = threading.Thread(target=update_data, daemon=True)
    update_thread.start()
    
    # Get port from environment variable or use 5000
    port = int(os.getenv('PORT', 5000))
    
    # Run the Flask app with eventlet
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,
        use_reloader=False,
        log_output=True,
        allow_unsafe_werkzeug=False
    ) 