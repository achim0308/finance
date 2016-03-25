from decimal import *
from django.utils import timezone
import datetime
from lxml import html
import requests 
import pandas as pd
from bokeh.charts import Bar, vplot, output_file, show
from bokeh.charts.attributes import cat
from bokeh.charts.operations import blend
from .models import Security, Transaction, Account, HistValuation
from .calc import callSolver, callSolver2
    
def calcReturns(transaction_history):
    if not transaction_history:
        raise RuntimeError('Empty list')

    dates = []
    cashflows = []

    for transaction in transaction_history:
        if not (transaction.kind == Transaction.INTEREST and transaction.security.accumulate_interest == True):
            dates.append(transaction.date)
            cashflows.append(float(transaction.cashflow))

    r = "%.2f" % (callSolver(dates, cashflows) * 100.0)
        
    return r

def markToMarket(security):
# screen scraping based on onvista website
    try:
        page = requests.get(security.url)
    except requests.exeptions.RequestException:
        raise RuntimeError('Unknown URL')

    tree = html.fromstring(page.content)
        
    priceInfo = tree.xpath('//span[@itemprop="price"]/text()')
    
    try:
        price = float(priceInfo.pop().replace("'","").replace(",","."))
    except:
        raise RuntimeError('Empty list')
    return price

def markToMarketHistorical(security, date):
    h = HistValuation.objects.filter(security=security.id,date__lte=date).order_by('-date')

    if not h:
        return Decimal("0.0")
    else:
        return h[0].value

def getTotal(transaction_history, date):
    total = Decimal("0.0")

    if date == []:
        for t in transaction_history:
            if t.kind == Transaction.CURRENT:
                total = total + t.cashflow
    else:
        for t in transaction_history:
            if t.kind == Transaction.HISTORICAL and t.date == date:
                total = total + t.cashflow

    return '{:,}'.format(total)

def constructCompleteInfoRestrict(transaction_history, begin_date, end_date):
    if not transaction_history:
        raise RuntimeError('Empty list')
#    if not isinstance(begin_date, datetime):
#        raise RuntimeError('Not a date')
#    if not isinstance(end_date, datetime):
#        raise RuntimeError('Not a date')

    transaction_history2 = [t for t in transaction_history if t.date >= begin_date and t.date <= end_date]

    # calculate initial value
    other_securities = dict()
    mtm_securities = dict()

    for transaction in transaction_history:
        if transaction.date >= begin_date:
            continue
        else:
            if (transaction.security.mark_to_market):
                mtm_securities[transaction.security] = Decimal(handleNull(mtm_securities.get(transaction.security))) + transaction.num_transacted
            else:
                if ((transaction.security.accumulate_interest) and (transaction.kind == Transaction.INTEREST)):
                    other_securities[transaction.security] = Decimal(handleNull(other_securities.get(transaction.security))) + transaction.cashflow
                if ((transaction.kind == Transaction.SELL) or (transaction.kind == Transaction.BUY)):
                    other_securities[transaction.security] = Decimal(handleNull(other_securities.get(transaction.security))) - transaction.cashflow
        
    for s, cf in other_securities.items():
        transaction_history2.append(Transaction(kind=Transaction.HISTORICAL,
                                                date=begin_date,
                                                security=Security.objects.get(pk=s.id),
                                                expense = 0.0,
                                                tax = 0.0,
                                                cashflow = -cf,
                                                account = Account.objects.get(pk=1),
                                                num_transacted = ""))

    for s, num in mtm_securities.items():
        if (num != 0.0):
            price = markToMarketHistorical(s, begin_date)
            cf = Decimal("%.2f" % (-num*Decimal(price)))
            transaction_history2.append(Transaction(kind=Transaction.HISTORICAL, 
                                                    date=begin_date,
                                                    security=Security.objects.get(pk=s.id),
                                                    expense = 0.0,
                                                    tax = 0.0,
                                                    cashflow = cf,
                                                    account = Account.objects.get(pk=1),
                                                    num_transacted = num))    
    
    # calculate final value
    if end_date >= timezone.now().date():
        return constructCompleteInfo(transaction_history2)
        
    other_securities = dict()
    mtm_securities = dict()

    for transaction in transaction_history:
        if transaction.date > end_date:
            continue
        else:
            if (transaction.security.mark_to_market):
                mtm_securities[transaction.security] = Decimal(handleNull(mtm_securities.get(transaction.security))) + transaction.num_transacted
            else:
                if ((transaction.security.accumulate_interest) and (transaction.kind == Transaction.INTEREST)):
                    other_securities[transaction.security] = Decimal(handleNull(other_securities.get(transaction.security))) + transaction.cashflow
                if ((transaction.kind == Transaction.SELL) or (transaction.kind == Transaction.BUY)):
                    other_securities[transaction.security] = Decimal(handleNull(other_securities.get(transaction.security))) - transaction.cashflow

    
    for s, cf in other_securities.items():
        transaction_history2.append(Transaction(kind=Transaction.HISTORICAL,
                                                date=end_date,
                                                security=Security.objects.get(pk=s.id),
                                                expense = 0.0,
                                                tax = 0.0,
                                                cashflow = cf,
                                                account = Account.objects.get(pk=1),
                                                num_transacted = ""))

    for s, num in mtm_securities.items():
        if (num != 0.0):
            price = markToMarketHistorical(s, end_date)
            cf = Decimal("%.2f" % (num*Decimal(price)))
            transaction_history2.append(Transaction(kind=Transaction.HISTORICAL, 
                                                    date=end_date,
                                                    security=Security.objects.get(pk=s.id),
                                                    expense = 0.0,
                                                    tax = 0.0,
                                                    cashflow = cf,
                                                    account = Account.objects.get(pk=1),
                                                    num_transacted = num))    


    return transaction_history2

def constructCompleteInfo(transaction_history):
    if not transaction_history:
        raise RuntimeError('Empty list')

    other_securities = dict()
    mtm_securities = dict()

    for transaction in transaction_history:
        if (transaction.security.mark_to_market):
            mtm_securities[transaction.security] = Decimal(handleNull(mtm_securities.get(transaction.security))) + transaction.num_transacted
        else:
            if ((transaction.security.accumulate_interest) and (transaction.kind == Transaction.INTEREST)):
                other_securities[transaction.security] = Decimal(handleNull(other_securities.get(transaction.security))) + transaction.cashflow
            if ((transaction.kind == Transaction.SELL) or (transaction.kind == Transaction.BUY)):
                other_securities[transaction.security] = Decimal(handleNull(other_securities.get(transaction.security))) - transaction.cashflow
    
    for s, cf in other_securities.items():
        transaction_history.append(Transaction(kind=Transaction.CURRENT,
                                               date=timezone.now().date(),
                                               security=Security.objects.get(pk=s.id),
                                               expense = 0.0,
                                               tax = 0.0,
                                               cashflow = cf,
                                               account = Account.objects.get(pk=1),
                                               num_transacted = ""))

    for s, num in mtm_securities.items():
        if (num != 0.0):
            price = markToMarket(s)
            cf = Decimal("%.2f" % (num*Decimal(price)))
            transaction_history.append(Transaction(kind=Transaction.CURRENT, 
                                                   date=timezone.now().date(),
                                                   security=Security.objects.get(pk=s.id),
                                                   expense = 0.0,
                                                   tax = 0.0,
                                                   cashflow = cf,
                                                   account = Account.objects.get(pk=1),
                                                   num_transacted = ""))
    return transaction_history

def aggregate(transaction_history):
    net = dict()
    buy = dict()
    sell = dict()
    interest = dict()
    dividend = dict()
    historical = dict()
    
    for t in transaction_history:
        quarter = "%s-Q%i" % (t.date.year, (t.date.month-1)//3+1)
        net[quarter] = float(handleNull(net.get(quarter))) + float(t.cashflow)
        if t.kind == Transaction.BUY:
            buy[quarter] = float(handleNull(buy.get(quarter))) + float(t.cashflow)
        elif t.kind == Transaction.SELL:
            sell[quarter] = float(handleNull(sell.get(quarter))) + float(t.cashflow)
        elif t.kind == Transaction.INTEREST:
            interest[quarter] = float(handleNull(interest.get(quarter))) + float(t.cashflow)
        elif t.kind == Transaction.DIVIDEND:
            dividend[quarter] = float(handleNull(dividend.get(quarter))) + float(t.cashflow)
        elif t.kind == Transaction.HISTORICAL or t.kind == Transaction.CURRENT:
            historical[quarter] = float(handleNull(historical.get(quarter))) + float(t.cashflow)

    net = addMissingQuarters(net)
    buy = addMissingQuarters(buy)
    sell = addMissingQuarters(sell)
    interest = addMissingQuarters(interest)
    dividend = addMissingQuarters(dividend)
    historical = addMissingQuarters(historical)

    d = {'net': pd.Series(net),
         'buy': pd.Series(buy), 
         'sell': pd.Series(sell),
         'interest':pd.Series(interest),
         'dividend':pd.Series(dividend),
         'historical':pd.Series(historical)}

    df = pd.DataFrame(d)
    df['label']=df.index
    p1 = Bar(df, 
            values = blend('buy','sell','interest','dividend','historical',name='cashflow', labels_name='cf'),
            label=cat(columns='label',sort=False),
            stack=cat(columns='cf',sort=False))

    p2 = Bar(df,
             values = blend('net'),
             label='label')

    output_file("test.html")
    
    show(vplot(p1, p2))
            
def handleNull(s):
    if s is None:
        return 0.0
    else:
        return s

def addMissingQuarters(d):
    quarter = sorted(d)
    quarterFirst = quarter[0]
    quarterLast = quarter[-1]
            
    for y in range(int(quarterFirst[:4]), int(quarterLast[:4])+1):
        for q in range(1,5):
            s = "%s-Q%i" % (y, q)
            d[s] = float(handleNull(d.get(s)))

    return d
