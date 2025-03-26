import os
import time
import ccxt
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import schedule
import logging
import requests
from solana.rpc.api import Client
from solders.pubkey import Pubkey
import base58

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crypto_tracker.log'),
        logging.StreamHandler()
    ]
)

# Load environment variables
load_dotenv()

class CryptoAccumulationTracker:
    def __init__(self):
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })
        
        # Initialize Solana client
        self.solana_client = Client("https://api.mainnet-beta.solana.com")
        
        # Load configuration
        self.crypto_pair = os.getenv('CRYPTO_PAIR', 'BTC/USDT')
        self.volume_threshold = float(os.getenv('VOLUME_THRESHOLD', 100000))
        self.accumulation_threshold = float(os.getenv('ACCUMULATION_THRESHOLD', 50))
        
        # Solana token configuration
        self.solana_token_address = "jjwkEZufZa7LKuMb9NMP5QtVKy2E26sVJSM96c1XGFM"
        self.token_pubkey = Pubkey.from_string(self.solana_token_address)
        
        # Initialize data storage
        self.volume_history = []
        self.price_history = []
        self.token_holders = {}
        
    def fetch_solana_token_data(self):
        """Fetch Solana token data including holders and transactions."""
        try:
            # Get token account info
            token_accounts = self.solana_client.get_token_accounts_by_owner(
                self.token_pubkey,
                {"programId": Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")}
            )
            
            # Get recent transactions
            signatures = self.solana_client.get_signatures_for_address(self.token_pubkey)
            
            # Process holder data
            holder_data = {}
            for account in token_accounts.value:
                account_info = self.solana_client.get_account_info(account.pubkey)
                if account_info.value:
                    holder_data[account.pubkey] = {
                        'balance': account_info.value.data.parsed['info']['tokenAmount']['amount'],
                        'decimals': account_info.value.data.parsed['info']['tokenAmount']['decimals']
                    }
            
            # Process transaction data
            recent_transactions = []
            for sig in signatures.value:
                tx = self.solana_client.get_transaction(sig.signature)
                if tx.value:
                    recent_transactions.append({
                        'timestamp': tx.value.block_time,
                        'signature': sig.signature,
                        'amount': tx.value.meta.post_balances[0] - tx.value.meta.pre_balances[0]
                    })
            
            return {
                'holders': holder_data,
                'transactions': recent_transactions,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logging.error(f"Error fetching Solana token data: {str(e)}")
            return None

    def analyze_solana_accumulation(self, token_data):
        """Analyze Solana token accumulation patterns."""
        if not token_data:
            return False, 0

        # Calculate total holder value
        total_holder_value = sum(
            holder['balance'] / (10 ** holder['decimals'])
            for holder in token_data['holders'].values()
        )

        # Calculate recent transaction volume
        recent_transactions = token_data['transactions'][:10]  # Last 10 transactions
        transaction_volume = sum(abs(tx['amount']) for tx in recent_transactions)

        # Compare with previous data
        if hasattr(self, 'previous_holder_value'):
            holder_increase = ((total_holder_value - self.previous_holder_value) / self.previous_holder_value) * 100
        else:
            holder_increase = 0

        self.previous_holder_value = total_holder_value

        # Check for accumulation conditions
        is_accumulating = (
            holder_increase > self.accumulation_threshold and
            transaction_volume > self.volume_threshold
        )

        return is_accumulating, holder_increase

    def fetch_market_data(self):
        """Fetch current market data for the specified pair."""
        try:
            ticker = self.exchange.fetch_ticker(self.crypto_pair)
            return {
                'timestamp': datetime.now(),
                'price': ticker['last'],
                'volume': ticker['quoteVolume'],
                'change_24h': ticker['percentage']
            }
        except Exception as e:
            logging.error(f"Error fetching market data: {str(e)}")
            return None

    def analyze_accumulation(self, current_data):
        """Analyze if there's significant accumulation happening."""
        if not current_data:
            return False, 0

        # Add current data to history
        self.volume_history.append(current_data['volume'])
        self.price_history.append(current_data['price'])

        # Keep only last 24 hours of data
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.volume_history = [v for v in self.volume_history if v > 0]
        self.price_history = [p for p in self.price_history if p > 0]

        if len(self.volume_history) < 2:
            return False, 0

        # Calculate volume increase
        recent_volume = sum(self.volume_history[-6:])  # Last 6 periods
        previous_volume = sum(self.volume_history[-12:-6])  # Previous 6 periods
        
        if previous_volume == 0:
            return False, 0

        volume_increase = ((recent_volume - previous_volume) / previous_volume) * 100
        
        # Check for accumulation conditions
        is_accumulating = (
            volume_increase > self.accumulation_threshold and
            recent_volume > self.volume_threshold
        )

        return is_accumulating, volume_increase

    def send_alert(self, volume_increase, is_solana=False):
        """Send alert when significant accumulation is detected."""
        if os.getenv('ENABLE_ALERTS', 'true').lower() == 'true':
            if is_solana:
                alert_message = (
                    f"Significant accumulation detected for Solana token {self.solana_token_address}!\n"
                    f"Holder value increase: {volume_increase:.2f}%\n"
                    f"Total holder value: {self.previous_holder_value:.2f}"
                )
            else:
                alert_message = (
                    f"Significant accumulation detected for {self.crypto_pair}!\n"
                    f"Volume increase: {volume_increase:.2f}%\n"
                    f"Current price: {self.price_history[-1]:.2f}"
                )
            logging.info(alert_message)
            # Add your preferred alert method here (email, telegram, etc.)

    def run_tracking(self):
        """Main tracking loop."""
        logging.info(f"Starting tracking for {self.crypto_pair} and Solana token {self.solana_token_address}")
        
        while True:
            try:
                # Track regular crypto pair
                current_data = self.fetch_market_data()
                if current_data:
                    is_accumulating, volume_increase = self.analyze_accumulation(current_data)
                    if is_accumulating:
                        self.send_alert(volume_increase)
                    
                    logging.info(
                        f"Status for {self.crypto_pair}: "
                        f"Price: {current_data['price']:.2f}, "
                        f"24h Change: {current_data['change_24h']:.2f}%"
                    )

                # Track Solana token
                token_data = self.fetch_solana_token_data()
                if token_data:
                    is_accumulating, holder_increase = self.analyze_solana_accumulation(token_data)
                    if is_accumulating:
                        self.send_alert(holder_increase, is_solana=True)
                    
                    logging.info(
                        f"Status for Solana token {self.solana_token_address}: "
                        f"Total holder value: {self.previous_holder_value:.2f}, "
                        f"Holder increase: {holder_increase:.2f}%"
                    )
                
                time.sleep(int(os.getenv('TRACKING_INTERVAL', 5)) * 60)  # Convert minutes to seconds
                
            except Exception as e:
                logging.error(f"Error in tracking loop: {str(e)}")
                time.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    tracker = CryptoAccumulationTracker()
    tracker.run_tracking() 