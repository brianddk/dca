# TODO
# 1. Add a CB (non-pro) api
# 2. Add ability to get all deposit times from CB
# 3. Add ability to get all BAT, BCH, XTZ, OXT from Pro
# 4. Make a comparison that would assume buy BTC on arrival of all of the above
# 5. Full balance as a function of USD
# 6. Compare the two

from fileinput import input
from base64 import b64encode, b64decode
from requests import get, post, delete
from time import time, perf_counter, sleep
from hashlib import sha256
from hmac import new as new_hmac
from json import dump, dumps, load
from requests.auth import AuthBase
from sys import argv, exit
from enum import Enum

trezor_encrypt = trezor_decrypt = pad_size = False
def imp_Trezor():
    from trezor_ks import trezor_encrypt as imp_trezor_encrypt
    from trezor_ks import trezor_decrypt as imp_trezor_decrypt
    from trezor_ks import pad_size as imp_pad_size
    
    global trezor_encrypt, trezor_decrypt, pad_size
    trezor_encrypt, trezor_decrypt, pad_size = (
                imp_trezor_encrypt, imp_trezor_decrypt, imp_pad_size)

RATE_PER_SEC = 5                
class KeyStore(Enum):
    Stdin  = 1
    Trezor = 2
    GPG    = 3
    
class Method(Enum):
    Get    = 1
    Post   = 2
    Delete = 3

class ProApi():
    class _keystore():
        def __init__(self, keystore, fd = '-'):            
            s = self
            s.keystore = keystore
            s.fd = fd            
            if keystore == KeyStore.Stdin:
                decoder = s._stdin
            if keystore == KeyStore.Trezor:
                decoder = s._trezor
            if keystore == KeyStore.GPG:
                decoder = s._gpg
            s.decoder = decoder
            s.api_key = s.secret_key = s.passphrase = s.decoded = False
        
        def decode(self):
            s = self
            s.api_key, s.secret_key, s.passphrase = s.decoder(s.fd)
            s.decoded = True

        def _stdin(self, fd = '-'):
            keys = []
            for line in input('-'):
                keys += [line.strip()]
            return tuple(keys)

        def _trezor(self, fd):
            imp_Trezor()
            clear = {}
            with open(fd, 'r') as file:
                cipher = load(file)
            label  = ['api_key', 'secret_key', 'passphrase']
            for k in label:
                clear[k] = trezor_decrypt(k, cipher[k])
            keys = []
            for i in label:
                keys += [clear[i]]
            return tuple(keys)            

        def _gpg(self, fd):
            print("Not yet!")
            exit(2)
                        
        def trezor_encode(self, fd):
            imp_Trezor()
            label  = ['api_key', 'secret_key', 'passphrase']
            print("Input", tuple(label), "one per line, then ^Z")
            clear  = list(self._stdin())
            cipher = { 'pad_size': pad_size }
            for i in range(0, len(label)):
                cipher[label[i]] = trezor_encrypt(label[i], clear[i])
            with open(fd, 'w') as file:
                dump(cipher, file, indent=4)
            
    class _no_auth(AuthBase):
        def __call__(self, request):
            request.headers.update({
                'Content-Type': 'application/json'
            })
            return request

    class _auth(AuthBase):
        def __init__(self, keystore):
            self.keystore = keystore
        
        def decode(self):
            self.keystore.decode()
            self.api_key = self.keystore.api_key
            self.secret_key = self.keystore.secret_key
            self.passphrase = self.keystore.passphrase

        def __call__(self, request):
            if not self.keystore.decoded:
                self.decode()
            timestamp = str(time())
            message = (timestamp + request.method + 
                        request.path_url).encode() + (request.body or b'')
            hmac_key = b64decode(self.secret_key)
            signature = new_hmac(hmac_key, message, sha256)
            signature_b64 = b64encode(signature.digest())

            request.headers.update({
                'CB-ACCESS-SIGN': signature_b64,
                'CB-ACCESS-TIMESTAMP': timestamp,
                'CB-ACCESS-KEY': self.api_key,
                'CB-ACCESS-PASSPHRASE': self.passphrase,
                'Content-Type': 'application/json'
            })
            return request

    def __init__(self, keystore, 
                 fd = '-', 
                 api_url = 'https://api.pro.coinbase.com/'):
        self.keystore = ProApi._keystore(keystore, fd)
        self.auth = ProApi._auth(self.keystore)
        self.no_auth = ProApi._no_auth()
        self.t0 = False
        self.count = 0
        self.api_url = api_url

    def _wait(self, boost):
        wt = 0
        if self.count < 2:
            boost = True
        if boost: return
        if not self.t0: self.t0 = perf_counter()
        now = perf_counter()
        wt = self.count / 5 - now + self.t0
        if wt > 0: sleep(wt)

    def _method(self, method, frag, 
            boost = False, params = None, auth = False, json = None):
        if method == Method.Get:
            cmd = get
        if method == Method.Post:
            cmd = post
        if method == Method.Delete:
            cmd = delete
        if not auth: auth = self.auth
        url = self.api_url + frag
        self.count += 1
        self._wait(boost)
        r = cmd(url, auth=auth, params=params, json=json)
        if not r.ok: 
            self.count -= 1
            print(dumps(r.json(), indent = 4))
            print(r.status_code)
            print(url)
            exit(5)
        return r
        
    def _get(self, frag, 
            boost = False, params = None, auth = False):
        r = self._method(Method.Get, frag, boost, params, auth)
        return r
    
    def _post(self, frag, 
            boost = False, params = None, auth = False, json = None):
        r = self._method(Method.Post, frag, boost, params, auth, json)
        return r
    
    def _delete(self, frag, 
            boost = False, params = None, auth = False):
        r = self._method(Method.Delete, frag, boost, params, auth)
        return r
    
    def get_products(self, boost = False):
        r = self._get('products', boost, auth=self.no_auth)
        return r.json()
        
    def get_accounts(self, boost = False):
        r = self._get('accounts', boost)
        return r.json()
    
    def get_orders(self, product = "BTC-USD", boost = False):
        params = dict(product_id = product)
        r = self._get('orders', boost)
        return r.json()
    
    def get_fills(self, product = "BTC-USD", boost = False, params = None):
        params = params if params else {}
        params = dict(**params, **dict(product_id = product))
        r = self._get('fills', boost, params)
        return r.json()
        
    def get_candles(self, product = "BTC-USD", boost = False, params = None):
        frag = 'products/' +product+ '/candles'
        r = self._get(frag, boost, params=params, auth=self.no_auth)
        return r.json()
    
    def get_book(self, product = "BTC-USD", boost = False):
        frag = 'products/' +product+ '/book'
        r = self._get(frag, boost, auth=self.no_auth)
        return r.json()
    
    def cancel_order(self, id, boost = False):
        frag = 'orders/' + id
        r = self._delete(frag, boost)
        return r.json()
    
    def add_order(self, json, boost = False):
        frag = 'orders'
        r = self._post(frag, boost, params=None, auth=False, json=json)
        return r.json()

    def keystore_encode(self, fd):
        if self.keystore.keystore == KeyStore.Trezor:
            self.keystore.trezor_encode(fd)
        else:
            print("Not yet!")
            exit(2)
