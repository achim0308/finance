from django.db import transaction

from decimal import *
from datetime import date
from moneyed import Money, get_currency
from .models import Security, Transaction, Account, HistValuation, Inflation, SecurityValuation, AccountValuation
from .utilities import yearsago, last_day_of_month, mid_day_of_next_month

def updateSecurityValuation(owner):
    # get date of last update of security valuations
    try:
        lastUpdate = SecurityValuation.object.filter(owner=owner).order_by('-modifiedDate').last().modifiedDate
    except:
         lastUpdate = date(1900,1,1)
    # find transactions that have been added since
    transactionList = Transaction.objects.filter(owner=owner,modifiedDate__gte=lastUpdate).order_by('date').select_related('security')

    today = date.today()

    if transactionList.exists():
        transactionIterator = transactionList.iterator()
        endOfTransactionList = False
        previousTransactionNotProcessed = False
        currentDate = last_day_of_month(transactionList.first().date)
    
    else:
        endOfTransactionList = True
        currentDate = last_day_of_month(today)
    
    # set up data structure
    numSecurityObjects = Security.objects.order_by('id').last().id
    securityActive = [False for i in range(numSecurityObjects+1)]
    securityMtM = [False for i in range(numSecurityObjects+1)]
    numSecurity = [Decimal(0.0) for i in range(numSecurityObjects+1)]
    curValueSecurity = [Decimal(0.0) for i in range(numSecurityObjects+1)]
    baseValueSecurity = [Decimal(0.0) for i in range(numSecurityObjects+1)]
    currencySecurity = ['' for i in range(numSecurityObjects+1)]
    
    # populate using existing data
    for s in Security.objects.all():
        sID = s.id
        try:
            secValuation = SecurityValuation.objects.filter(owner=owner, date__lte=lastUpdate, security=s).order_by('-date').first()
            numSecurity[sID] = secValuation.sum_num
            curValueSecurity[sID] = secValuation.cur_value.amount
            baseValueSecurity[sID] = secValuation.base_value.amount
            securityActive[sID] = True
            currencySecurity[sID] = s.currency
            if s.markToMarket == True:
                securityMtM = True
        except:
            currencySecurity[sID] = 'EUR'
            pass


    endOfMonth = True
    if today.day > 15:
        lastDay = last_day_of_month(today)
    else:
        lastDay = today.replace(day=15)
    
    while currentDate <= lastDay:
        
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
            tSecurityId = t.security_id
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
                    # if all securities were sold, no longer need to update
                    if numSecurity[securityId] <= 0.0:
                        securityActive[securityId] = False;
                    curValueSecurity[securityId] = numSecurity[securityId] * (HistValuation.objects.getHistValuation(securityId, currentDate).amount)
                else:
                    # if all securities were sold, no longer need to update
                    if curValueSecurity[securityId] <= 0.0:
                        securityActive[securityId] = False;
                
                # store information, update record if possible
                s, created = SecurityValuation.objects.update_or_create(
                    date = currentDate,
                    security_id = securityId,
                    owner = owner,
                    defaults = {
                        'cur_value': Money(amount=curValueSecurity[securityId], currency=currencySecurity[securityId]),
                        'base_value': Money(amount=baseValueSecurity[securityId], currency=currencySecurity[securityId]),
                        'sum_num': numSecurity[securityId],
                        'modifiedDate': today
                    },
                )
        
        # go to next date (15th of next month or last day of month)
        if endOfMonth == True:
            currentDate = mid_day_of_next_month(currentDate)
            endOfMonth = False
        else:
            currentDate = last_day_of_month(currentDate)
            endOfMonth = True

def updateAccountValuation():
    # get date of last update of account valuations
    try:
        lastUpdate = AccountValuation.object.order_by('-modifiedDate').last().modifiedDate
    except:
         lastUpdate = date(1900,1,1)
    # find transactions that have been added since
    transactionList = Transaction.objects.filter(modifiedDate__gte=lastUpdate).order_by('date').select_related('security')

    today = date.today()

    if transactionList.exists():
        transactionIterator = transactionList.iterator()
        endOfTransactionList = False
        previousTransactionNotProcessed = False
        currentDate = last_day_of_month(transactionList.first().date)

    else:
        endOfTransactionList = False
        currentDate = last_day_of_month(today)
    
    # construct list of all accounts that require updating
    relevantAccounts = list(set(transactionList.values_list('account_id', flat=True).order_by('account_id')))
    
    # construct list of all required transactions
    transactionList = Transaction.objects.filter(account_id__in=relevantAccounts).order_by('date')
    
    # set up data structure
    numSecurityObjects = Security.objects.order_by('id').last().id
    numAccountObjects = Account.objects.order_by('id').last().id
    accountActive = [False for i in range(numAccountObjects+1)]
    securityActive = [False for i in range(numSecurityObjects*numAccountObjects+1)]
    securityEverActive = [False for i in range(numSecurityObjects*numAccountObjects+1)]
    securityMtM = [False for i in range(numSecurityObjects+1)]
    numSecurity = [Decimal(0.0) for i in range(numSecurityObjects*numAccountObjects+1)]
    curValueSecurity = [Decimal(0.0) for i in range(numSecurityObjects*numAccountObjects+1)]
    baseValueSecurity = [Decimal(0.0) for i in range(numSecurityObjects*numAccountObjects+1)]
    currencySecurity = ['' for i in range(numSecurityObjects+1)]
    for s in Security.objects.all():
        currencySecurity[s.id] = s.currency
    currencyAccount = ['' for i in range(numAccountObjects+1)]
    for a in Account.objects.all():
       currencyAccount[a.id] = a.currency



    endOfMonth = True
    if today.day > 15:
        lastDay = last_day_of_month(today)
    else:
        lastDay = today.replace(day=15)
    
    while currentDate <= lastDay:
        
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
            tSecurityId = t.security_id
            tAccountId = t.account_id
            tPosition = tSecurityId + (tAccountId-1)*numSecurityObjects
            securityActive[tPosition] = True
            securityEverActive[tPosition] = True
            accountActive[tAccountId] = True
            
            # update base value
            # treat accumulated interest or matched contributions separately
            # -cashflow b/c sign convention for cashflows
            if not (t.security.accumulate_interest and (t.kind == Transaction.INTEREST or t.kind == Transaction.MATCH)):
                baseValueSecurity[tPosition] = baseValueSecurity[tPosition] - t.cashflow.amount
            
            # update number of securities
            if t.security.mark_to_market:
                numSecurity[tPosition] = numSecurity[tPosition] + t.num_transacted
                securityMtM[tSecurityId] = True
            # update current value
            else:
                # treat accumulated interest or matched contributions separate
                # cashflow b/c sign convention for cashflows (always >0 for these)
                if t.security.accumulate_interest and (t.kind == Transaction.INTEREST or t.kind == Transaction.MATCH):
                    curValueSecurity[tPosition] = curValueSecurity[tPosition] + t.cashflow.amount
                # -cashflow b/c sign convention for cashflows
                elif not (t.kind == Transaction.INTEREST or t.kind == Transaction.MATCH):
                    curValueSecurity[tPosition] = curValueSecurity[tPosition] - (t.cashflow.amount - t.tax.amount - t.expense.amount)
        
        # store information 
        # loop over accounts
        for accountId in range(1,numAccountObjects+1):
            # check if account is active
            if accountActive[accountId] == True:
                curValueAccount = Money(amount=0.0, currency=currencyAccount[accountId])
                baseValueAccount = Money(amount=0.0, currency=currencyAccount[accountId])
                
                # loop over securities
                for securityId in range(1,numSecurityObjects+1):
                    positionId = securityId + (accountId-1)*numSecurityObjects
                    # only need to do sth for active objects
                    if securityActive[positionId] == True:
                        # update security value with market data if applicable
                        if securityMtM[securityId] == True:
                            # if all securities were sold, no longer need to update
                            if numSecurity[positionId] <= 0.0:
                                securityActive[positionId] = False
                            curValueSecurity[positionId] = numSecurity[positionId] * (HistValuation.objects.getHistValuation(securityId, currentDate).amount)
                        else:
                            # if all securities were sold, no longer need to update
                            if curValueSecurity[positionId] <= 0.0:
                                securityActive[positionId] = False
                                                
                        curValueAccount = curValueAccount + Money(amount=curValueSecurity[positionId],
                                                                  currency=currencySecurity[securityId])
                        baseValueAccount = baseValueAccount + Money(amount=baseValueSecurity[positionId],
                                                                    currency=currencySecurity[securityId])
                    elif securityEverActive[positionId] == True:
                        curValueAccount = curValueAccount + Money(amount=curValueSecurity[positionId],
                                                                  currency=currencySecurity[securityId])
                        baseValueAccount = baseValueAccount + Money(amount=baseValueSecurity[positionId],
                                                                    currency=currencySecurity[securityId])
                    #if accountId == 8:
                    #    print(currentDate, accountId, securityId, curValueAccount, baseValueAccount)
                        
                # store information, update record if possible
                s, created = AccountValuation.objects.update_or_create(
                    date = currentDate,
                    account_id = accountId,
                    defaults = {
                        'cur_value': curValueAccount,
                        'base_value': baseValueAccount,
                        'modifiedDate': today
                    },
                )
        
        # go to next date (15th of next month or last day of month)
        if endOfMonth == True:
            currentDate = mid_day_of_next_month(currentDate)
            endOfMonth = False
        else:
            currentDate = last_day_of_month(currentDate)
            endOfMonth = True

def makePieChartSegPerf(segPerf):
# Prepare data for pie chart
    listOfAssets = []
    xdata = []
    for kind in Security.SEC_KIND_CHOICES:
        listOfAssets.append(kind[1])
        xdata.append(kind[1])
    ydata = [float(segPerf[s]['tYTD'].amount) for s in listOfAssets]
    
    chartdata = {'x': xdata, 'y1': ydata}
    charttype = 'pieChart'
    chartcontainer = 'asset_allocation'

    return {
        'charttype': charttype,
        'chartdata': chartdata,
        'chartcontainer': chartcontainer,
        'extra': {
            'x_is_date': False,
            'x_axis_format': '',
            'tag_script_js': True,
            'jquery_on_ready': False,
            'donut': True,
        }
    }

def makeBarChartSegPerf(segPerf):
    listOfAssets = []
    catdata = []
    for kind in Security.SEC_KIND_CHOICES:
        listOfAssets.append(kind[1])
        catdata.append(kind[1])
    xdata = ["YTD", "1 Yr", "5 Yrs", "Overall"]
    listOfTimes = ["rYTD", "r1Y", "r5Y", "rInfY"]
    
    ydata = {}
    for s in listOfAssets:
        ydata[s] = [segPerf[s][t] for t in listOfTimes]

    chartdata = {
        'x': xdata,
        'name1': catdata[0], 'y1': ydata[listOfAssets[0]],
        'name2': catdata[1], 'y2': ydata[listOfAssets[1]],
        'name3': catdata[2], 'y3': ydata[listOfAssets[2]],
        'name4': catdata[3], 'y4': ydata[listOfAssets[3]],
        'name5': catdata[4], 'y5': ydata[listOfAssets[4]],
        'name6': catdata[5], 'y6': ydata[listOfAssets[5]],
    }

    charttype = 'multiBarHorizontalChart'
    chartcontainer = 'asset_performance'
    return {
        'charttype': charttype,
        'chartdata': chartdata,
        'chartcontainer': chartcontainer,
        'extra': {
            'x_is_date': False,
            'x_axis_format': '',
            'tag_script_js': True,
            'jquery_on_ready': False,
        }
    }
