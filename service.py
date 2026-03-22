from datetime import datetime

#Important Functions 


def calculate_fifo(holding):
        lots = []
        for t in holding.transactions:
            if t.type == "BUY":
                lots.append((t.shares, t.price_per_share))
            else:
                shares_to_sell = t.shares
                while shares_to_sell > 0 and lots:
                    lots = lots[0]
                    if lots[0][0] > shares_to_sell:
                        lots[0][0] -= shares_to_sell
                        shares_to_sell = 0
                    else:
                        shares_to_sell -= lots[0][0]
                        lots.pop(0)

        holding.shares_owned = sum(lot[0] for lot in lots)
        if holding.shares_owned > 0:
            holding.total_invested = sum(lot[0] * lot[1] for lot in lots)
            holding.average_price = holding.total_invested / holding.shares
        else:
            holding.average_price = 0

# threshold will be datetime.timedelta(days=1)
def is_stale(stock, threshold):
    if not stock.last_updated:
        return True
    return stock.last_updated.date() + threshold > datetime.now()