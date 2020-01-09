from sys import exit

def mth_rnd(n):
    i = int(n)
    d = int(n * 10) % 10
    return i if d < 5 else i + 1

def get_orders(price, rnd, invest, size, spread = 10, first = False):
    coef = -1.0 # buy
    max_delta = coef * spread / 100.0
    first = coef * first / 100 if first else False
    chips = 0 # buy
    sz = size
    vest = invest / 1.005
    ord_lst, prices, total = main(vest, chips, max_delta, first, sz, price, rnd)

    return tuple([ord_lst, prices])

def int_sum(n):
    return (n**2 + n) // 2
    # x = (sqrt(8y + 1) - 1) / 2
    
def mk_lst(chips):          
    if chips > 2:
        for orders in range(1, chips):
            mchips = int_sum(orders)
            if mchips >= chips:
                break;
    else:                      # 1->(1,1); 2->(2,3)
        orders = chips
        mchips = orders + chips - 1    
    
    pct_lst = [(i+1)/mchips for i in range(0, orders)]

    delta, upper, lower = (0, 1, -1)
    for i in range(0, chips):
        ord_lst = []
        for j in range(0, orders):
            raw = chips * pct_lst[j] + delta
            rnd = mth_rnd(raw)
            ord_lst += [int(rnd)]            
        ord_cnt = sum(ord_lst)
        if ord_cnt == chips: break        
        if ord_cnt > chips:
            upper = delta
        if ord_cnt < chips:
            lower = delta
        delta = (upper + lower) / 2
    
    if ord_cnt != chips:
        print("Error: couldn't reduce list", ord_cnt, chips)
        exit(1)
    return ord_lst

def mk_ord(chips, max_delta, first, sz, price, rnd):
    srnd = len(str(sz).split('.')[-1])
    ord_lst = [round(i * sz, srnd) for i in mk_lst(chips)]
    step = max_delta / len(ord_lst)
    first = first - step if first else 0
    prices = [price * (first + 1 + step * (i + 1)) for i in range(0,len(ord_lst))]
    prices = [round(i, rnd) for i in prices]
    _total = [ord_lst[i] * round(prices[i], rnd) for i in range(0, len(prices))]
    total = round(sum(_total), rnd)
    return (ord_lst, prices, total)
    
def main(vest, chips, max_delta, first, sz, price, rnd):
    if chips > 0:
        ord_lst, prices, total = mk_ord(chips, max_delta, first, sz, price, rnd)    
    else:
        lchip = int(vest / price / sz)
        hchip = int(vest / price / sz / (1+max_delta))        
        for i in range(lchip, hchip + 1):
            ord_lst, prices, total = mk_ord(i, max_delta, first, sz, price, rnd)
            if(total > vest): 
                ord_lst, prices, total = mk_ord(i-1, max_delta, first, sz, price, rnd)
                break;
    return (ord_lst, prices, total)
