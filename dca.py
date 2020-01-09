from json import dumps
from math import log
from random import randint
from datetime import datetime, timedelta
from collections import namedtuple
from pro_api import ProApi, KeyStore
from martingale import get_orders

# Todo
# 1. Implement exception throws so that so that failures are not fatal

def get_balance(cb, currency):
    j = cb.get_accounts()
    for o in j:
        if o['currency'] == currency: 
            return(float(o['available']))
            
def get_product(cb, product):
    j = cb.get_products()
    rtn = {}
    for o in j:
        if o['id'] == product: 
            for k in ['base_min_size', 'quote_increment', 'base_increment']:
                rtn[k] = float(o[k])
            # brnd = 0 - int(round(log(base_increment)/log(10),0))
            rtn['qrnd'] = 0 - int(round(log(rtn['quote_increment'])/log(10),0))
    Product = namedtuple('Product', list(rtn.keys()))
    return Product(**rtn)

def get_bid(cb, quote_increment, product):
    j = cb.get_book(product = 'BTC-USD')
    bid = float(j['asks'][0][0]) - quote_increment    
    if SANDBOX:
        bid -= float(randint(5, 987) / 100) # debug
    return bid

def place_order(cb, json, boost=False):
    j = cb.add_order(json=json, boost=boost)
    return j

def place_orders(cb, bid, qrnd, balance, min_size):
    orders, prices = get_orders(bid, qrnd, balance, min_size)
    cost = sum([orders[i] * prices[i] for i in range(0, len(orders))])
    rtn = []

    for i in range(0, len(orders)):
        order = get_market_order(orders[i], prices[i])
        j = cb.add_order(json=order, boost=True)
        rtn += [j]

    return rtn
    
def get_market_order(size, price, dust=False):
    if dust:
        ts_now = datetime.now()
        dust = str(ts_now.hour) + ('00' + str(ts_now.minute))[-2:]
        size = size + float(dust) / 100_000_000
    size = "{:.8f}".format(size)
    price = str(round(price, 2))
    order = dict(
        size = size,
        price = price,
        side = 'buy',
        product_id = 'BTC-USD'
    )
    return order

# def chase_book(cb, inc, watch_id):
    # while True:
        # j = cb.get_orders(product = 'BTC-USD')
        # if not j: return
        # s = sorted(j, key=lambda item: item['price'])
        # best = s[-1]
        # if watch_id != best['id']: return
        # bid = get_bid(cb, inc, product = 'BTC-USD')
        # if bid > float(best['price']):
            # order = get_market_order(0.001, bid)
            # j = place_order(cb, order)                
            # cb.cancel_order(watch_id, boost=True)
            # watch_id = j['id']
                
def chase_order(cb, watch_id):
    params = dict(order_id=watch_id)
    while True:
        j = cb.get_fills(product = 'BTC-USD', params = params)
        for f in j:
            if f['order_id'] == watch_id:
                return
                
def fake_taker(cb, inc, size, price):                
    print("Placing fake taker")
    order = get_market_order(size, price + 10, True)
    order = dict(**order, 
                **dict(time_in_force='IOC', post_only=False))
    j = place_order(cb, order)
    id = j['id']
    chase_order(cb, id)
    print("Done")

def get_costbasis(cb, product):
    ts = datetime.fromisoformat(DAY_ZERO)
    j = cb.get_fills(product = product)
    fills = []
    for f in j:
        # '2019-12-22T15:42:39.469Z' => '2019-12-22T15:42:39'
        isot = f['created_at'].split('Z')[0].split('.')[0]
        fts  = datetime.fromisoformat(isot)
        if fts > ts: fills += [f]

    btc = usd = 0
    for f in fills:
        btc += float(f['size'])
        usd += float(f['usd_volume'])
        usd += float(f['fee'])

    return tuple([btc, usd])

def get_avg_dca(cb, btc, usd):
    ts = datetime.now() + timedelta(days=1)
    params = dict(  start = DAY_ZERO       ,
                    end   = ts.isoformat() ,
                    granularity = 86400    )
    # {60, 300, 900, 3600, 21600, 86400}
    # {1m, 5m,  15m, 1h,   6h,    1d}
   
    l = cb.get_candles(product = "BTC-USD", params = params)

    l.reverse()
    daily = btc*99.5/len(l)
    dusd = dbtc = 0
    for i in l:
        utime, low, high, open, close, volume = tuple([float(x) for x in i])
        # print(utime, low, high, open, close, volume)
        dbtc += daily
        dusd += daily * (low + high) / 2

    cb = usd/btc
    dcb = dusd/dbtc
    delta = (dcb - cb)/dcb*100
    return tuple([delta, dcb])
    
MAKE_ORDER = False
# MAKE_ORDER = True

SANDBOX = False
# SANDBOX = True

DAY_ZERO="2019-12-17"
    
def main():    
    if SANDBOX:
        cb = ProApi(KeyStore.Stdin, api_url = 'https://api-public.sandbox.pro.coinbase.com/')
        # browser URL = https://public.sandbox.pro.coinbase.com/trade/BTC-USD
    else:
        # ProApi(KeyStore.Trezor).keystore_encode('test.json') ; exit(2)
        # cb = ProApi(KeyStore.Trezor, 'trezor_ks.json')
        cb = ProApi(KeyStore.Stdin)
    
    prod = get_product(cb, 'BTC-USD')
    bid = get_bid(cb, prod.quote_increment, product = 'BTC-USD')
    balance = get_balance(cb, 'USD')
    buy = max(0.001, round(balance * 0.05 / bid, 4))
    print("Bid:", bid)
    print("Balance:", round(balance, 2))
    print("Buy:", buy)
    
    if MAKE_ORDER:
        fake_taker(cb, prod.quote_increment, buy, bid)
        
    balance = get_balance(cb, 'USD')
    print("Balance:", round(balance, 2))
    j = place_orders(cb, bid, prod.qrnd, balance, prod.base_min_size)
    print(len(j), "Orders placed")
    btc, usd = get_costbasis(cb, 'BTC-USD')
    print("BTC:", round(btc,8), "USD:", round(usd,2))
    print("Cost Basis:", round(usd/btc, 2))
    delta, dcb = get_avg_dca(cb, btc, usd)
    print("DCA Basis:", round(dcb,2))
    print("Delta", round(delta,3), "%")

if __name__ == "__main__":
    main()
