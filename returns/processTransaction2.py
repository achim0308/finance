from decimal import *
from django.utils import timezone
from datetime import datetime, timedelta, date
from lxml import html
import requests 
import pandas as pd
from bokeh.charts import Bar, vplot, output_file, show
from bokeh.charts.attributes import cat
from bokeh.charts.operations import blend
from .models import Security, Transaction, Account, HistValuation
from .calc import callSolver, callSolver2
    
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

def constructCompleteInfo2(accounts = None, securities = None, beginDate = None, endDate = None):

    cashflowList = []
    ## add cashflow at beginning of period
    if beginDate:
        beginNum = Transaction.thobjects.getNum(accounts = accounts, securities = securities, beginDate = date(1900,1,1), endDate = beginDate + timedelta(days=-1))
        beginValue = Transaction.thobjects.getValue(accounts = accounts, securities = securities, beginDate = date(1900,1,1), endDate = beginDate + timedelta(days=-1))
    
        cf = 0
        if beginValue and beginValue != [] and beginValue[0]['cashflow'] != None:
            for v in beginValue:
                cf = cf + v['cashflow']
        if beginNum:
            for n in beginNum:
                if n['num_transacted'] != 0.0: 
                    price = markToMarketHistorical(Security.objects.get(pk=n['security_id']), beginDate + timedelta(days=-1))
                    cf = cf - Decimal('%.2f' % (Decimal(price)*n['num_transacted']))
        if cf != 0:
            cashflowList.append({'cashflow': cf, 'date': beginDate + timedelta(days=-1)})
    
    ## add cashflow at end of period
    endNum = Transaction.thobjects.getNum(accounts = accounts, securities = securities, beginDate = None, endDate = endDate)
    endValue = Transaction.thobjects.getValue(accounts = accounts, securities = securities, beginDate = None, endDate = endDate)

    cf = 0
    if endValue and endValue != [] and endValue[0]['cashflow'] != None:
        for v in endValue:
            cf = cf - v['cashflow']
    if endNum:
        if not endDate or endDate == timezone.now().date():
            for n in endNum:
                if n['num_transacted'] != 0.0: 
                    price = markToMarket(Security.objects.get(pk=n['security_id']))
                    cf = cf + Decimal('%.2f' % (Decimal(price)*n['num_transacted']))
        else:
            for n in endNum:
                if n['num_transacted'] != 0.0: 
                    price = markToMarketHistorical(Security.objects.get(pk=n['security_id']), endDate)
                    cf = cf + Decimal('%.2f' % (Decimal(price)*n['num_transacted']))
    if cf != 0:
        if not endDate:
            cashflowList.append({'cashflow': cf, 'date': timezone.now().date()})
        else:
            cashflowList.append({'cashflow': cf, 'date': endDate})
                    
    return cashflowList
    
def getReturns(accounts = None, securities = None, kind = None, beginDate = None, endDate = None):

    # Workaround for now --- maybe add this as another query
    if kind:
        accounts = None
        securities = [s.id for s in Security.objects.filter(kind__in = kind)]

    # construct cash flow list
    cashflowList = Transaction.thobjects.getCashflow(accounts=accounts, securities = securities, beginDate = beginDate, endDate = endDate)        

    # add current/historical values
    addCashflows = constructCompleteInfo2(accounts=accounts, securities = securities, beginDate = beginDate, endDate = endDate)

    # add additional cashflow information
    if addCashflows:
        if cashflowList is None:
            cashflowList = addCashflows
        else:
            cashflowList = cashflowList + addCashflows
        totalDecimal = Decimal(addCashflows[-1]['cashflow'])
        total = '{:,}'.format(addCashflows[-1]['cashflow'])
        if len(addCashflows) == 2:
            initial = '{:,}'.format(-addCashflows[-2]['cashflow'])
        else:
            initial = 0
    else:
        total = 0
        initial = 0
        totalDecimal = 0
    # calculate returns
    try:
        returns = callSolver2(cashflowList)
        errorReturns = ''
    except RuntimeError as e:
        errorReturns = "Error: {0}".format(e)
        returns = ''

    return  {'cashflowList': cashflowList, 'total': total, 'totalDecimal': totalDecimal, 'initial': initial, 'returns': returns, 'errorReturns': errorReturns}

def gatherData(accounts = None, securities = None, kind = None, beginDate = None, endDate = None):

    # Workaround for now --- maybe add this as another query
    if kind:
        accounts = None
        securities = [s.id for s in Security.objects.filter(kind__in = kind)]      

    # get transaction history
    transaction_history = Transaction.thobjects.getTransactionHistory(accounts=accounts, securities = securities, beginDate = beginDate, endDate = endDate)

    # get financial performance info
    performance = getReturns(accounts=accounts, securities = securities, beginDate = beginDate, endDate = endDate)

    # Make list of accounts/securities
    if accounts:
        accounts = Account.objects.filter(pk__in=accounts)
    if securities:
        securities = Security.objects.filter(pk__in=securities)
    
    return {'accounts': accounts, 'securities': securities, 'beginDate': beginDate, 'endDate':endDate, 'cashflowList': performance['cashflowList'], 'total': performance['total'], 'returns': performance['returns'], 'errorReturns': performance['errorReturns'], 'transaction_history': transaction_history}

def addSegmentPerformance():
    pTG = addHistoricalPerformance(kind=[Security.TAGESGELD])
    pAK = addHistoricalPerformance(kind=[Security.AKTIE])
    pAF = addHistoricalPerformance(kind=[Security.AKTIENETF])
    pBD = addHistoricalPerformance(kind=[Security.BONDS])
    pBF = addHistoricalPerformance(kind=[Security.BONDSETF])
    pAV = addHistoricalPerformance(kind=[Security.ALTERSVORSORGE])

    return {'pTG': pTG, 'pAK': pAK, 'pAF': pAF, 'pBD': pBD, 'pBF': pBF, 'pAV': pAV}

def addHistoricalPerformance(accounts = None, securities = None, kind = None):
    today = timezone.now().date()
    thisYear = date(today.year,1,1)
    prevYear = yearsago(1)
    fiveYear = yearsago(5)

    performanceYTD = getReturns(accounts=accounts, securities = securities, kind = kind, beginDate = thisYear, endDate = today)
    performancePrevYear = getReturns(accounts=accounts, securities = securities, kind = kind, beginDate = prevYear, endDate = today)
    performanceFiveYear = getReturns(accounts=accounts, securities = securities, kind = kind, beginDate = fiveYear, endDate = today)
    performanceOverall = getReturns(accounts=accounts, securities = securities, kind = kind)

    return {'rYTD': performanceYTD['returns'],
            'iYTD': performanceYTD['initial'],
            'tYTD': performanceYTD['total'],
            'r1Y': performancePrevYear['returns'],
            'i1Y': performancePrevYear['initial'],
            't1Y': performancePrevYear['total'],
            'r5Y': performanceFiveYear['returns'],
            'i5Y': performanceFiveYear['initial'],
            't5Y': performanceFiveYear['total'],
            'rInfY': performanceOverall['returns'],
            'iInfY': performanceOverall['initial'],
            'tInfY': performanceOverall['total']}

def calcInterest(security, date):
    performance = getReturns(securities=[security], endDate = date)
    total = performance['totalDecimal']
    s = Security.objects.get(pk=security)
    # calculate interest payment (calc_interest is in %!)
    interest = total * s.calc_interest / Decimal(100.0)
    return interest

def match(transaction, percentage):
    # Copy transaction and adjust
    transaction.pk = None
    transaction.kind = Transaction.INTEREST
    transaction.cashflow = + Decimal(percentage) / Decimal(100.0) * abs(transaction.cashflow)

    return transaction

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

def yearsago(years, from_date=None):
    if from_date is None:
        from_date = timezone.now().date()
    try:
        return from_date.replace(year=from_date.year - years)
    except ValueError:
        # Must be 2/29
        return from_date.replace(month=2, day=28,year=from_date.year-years)
