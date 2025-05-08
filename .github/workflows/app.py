import asyncio
import os
from flask import Flask, render_template, request, jsonify
from metaapi_cloud_sdk import MetaApi
import nest_asyncio
from dotenv import load_dotenv
import traceback

# Load environment variables from .env file
load_dotenv()
API_TOKEN = os.getenv('METAAPI_TOKEN')

nest_asyncio.apply()
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/connect', methods=['POST'])
def connect():
    data = request.json
    login = data.get('login')
    password = data.get('password')
    server_name = data.get('server_name')
    if not all([login, password, server_name]):
        return jsonify({"status": "Error", "message": "Missing login, password, or server_name"}), 400
    try:
        asyncio.run(connect_to_account(login, password, server_name))
        return jsonify({"status": "Connected"})
    except Exception as e:
        print("Exception occurred:", e)
        traceback.print_exc()  # Prints the full stack trace
        return jsonify({"status": "Error", "message": str(e)}), 500

@app.route('/trade', methods=['POST'])
def trade():
    data = request.json
    login = data.get('login')
    password = data.get('password')
    server_name = data.get('server_name')
    symbol = data.get('symbol')
    lot_size = data.get('lot_size')
    num_trades = data.get('num_trades')
    auto_trade = data.get('auto_trade')
    trading_logic = data.get('trading_logic', 'crossover')
    if not all([login, password, server_name, symbol, lot_size, num_trades]):
        return jsonify({"status": "Error", "message": "Missing required trade parameters"}), 400
    try:
        asyncio.run(execute_trade(login, password, server_name, symbol, lot_size, num_trades, auto_trade, trading_logic))
        return jsonify({"status": "Trade Successful"})
    except Exception as e:
        print("Exception occurred:", e)
        traceback.print_exc()  # Prints the full stack trace
        return jsonify({"status": "Error", "message": str(e)}), 500

async def connect_to_account(login, password, server_name):
    api = MetaApi(API_TOKEN)
    accounts = await api.metatrader_account_api.get_accounts_with_infinite_scroll_pagination()
    account = next((item for item in accounts if item.login == login and item.type.startswith('cloud')), None)
    if not account:
        try:
            print(f"Creating account with login={login}, server={server_name}")
            account = await api.metatrader_account_api.create_account({
                'name': 'Test account',
                'type': 'cloud',
                'login': login,
                'password': password,
                'server': server_name,
                'platform': 'mt5',
                'application': 'MetaApi',
                'magic': 1000,
            })
        except Exception as e:
            print(f"Failed to create account: {e}")
            if hasattr(e, 'details'):
                print(f"Details: {e.details}")
            raise
    await account.deploy()
    while True:
        state = account.state
        connection_status = account.connection_status
        if state == 'DEPLOYED' and connection_status == 'CONNECTED':
            break
        await asyncio.sleep(5)
    print('Account connected')

async def execute_trade(login, password, server_name, symbol, lot_size, num_trades, auto_trade, trading_logic):
    api = MetaApi(API_TOKEN)
    accounts = await api.metatrader_account_api.get_accounts_with_infinite_scroll_pagination()
    account = next((item for item in accounts if item.login == login and item.type.startswith('cloud')), None)
    if not account:
        raise Exception("Account not found. Please connect first.")
    await account.deploy()
    connection = account.get_rpc_connection()
    await connection.connect()

    moving_average = None
    for _ in range(int(num_trades)):
        price_data = await connection.get_symbol_price(symbol)
        price = price_data['bid']

        if moving_average is None:
            moving_average = price
        moving_average = (moving_average + price) / 2

        if price > moving_average:
            order = await connection.create_market_buy_order(symbol, float(lot_size))
        else:
            order = await connection.create_market_sell_order(symbol, float(lot_size))

        print(f'Trade successful: {order}')
        await asyncio.sleep(1)

if __name__ == "__main__":
    app.run(debug=True, port=5000)