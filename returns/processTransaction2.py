from decimal import *
from django.utils import timezone
from datetime import datetime, timedelta, date
from lxml import html
from moneyed import Money, get_currency
import requests 
import csv
from .models import Security, Transaction, Account, HistValuation, Inflation, SecurityValuation
from .calc import callSolver2
    
def markToMarket(security):
# screen scraping based on yahoo website

    try:
        data = requests.get(security.url)
        price = float(data.content)
    except:
        raise RuntimeError('Trouble getting data')
    return price

#    try:
#        page = requests.get(security.url)
#    except requests.exeptions.RequestException:
#        raise RuntimeError('Unknown URL')

#    tree = html.fromstring(page.content)

    #priceInfo = tree.xpath('//span[@itemprop="price"]/text()')
#    priceInfo = tree.xpath('//*[@id="table1"]/tbody/tr[1]/td/text()')

#    try:
#        price = float(priceInfo.pop().replace("'","").replace(",","."))
#    except:
#        raise RuntimeError('Empty list')
#    return price

def markToMarketHistorical(securityID, date):
    h = HistValuation.objects.filter(security=securityID,date__lte=date).order_by('-date')[:1]

    if not h:
        return Decimal("0.0")
    else:
        return h[0].value

def addNewMarkToMarketData():
    markToMarketSecurities = Security.objects.filter(mark_to_market=True)
    today = timezone.now().date()
    
    for s in markToMarketSecurities:
        if HistValuation.objects.filter(security=s.id,date=today).exists() == False:
            try:
                value = markToMarket(s)
                newH = HistValuation(date=today, security=s, value=Money(amount=value,currency=get_currency(code=s.currency)))
                newH.save()
            except :
                pass

def constructCompleteInfo2(accounts = None, securities = None, beginDate = None, endDate = None, owner = None):

    cashflowList = []
    initialValue = 0.0
    finalValue = 0.0
    ## add cashflow at beginning of period
    if beginDate:
        beginNum = Transaction.thobjects.getNum(accounts = accounts, securities = securities, beginDate = date(1900,1,1), endDate = beginDate + timedelta(days=-1), owner = owner)
        beginValue = Transaction.thobjects.getValue(accounts = accounts, securities = securities, beginDate = date(1900,1,1), endDate = beginDate + timedelta(days=-1), owner = owner)
    
        cf = 0
        if beginValue and beginValue != [] and beginValue[0]['cashflow'] != None:
            for v in beginValue:
                cf = cf + v['cashflow']
        if beginNum:
            for n in beginNum:
                if n['num_transacted'] != 0.0: 
                    price = markToMarketHistorical(n['security_id'], beginDate + timedelta(days=-1))
                    cf = cf - Decimal('%.2f' % (price*n['num_transacted']))
        if cf != 0:
            cashflowList.append({'cashflow': cf, 'date': beginDate + timedelta(days=-1)})
            initialValue = -cf
        else:
            initialValue = 0.0
    
    ## add cashflow at end of period
    endNum = Transaction.thobjects.getNum(accounts = accounts, securities = securities, beginDate = None, endDate = endDate, owner = owner)
    endValue = Transaction.thobjects.getValue(accounts = accounts, securities = securities, beginDate = None, endDate = endDate, owner = owner)

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
                    price = markToMarketHistorical(n['security_id'], endDate)
                    cf = cf + Decimal('%.2f' % (price*n['num_transacted']))
    if cf != 0:
        if not endDate:
            cashflowList.append({'cashflow': cf, 'date': timezone.now().date()})
        else:
            cashflowList.append({'cashflow': cf, 'date': endDate})
        finalValue = cf
    else:
        finalValue = 0.0
                    
    return {'cashflows': cashflowList, 'initialValue': initialValue, 'finalValue': finalValue}
    
def getReturns(accounts = None, securities = None, kind = None, beginDate = None, endDate = None, owner = None):

    # Workaround for now --- maybe add this as another query
    if kind:
        accounts = None
        securities = [s.id for s in Security.objects.filter(kind__in = kind)]

    # construct cash flow list
    cashflowList = Transaction.thobjects.getCashflow(accounts=accounts, securities = securities, beginDate = beginDate, endDate = endDate, owner = owner)        

    # add current/historical values
    addCashflows = constructCompleteInfo2(accounts=accounts, securities = securities, beginDate = beginDate, endDate = endDate, owner = owner)

    # add additional cashflow information
    if addCashflows['cashflows']:
        if cashflowList is None:
            cashflowList = addCashflows['cashflows']
        else:
            cashflowList = cashflowList + addCashflows['cashflows']
        totalDecimal = Decimal(addCashflows['finalValue'])
        total = '{:,.2f}'.format(addCashflows['finalValue'])
        initial = '{:,.2f}'.format(addCashflows['initialValue'])
    else:
        total = '{:,.2f}'.format(0)
        initial = '{:,.2f}'.format(0)
        totalDecimal = 0
    # calculate returns
    try:
        returns = callSolver2(cashflowList)
        errorReturns = ''
    except RuntimeError as e:
        errorReturns = "Error: {0}".format(e)
        returns = ''

    inflation = calcInflation(beginDate, endDate)

    return  {'cashflowList': cashflowList, 'total': total, 'totalDecimal': totalDecimal, 'initial': initial, 'returns': returns, 'errorReturns': errorReturns, 'inflation': inflation['inflation'], 'errorInflation': inflation['errorInflation']}

def gatherData(accounts = None, securities = None, kind = None, beginDate = None, endDate = None, owner = None):

    # Workaround for now --- maybe add this as another query
    if kind:
        accounts = None
        securities = [s.id for s in Security.objects.filter(kind__in = kind)]      

    # get transaction history
    transaction_history = Transaction.thobjects.getTransactionHistory(accounts=accounts, securities = securities, beginDate = beginDate, endDate = endDate, owner = owner)

    # get financial performance info
    performance = getReturns(accounts=accounts, securities = securities, beginDate = beginDate, endDate = endDate, owner = owner)

    # Make list of accounts/securities
    if accounts:
        accounts = Account.objects.filter(pk__in=accounts)
    if securities:
        securities = Security.objects.filter(pk__in=securities)
    
    return {'accounts': accounts, 'securities': securities, 'beginDate': beginDate, 'endDate':endDate, 'cashflowList': performance['cashflowList'], 'total': performance['total'], 'returns': performance['returns'], 'errorReturns': performance['errorReturns'], 'inflation': performance['inflation'], 'errorInflation': performance['errorInflation'], 'transaction_history': transaction_history}

def addSegmentPerformance(owner = None):
    pTG = addHistoricalPerformance(kind=[Security.TAGESGELD], owner = owner)
    pAK = addHistoricalPerformance(kind=[Security.AKTIE], owner = owner)
    pAF = addHistoricalPerformance(kind=[Security.AKTIENETF], owner = owner)
    pBD = addHistoricalPerformance(kind=[Security.BONDS], owner = owner)
    pBF = addHistoricalPerformance(kind=[Security.BONDSETF], owner = owner)
    pAV = addHistoricalPerformance(kind=[Security.ALTERSVORSORGE], owner = owner)

    # Calculate fraction of each asset class
    #total = float(pTG['tYTD']) + float(pAK['tYTD']) + float(pAF['tYTD']) + float(pBD['tYTD']) + float(pBF['tYTD']) + float(pAV['tYTD'])
    total = pTG['totalDecimal'] + pAK['totalDecimal'] + pAF['totalDecimal'] + pBD['totalDecimal'] + pBF['totalDecimal'] + pAV['totalDecimal']

    pTG['frac'] = '{:,.2f}'.format(pTG['totalDecimal'] / total * 100)
    pAK['frac'] = '{:,.2f}'.format(pAK['totalDecimal'] / total * 100)
    pAF['frac'] = '{:,.2f}'.format(pAF['totalDecimal'] / total * 100)
    pBD['frac'] = '{:,.2f}'.format(pBD['totalDecimal'] / total * 100)
    pBF['frac'] = '{:,.2f}'.format(pBF['totalDecimal'] / total * 100)
    pAV['frac'] = '{:,.2f}'.format(pAV['totalDecimal'] / total * 100)

    return {'pTG': pTG, 'pAK': pAK, 'pAF': pAF, 'pBD': pBD, 'pBF': pBF, 'pAV': pAV}

def addHistoricalPerformance(accounts = None, securities = None, kind = None, owner = None):
    today = timezone.now().date()
    thisYear = date(today.year,1,1)
    prevYear = yearsago(1)
    fiveYear = yearsago(5)

    performanceYTD = getReturns(accounts=accounts, securities = securities, kind = kind, beginDate = thisYear, endDate = today, owner = owner)
    performancePrevYear = getReturns(accounts=accounts, securities = securities, kind = kind, beginDate = prevYear, endDate = today, owner = owner)
    performanceFiveYear = getReturns(accounts=accounts, securities = securities, kind = kind, beginDate = fiveYear, endDate = today, owner = owner)
    performanceOverall = getReturns(accounts=accounts, securities = securities, kind = kind, owner = owner)

    return {'rYTD': performanceYTD['returns'],
            'iYTD': performanceYTD['initial'],
            'inYTD': performanceYTD['inflation'], 
            'tYTD': performanceYTD['total'],
            'totalDecimal': performanceYTD['totalDecimal'],
            'r1Y': performancePrevYear['returns'],
            'i1Y': performancePrevYear['initial'],
            'in1Y': performancePrevYear['inflation'], 
            't1Y': performancePrevYear['total'],
            'r5Y': performanceFiveYear['returns'],
            'i5Y': performanceFiveYear['initial'],
            'in5Y': performanceFiveYear['inflation'], 
            't5Y': performanceFiveYear['total'],
            'rInfY': performanceOverall['returns'],
            'iInfY': performanceOverall['initial'],
            'inInfY': performanceOverall['inflation'], 
            'tInfY': performanceOverall['total']}

def calcInterest(security, date2):
    performance = getReturns(securities=[security], endDate = date2)
    total = performance['totalDecimal']
    s = Security.objects.get(pk=security)
    # calculate interest payment (calc_interest is in %!)
    interest = total * s.calc_interest / Decimal(100.0)
    return interest

def match(transaction, percentage):
    # Copy transaction and adjust
    transaction.pk = None
    transaction.kind = Transaction.MATCH
    transaction.cashflow = + Decimal(percentage) / Decimal(100.0) * abs(transaction.cashflow)

    return transaction

def calcInflation(beginDate, endDate):
    # Obtains inflation
    if beginDate == None: 
        inflation1 = Inflation.objects.order_by('date')[:1]
    else:
        inflation1 = Inflation.objects.filter(date__lte=beginDate).order_by('-date')[:1]
    if endDate == None:
        inflation2 = Inflation.objects.order_by('-date')[:1]
    else:
        inflation2 = Inflation.objects.filter(date__lte=endDate).order_by('-date')[:1]

    cashflowList = []

    if not inflation1 or not inflation2:
        errorInflation = "Error: No data"
        inflation = ''
    else:
        i1 = inflation1[0]
        i2 = inflation2[0]
        cashflowList.append({'cashflow': i1.inflationIndex, 'date': i1.date})
        cashflowList.append({'cashflow': -i2.inflationIndex, 'date': i2.date})

        try:
            inflation = callSolver2(cashflowList)
            errorInflation = ''
        except RuntimeError as e:
            errorInflation = "Error: {0}".format(e)
            inflation = ''
    return {'inflation':inflation,'errorInflation':errorInflation}

def yearsago(years, from_date=None):
    if from_date is None:
        from_date = timezone.now().date()
    try:
        return from_date.replace(year=from_date.year - years)
    except ValueError:
        # Must be 2/29
        return from_date.replace(month=2, day=28,year=from_date.year-years)

def last_day_of_month(any_day):
    next_month = any_day.replace(day=28) + timedelta(days=4)  # this will never fail
    return next_month - timedelta(days=next_month.day)

def updateSecurityValuation(owner):
    # get date of last update of security valuations
    try:
        lastUpdate = SecurityValuation.object.filter(owner=owner).order_by('-modifiedDate').last().modifiedDate
    except:
         lastUpdate = date(1900,1,1)
    # find transactions that have been added since
    transactionList = Transaction.objects.filter(owner=owner,modifiedDate__gte=lastUpdate).order_by('date')

    if not transactionList.exists():
        return # nothing to do here 

    # set up data structure    
    numSecurityObjects = Security.objects.order_by('id').last().id
    securityActive = [False for i in range(numSecurityObjects+1)]
    securityMtM = [False for i in range(numSecurityObjects+1)]
    numSecurity = [Decimal(0.0) for i in range(numSecurityObjects+1)]
    curValueSecurity = [Decimal(0.0) for i in range(numSecurityObjects+1)]
    baseValueSecurity = [Decimal(0.0) for i in range(numSecurityObjects+1)]
    
    currentDate = last_day_of_month(transactionList.first().date)
    today = date.today()
    
    transactionIterator = transactionList.iterator()
    endOfTransactionList = False
    previousTransactionNotProcessed = False
    
    while currentDate <= today:
        
        while not endOfTransactionList: 
            # advance iterator unless previous transaction was not processed
            if not previousTransactionNotProcessed:
                try:
                    t = next(transactionIterator)
                except StopIteration:
                    endOfTransactionList = True
                    break
            else:
                previousTransactionNotProcessed = False
            
            # check if transaction occurred in currently considered month
            if t.date > currentDate:
                previousTransactionNotProcessed = True
                break
            # process current transaction record
            tSecurityId = t.security.id
            securityActive[tSecurityId] = True
            
            # update base value
            # treat accumulated interest or matched contributions separately
            # -cashflow b/c sign convention for cashflows
            if not (t.security.accumulate_interest and (t.kind == Transaction.INTEREST or t.kind == Transaction.MATCH)):
                baseValueSecurity[tSecurityId] = baseValueSecurity[tSecurityId] - t.cashflow.amount
            
            # update number of securities
            if t.security.mark_to_market:
                numSecurity[tSecurityId] = numSecurity[tSecurityId] + t.num_transacted
                securityMtM[tSecurityId] = True
            # update current value
            else:
                # treat accumulated interest or matched contributions separate
                # cashflow b/c sign convention for cashflows (always >0 for these)
                if t.security.accumulate_interest and (t.kind == Transaction.INTEREST or t.kind == Transaction.MATCH):
                    curValueSecurity[tSecurityId] = curValueSecurity[tSecurityId] + t.cashflow.amount
                # -cashflow b/c sign convention for cashflows
                elif not (t.kind == Transaction.INTEREST or t.kind == Transaction.MATCH):
                    curValueSecurity[tSecurityId] = curValueSecurity[tSecurityId] - (t.cashflow.amount - t.tax.amount - t.expense.amount)
        
        # store information 
        for securityId in range(1,numSecurityObjects+1):
            if securityActive[securityId] == True:
                # update security value with market data if applicable
                if securityMtM[securityId] == True:
                    curValueSecurity[securityId] = numSecurity[securityId] * (markToMarketHistorical(securityId, currentDate).amount)
                
                currency = Security.objects.get(pk=securityId).currency
                
                # store information, update record if possible
                s, created = SecurityValuation.objects.update_or_create(
                    date = currentDate,
                    security_id = securityId,
                    owner = owner,
                    defaults = {
                        'cur_value': Money(amount=curValueSecurity[securityId], currency=get_currency(code=currency)),
                        'base_value': Money(amount=baseValueSecurity[securityId], currency=get_currency(code=currency)),
                        'modifiedDate': today
                    },
                )
        
        # go to end of next month
        currentDate = last_day_of_month(currentDate + timedelta(days=1))