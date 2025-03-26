# Crypto Tracker - Real-time Cryptocurrency Price Monitor

A real-time cryptocurrency price tracking application that displays live prices, market data, and interactive charts for Solana and Bitcoin.

## Features

- Real-time price updates via WebSocket
- Interactive price charts
- 24-hour price changes
- Trading volume statistics
- Market capitalization data
- Mobile-responsive design
- Dark theme UI

## Live Demo

Visit the live demo at: [https://crypto-tracker-xxxx.onrender.com](https://crypto-tracker-xxxx.onrender.com)

## Tech Stack

- Backend: Python/Flask
- Frontend: HTML, CSS, JavaScript
- Real-time Updates: Flask-SocketIO
- Data Source: CoinGecko API
- Deployment: Render.com

## Local Development

1. Clone the repository:
```bash
git clone https://github.com/yourusername/crypto-tracker.git
cd crypto-tracker
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file:
```
SECRET_KEY=your-secret-key
```

5. Run the application:
```bash
python app.py
```

6. Visit http://localhost:5000 in your browser

## Deployment

This project is configured for deployment on Render.com:

1. Fork this repository
2. Create a new Web Service on Render.com
3. Connect your GitHub repository
4. Set the following:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn --worker-class eventlet -w 1 app:app`
   - Environment Variables:
     - `SECRET_KEY`: Your secret key

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- CoinGecko API for providing cryptocurrency data
- Flask and Flask-SocketIO for the backend framework
- Chart.js for the interactive charts 