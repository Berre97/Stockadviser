import os
import json
import random
import pandas as pd
import numpy as np
import time
import ta
from telegram import Bot
import asyncio
from datetime import datetime
import os
import yfinance as yf
import requests
from bs4 import BeautifulSoup


token = Bot(token='7277331559:AAGtyCZcKJ2UI80U6sqJo5jcjQrHD2BXlB8')
chat_id = -1002203456191

class apibot():
    def __init__(self, file_path_assets, file_path_data, markets):
        self._file_path_assets = file_path_assets
        self._file_path_data = file_path_data
        self._markets = markets
        self._list = []


    async def send_telegram_message(self, message):
      try:
          await token.send_message(chat_id=chat_id, text=message, read_timeout=20)
      except TimeoutError:
        print("Failed to send message due to timeout.")


    def load_assets(self, file_path):
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                return data
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print('Error loading json data: {e}')
                return {}


    def update_assets(self, file_path, order):

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)

            except json.JSONDecodeError:
                # Als er een decodeerfout is, initialiseert een lege dictionary
                data = []
        else:
            data = []

        if order['type'] == "Sold":
            for i in data:
                if i['order'] == order['order']:
                    i.update(order)

        elif order['type'] == 'Stoploss':
            for i in data:
                if i['order'] == order['order']:
                    i.update(order)

        elif order['type'] == 'Bought':
            if 'last_update' in order.keys():
                for i in data:
                    if order['order'] == i['order']:
                        i.update(order)
            else:
                data.append(order)

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)


    def load_data(self, file_path):
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                return data
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print('Error loading json data: {e}')
                return {}

    def update_data(self, file_path, order):

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = []

            except json.JSONDecodeError:
                # Als er een decodeerfout is, initialiseert een lege dictionary
                data = []
        else:
            data = []

        data.append(order)

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)

    
    async def get_data(self, market):

        url = f'https://finance.yahoo.com/quote/{market}/'
        page = requests.get(url)
        soup = BeautifulSoup(page.text, 'html.parser')
        response = yf.download(market, period='1y')

        df = response.sort_index()
        df['SMA_50'] = ta.trend.sma_indicator(df['Close'], window=50)
        df['SMA_20'] = ta.trend.sma_indicator(df['Close'], window=20)
        df['SMA_200'] = ta.trend.sma_indicator(df['Close'], window=200)

        # Relatieve sterkte-index (RSI)
        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)

        # Moving Average Convergence Divergence (MACD)
        df['MACD'] = ta.trend.macd(df['Close'])
        df['MACD_signal'] = ta.trend.macd_signal(df['Close'])

        # Bollinger Bands
        bollinger = ta.volatility.BollingerBands(df['Close'], window=20, window_dev=2)
        df['Bollinger_High'] = bollinger.bollinger_hband()
        df['Bollinger_Low'] = bollinger.bollinger_lband()

        df['EMA_8'] = ta.trend.ema_indicator(df['Close'], window=8)
        df['EMA_13'] = ta.trend.ema_indicator(df['Close'], window=13)
        df['EMA_21'] = ta.trend.ema_indicator(df['Close'], window=21)
        df['EMA_55'] = ta.trend.ema_indicator(df['Close'], window=55)

        df['EMA_8_above_EMA_13'] = df['EMA_8'] > df['EMA_13']
        df['EMA_13_above_EMA_21'] = df['EMA_13'] > df['EMA_21']
        df['EMA_21_above_EMA_55'] = df['EMA_21'] > df['EMA_55']

        df['EMA_above'] = (df['EMA_8_above_EMA_13'] &
                           df['EMA_13_above_EMA_21'] &
                           df['EMA_21_above_EMA_55']).rolling(window=20).sum() == 20

        df['EMA_below'] = (~df['EMA_8_above_EMA_13'] &
                           ~df['EMA_13_above_EMA_21'] &
                           ~df['EMA_21_above_EMA_55']).rolling(window=20).sum() == 20

        df['volume_MA'] = df['Volume'].rolling(window=20).mean()
        df['Buy Signal Long'] = df['EMA_above']
        df['Buy Signal Short'] = df['EMA_below']

        last_index = df.index[-1]
        last_row = df.iloc[-1]

        # Going long
        indicators_buy_long = df.loc[last_index, ['Buy Signal Long']]

        for col in df.columns:
            if df[col].isnull().any():
                pass

            else:
                # Golden Cross / Death Cross

                # RSI Overbought / Oversold
                df['RSI_Overbought'] = np.where(df['RSI'] >= 40, True, False)
                df['RSI_Oversold'] = np.where(df['RSI'] <= 35, True, False)
                df['Bollinger_Breakout_High'] = np.where((df['Close'] > df['Bollinger_High']), True, False)
                df['Bollinger_Breakout_Low'] = np.where((df['Close'] < df['Bollinger_Low']), True, False)
                df['Market'] = market

                short_ema = df['Close'].ewm(span=12, adjust=False).mean()
                long_ema = df['Close'].ewm(span=26, adjust=False).mean()
                df['MACD'] = short_ema - long_ema
                df['Signal Line'] = df['MACD'].ewm(span=9, adjust=False).mean()

                # MACD Crossovers
                df['MACD_Bullish'] = np.where(
                    (df['MACD'] > df['Signal Line']) & (df['MACD'].shift(1) <= df['Signal Line'].shift(1)), True,
                    False)
                df['MACD_Bearish'] = np.where(
                    (df['MACD'] < df['Signal Line']) & (df['MACD'].shift(1) >= df['Signal Line'].shift(1)), True,
                    False)

        if page.status_code == 200:

            values = soup.find_all('span', class_='value yf-tx3nkj')
            values2 = soup.find_all('span', class_= 'value yf-mrt107')
            valuation_measures = soup.find_all('p', class_="value yf-1n4vnw8")
            fin_highlights = soup.find_all('p', class_="value yf-lc8fp0")
            current_price = soup.find('span', class_="price yf-15b2o7n")

            current_price = current_price.text.strip()


            metric_values = {"prev close": None, "open": None, "bid": None, "ask": None,
                             "day's range": None, "year's range": None, "volume": None, "avg volume": None,
                             "market cap": None, "beta 5y": None, "pe ratio ttm": None, 'eps ttm': None,
                             "earnings date": None, "forward div yield": None, "ex div date": None, "1y target est": None,
                             "market cap dup": None,"enterprise value": None, "trailing pe": None, "forward pe": None,
                             "peg ratio 5yr": None, "price_to_sales ttm": None, "price_to_book mrq": None,
                             "enterp value_to_revenue": None, "enterp value_to_ebitda": None,"profit margin": None, "roa ttm": None, "roe ttm": None}

            list_values = []

            if values:
                for value in values:
                    value = value.text.strip()
                    if value != "--":
                        list_values.append(value)
                    else:
                        list_values.append(None)


            elif values2:
                for value in values2:
                    value = value.text.strip()
                    if value != "--":
                        list_values.append(value)
                    else:
                        list_values.append(None)

            
            for i in fin_highlights:
                i = i.text.strip()
                if i != "--":
                    list_values.append(i)
                else:
                    list_values.append(None)


            for metric, value in zip(metric_values, list_values):
                metric_values[metric] = value
                

            print(list_values)
            eps_ttm = metric_values['eps ttm']
            trailing_pe = metric_values['trailing pe']
            forward_pe = metric_values['forward pe']
            peg_ratio_5yr = metric_values['peg ratio 5yr']
            roe_ttm = metric_values['roe ttm']
            roa_ttm = metric_values['roa ttm']
            pe_ratio_ttm = metric_values['pe ratio ttm']
            price_to_book_mrq = metric_values['price_to_book mrq']
            years_range = metric_values["year's range"]
            profit_margin = metric_values['profit margin']
            enterprice_value_ebitda = metric_values["enterp value_to_ebitda"]

            eps_ttm = float(eps_ttm.replace(",", "")) if eps_ttm is not None else None
            trailing_pe = float(trailing_pe.replace(",", "")) if trailing_pe is not None else None
            forward_pe = float(forward_pe.replace(",", "")) if forward_pe is not None else None
            pe_ratio_ttm = float(pe_ratio_ttm.replace(",", "")) if pe_ratio_ttm is not None else None
            peg_ratio_5yr = float(peg_ratio_5yr.replace(",", "")) if peg_ratio_5yr is not None else None
            roe_ttm = float(roe_ttm.replace('%', "")) if roe_ttm is not None else None
            roa_ttm = float(roa_ttm.replace('%', "")) if roa_ttm is not None else None
            current_price = float(current_price.replace(",", "")) if current_price is not None else None

            price_to_book_mrq = float(price_to_book_mrq) if price_to_book_mrq is not None else None
            years_range = years_range.split("-") if years_range is not None else None
            years_range_min = float(min(years_range).replace(',', "")) if years_range is not None else None
            years_range_max = float(max(years_range).replace(',', "")) if years_range is not None else None
            profit_margin = float(profit_margin.replace("%", "")) if profit_margin is not None else None
            enterprice_value_ebitda = float(enterprice_value_ebitda) if enterprice_value_ebitda is not None else None

            print("Laatste data:")
            print(last_row, last_index)
            print(f"PE ratio ttm: {pe_ratio_ttm}\nROE ttm: {roe_ttm}\nROA ttm: {roa_ttm}\nEPS ttm: {eps_ttm}\nPEG_ratio 5y: {peg_ratio_5yr}")
            print('--------------------------------------------------------')


            if self.load_data(self._file_path_assets) is not None:
                for order in self.load_data(self._file_path_assets):
                    for i in self.load_data(self._file_path_data)[-len(self._markets):]:
                        prev_roe_ttm = i['roe ttm']
                        prev_roa_ttm = i['roa ttm']

                    if roa_ttm and roe_ttm:
                        if order['type'] == 'Bought' and order['symbol'] == market and \
                             roa_ttm < 8 or roe_ttm < 10 and last_row['Buy Signal Long'] is False:

                                percentage = (float(current_price) - float(order['price_bought'])) / float(
                                    order['price_bought']) * 100
                                percentage = round(percentage, 2)
                                sell_order = {'type': 'Sold', 'symbol': market,
                                              'order': order['order'],
                                              'date_sold': str(datetime.now()),
                                              'closing_price': current_price,
                                              'price_bought': order['price_bought'],
                                              'date_bought': str(order['date_bought']),
                                              'percentage_gained': percentage}

                                sell_message = f"Verkoop:\n {market} prijs: {current_price} " \
                                               f"aankoopkoers: {float(order['price_bought'])}\n " \
                                               f"percentage gained: {percentage}"

                                print(sell_order)
                                await self.send_telegram_message(sell_message)
                                self.update_assets(self._file_path_assets, sell_order)

                        elif order['symbol'] == market and order['type'] == 'Bought':
                            percentage = (float(current_price) - float(order['price_bought'])) / float(
                                order['price_bought']) * 100
                            percentage = round(percentage, 2)
                            update_order = {'type': 'Bought', 'symbol': market,
                                            'order': order['order'],
                                            'last_update': str(datetime.now()),
                                            'closing_price': current_price,
                                            'price_bought': float(order['price_bought']),
                                            'date_bought': str(order['date_bought']),
                                            'percentage_gained': percentage}

                            update_message = f"Update:\n {market} prijs: {current_price} " \
                                             f"aankoopkoers: {float(order['price_bought'])}\n " \
                                             f"percentage gained: {percentage}"

                            self.update_assets(self._file_path_assets, update_order)

            days = 5 #100
            dict = {'p/e ratio ttm': []}
            if self.load_data(self._file_path_data) is not None:
                if roa_ttm and roa_ttm and pe_ratio_ttm:
                    if len(self.load_data(self._file_path_data)) >= days * len(self._markets):
                        for i in self.load_data(self._file_path_data)[-len(self._markets) * days:]:
                            if i['stock'] == market and i['roe ttm'] and i['roa ttm']:
                                dict['p/e ratio ttm'].append(i['p/e ratio ttm'])

            
            if dict['p/e ratio ttm']:
                max_pe_ratio = max(dict['p/e ratio ttm'])
                pe_ratio_drop = max_pe_ratio * 0.1 #0.2
                if pe_ratio_ttm < 50 and pe_ratio_ttm <= pe_ratio_drop and \
                        roe_ttm >= 10 and roa_ttm >= 8 and last_row['Buy Signal Long']:

                    buy_message = f"Koop:\n Stock: {market} Prijs: {current_price}"
                    order_number = random.randint(100, 999)
                    buy_order = {'type': 'Bought', 'symbol': market,
                                 'date_bought': str(datetime.now()),
                                 'price_bought': current_price,
                                 'order': order_number}

                    print(buy_order)
                    await self.send_telegram_message(buy_message)
                    self.update_assets(self._file_path_assets, buy_order)

            data = {'stock': market, 'date': str(datetime.now()), 'current price': current_price, "eps ttm": eps_ttm,
                    'trailing pe': trailing_pe, "forward pe": forward_pe,
                    "p/e ratio ttm": pe_ratio_ttm, "peg ratio 5y": peg_ratio_5yr,
                    "roe ttm": roe_ttm, "roa ttm": roa_ttm, "price to book ratio mrq": price_to_book_mrq,
                    "profit margin": profit_margin, "years range min": years_range_min,
                    "years range max": years_range_max, "enterprise value/ebitda": enterprice_value_ebitda

                    }

            self.update_data(self._file_path_data, data)
            
        return df

    async def main(self, bot):
            for i in self._markets:
                await bot.get_data(market=i)

if __name__ == '__main__':
    file_path_assets = os.getenv('FILE_PATH_ASSETS')
    file_path_data = os.getenv('FILE_PATH_DATA')
    bot = apibot(file_path_assets=file_path_assets, file_path_data=file_path_data, markets=['META', 'ADYEN.AS', 'CRWD', 'TTD'])

    asyncio.run(bot.main(bot))
