from time import mktime
from datetime import datetime, date, timedelta
from decimal import *
from moneyed import Money
from djmoney.models.fields import MoneyField, CurrencyField
from djmoney.forms.widgets import CURRENCY_CHOICES
from django_countries.fields import CountryField

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection, models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible

from .calc import Solver
from .utilities import yearsago

import requests

class SecurityQuerySet(models.QuerySet):
    def securityOwnedBy(self,ownerID):
        pk_securities = Transaction.thobjects2.owner(ownerID) \
                                              .values_list('security', flat=True)
        return self.filter(pk__in=pk_securities)
    
    def markToMarket(self):
        return self.filter(mark_to_market=True)
    
    def kinds(self, kind):
        return self.filter(kind__in=kind)
    
class SecurityManager(models.Manager):
    def get_queryset(self):
        return SecurityQuerySet(self.model, using=self._db)
    
    def securityOwnedBy(self,ownerID):
        return self.get_queryset().securityOwnedBy(ownerID)
    
    def markToMarket(self):
        return self.get_queryset().markToMarket()
    
    def kinds(self, kind):
        return self.get_queryset().kinds(kind)
    
    def saveCurrentMarkToMarketValue(self):
        # for each mark to market security get and save current value
        markToMarketSecurities = self.get_queryset().markToMarket()
        today = timezone.now().date()
        
        for s in markToMarketSecurities:
            try:
                value = s.markToMarket()
                HistValuation.objects.update_or_create(
                        date = today,
                        security = s,
                        defaults = { 'value': value }
                )
            except:
                pass

@python_2_unicode_compatible
class Security(models.Model):
    # models a single security held in an account
    TAGESGELD = 'TG'
    AKTIE = 'AK'
    AKTIENETF = 'AF'
    BONDSETF = 'BF'
    BONDS = 'BD'
    ALTERSVORSORGE = 'AV'
    SEC_KIND_CHOICES = (
        (TAGESGELD,'Savings'),
        (AKTIE, 'Stock'),
        (AKTIENETF, 'Stock-ETF'),
        (BONDSETF, 'Bond-ETF'),
        (BONDS, 'Bond'),
        (ALTERSVORSORGE, 'Retirement'),
    )
    name = models.CharField('name of security',
                            max_length = 40)
    descrip = models.CharField('detailed description',
                               max_length = 400)
    url = models.URLField('URL for pricing info',
                          max_length = 400,
                          default = '',
                          blank = True)
    kind = models.CharField('kind of security',
                            max_length = 2,
                            choices = SEC_KIND_CHOICES,
                            default = AKTIENETF)
    mark_to_market = models.BooleanField('True if security priced to market',
                                         default = False)
    accumulate_interest = models.BooleanField('True if interest accumulates (e.g. savings accounts)',
                                              default = False)
    calc_interest =  models.DecimalField('Fixed interest rate (%)',
                                         max_digits = 6,
                                         decimal_places = 2,
                                         default = 0)
    currency = models.CharField('Currency',
                                max_length = 3,
                                choices = CURRENCY_CHOICES,
                                default = 'EUR')
    
    objects = SecurityManager()
    
    def __str__(self):
        return "%s (%s)" % (self.name, self.descrip)
    
    def get_absolute_url(self):
        return reverse('views.security', args=[str(self.id)])

    def markToMarket(self):
    # screen scraping based on yahoo website
        if not self.mark_to_market:
            raise RuntimeError('Security not marked to market prices')
        try:
            data = requests.get(self.url)
            value = Decimal(float(data.content))
            price = Money(amount=value,currency=self.currency)
        except:
            raise RuntimeError('Trouble getting data for security', security.name)
        
        return price

    def calcInterest(self, date, owner):
    # calculate interest for security based on for year leading up to date
        if not self.calc_interest > 0:
            raise RuntimeError('Security does not have fixed interest payment')
        total = SecurityValuation.objects.filter(security=self, date__lte=date, owner_id=owner).order_by('date').last().cur_value
        
        # calculate interest payment (calc_interest is in %!)
        interest = Money(total.amount * self.calc_interest / Decimal(100.0), self.currency)
        return interest
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Securities'

class AccountQuerySet(models.QuerySet):
    def accountOwnedBy(self,ownerID):
        pk_accounts = Transaction.thobjects2.owner(ownerID) \
                                            .values_list('account', flat=True)
        return self.filter(pk__in=pk_accounts)

class AccountManager(models.Manager):
    def get_queryset(self):
        return AccountQuerySet(self.model, using=self._db)

    def accountOwnedBy(self,ownerID):
        return self.get_queryset().accountOwnedBy(ownerID)

@python_2_unicode_compatible
class Account(models.Model):
    # models an account
    name = models.CharField('name of account',
                            max_length = 40)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,
                              default=2,
#                              on_delete=models.CASCADE)
    )
    currency = models.CharField('Currency',
                                max_length = 3,
                                choices = CURRENCY_CHOICES,
                                default = 'EUR')
    
    objects = AccountManager()
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('views.account', args=[str(self.id)])
    
    class Meta:
        ordering = ['name']

class TransactionQuerySet(models.QuerySet):
    # custom query set function for Transaction
    def owner(self, ownerID):
        return self.filter(owner_id=ownerID)
    
    def beginDate(self, beginDate):
        return self.filter(date__gte = beginDate)
    
    def endDate(self, endDate):
        return self.filter(date__lte = endDate)
    
    def securities(self, securities):
        return self.filter(security_id__in = securities)
    
    def accounts(self, accounts):
        return self.filter(account_id__in = accounts)
    
    def recent(self):
        return self.filter(date__gte = timezone.now()+timedelta(days=-30)).select_related('security','account')
    
    def notCashflowRelevant(self):
    # remove transactions that are not relevant for cash flows, 
    # i.e., interest payments or company matches on securities that accumulate interest
        return self.filter(~(
                             Q(security__accumulate_interest = True) &
                                 (Q(kind = Transaction.INTEREST) |
                                  Q(kind = Transaction.MATCH))
                             ))
    
    def accumulatingSecuritiesInterestAndMatch(self):
    # show only interest and company match transactions
    # for securities that accumulate interest
        return self.filter(Q(security__accumulate_interest = True) &
                           (Q(kind = Transaction.INTEREST) | Q(kind = Transaction.MATCH))
                          )
    
    def nonMarkToMarketInAndOutflows(self):
    # exclude only interest and company match transactions as well as 
    # transactions for for securities that are marked to market
        return self.exclude(security__mark_to_market = False) \
                   .exclude(kind=Transaction.INTEREST) \
                   .exclude(kind=Transaction.MATCH) \
    
    def markToMarket(self):
    # only select transactions of mark_to_market securities
        return self.filter(security__mark_to_market = True)

class TransactionManager2(models.Manager):
    def get_queryset(self):
        return TransactionQuerySet(self.model, using=self._db)
    
    def recent(self):
        return self.get_queryset().recent().order_by('date')
    
    def owner(self, ownerID):
        return self.get_queryset().owner(ownerID)
    
    def transactionHistory(self, beginDate = None, endDate = None,
                           securities = None, accounts = None, owner = None):
        transactions = self.get_queryset().order_by('date')
        if not beginDate is None:
            transactions = transactions.beginDate(beginDate)
        if not endDate is None:
            transactions = transactions.endDate(endDate)
        if not owner is None:
            transactions = transactions.owner(owner)
        if not securities is None:
            transactions = transactions.securities(securities)
        if not accounts is None:
            transactions = transactions.accounts(accounts)
        
        return transactions
    
    def cashflow(self, beginDate = None, endDate = None,
                       securities = None, accounts = None, owner = None):
    # sum daily cashflows of all transactions relevant for cashflows 
        cashflows = self.transactionHistory(beginDate, endDate, securities, accounts, owner)
        cashflows = cashflows.notCashflowRelevant()
        
        # construct sum
        cashflows = cashflows.values('date') \
                             .annotate(sumCashflow=Sum('cashflow'))
        
        return cashflows

    def num(self, beginDate = None, endDate = None,
                  securities = None, accounts = None, owner = None):
    # sum transacted securities
        numSecurities = self.transactionHistory(beginDate, endDate, securities, accounts, owner)
        numSecurities = numSecurities.markToMarket()
        
        # construct sum
        numSecurities = numSecurities.values('security_id') \
                                     .annotate(sumNumTransacted=Sum('num_transacted'))
        
        return numSecurities
    
    def curValue(self, beginDate = None, endDate = None,
                       securities = None, accounts = None, owner = None):
    # get current, i.e. at end date if available, value of securities
        curValues = self.transactionHistory(beginDate, endDate, securities, accounts, owner)
        
        curValues1 = self.accumulatingSecuritiesInterestAndMatch()
        curValues2 = self.nonMarkToMarketInAndOutflows()
        
        # sum over cashflows only
        curValues1 = curValues1.values('security_id') \
                               .annotate(curValue=Sum(-F('cashflow')))
        
        # sum over cashflows minus taxes and expenses 
        # (since these also reduce the value of security)
        curValues2 = curValues2.values('security_id') \
                               .annotate(curValue=Sum(-(F('cashflow')
                                                        -F('tax')
                                                        -F('expense'))))
        
        # combine query
        curValues = curValues1 | curValues2
        
        # return sum of all current values
        return curValues
        
    
class TransactionManager(models.Manager):
    def getTransactionHistory(self, beginDate = None, endDate = None, securities = None, accounts = None, owner = None):

        cursor = connection.cursor()
        if securities == None and accounts == None:
            sql = """SELECT T1.id, DATE_FORMAT(date,'%%m/%%d/%%Y') tdate, T1.kind, security_id, name AS security_name, expense, tax, cashflow, account_id, num_transacted FROM returns_transaction T1 INNER JOIN returns_security T2 ON T1.security_id = T2.id"""
            arg = ()
            if owner != None:
                sql = sql + """ WHERE T1.owner_id = """ + str(owner)
        else:
            sql = """SELECT T1.id, DATE_FORMAT(date,'%%m/%%d/%%Y') tdate, T1.kind, security_id, name AS security_name, expense, tax, cashflow, account_id, num_transacted FROM returns_transaction T1 INNER JOIN returns_security T2 ON T1.security_id = T2.id"""
            if securities == None:
                format_string = ','.join(['%s'] * len(accounts))
                sql = sql + """ WHERE account_id IN (%s)""" % (format_string)
                arg = tuple(accounts)
            else: 
                format_string = ','.join(['%s'] * len(securities))
                sql = sql + """ WHERE security_id IN (%s)""" % (format_string)
                arg = tuple(securities)
            if owner != None:
                sql = sql + """ AND T1.owner_id = """ + str(owner)
        if beginDate != None and endDate != None:
            sql = sql + """ AND date BETWEEN CAST(%s AS DATE) AND CAST(%s AS DATE)"""
            arg =  arg + (beginDate.strftime('%Y-%m-%d'), endDate.strftime('%Y-%m-%d'))
        elif endDate != None:
            sql = sql + """ AND date BETWEEN CAST(%s AS DATE) AND CAST(%s AS DATE)"""
            arg = arg + ('1900-01-01', endDate.strftime('%Y-%m-%d'))

        sql = sql + """ ORDER BY date"""
        arg = None if arg == () else arg

        print(sql, arg)

        cursor.execute(sql, arg)
        
        return dict_cursor(cursor)

    def getCashflow(self, beginDate = None, endDate = None, securities = None, accounts = None, owner= None):

        cursor = connection.cursor()
        sql = """SELECT date, SUM(cashflow) AS cashflow FROM returns_transaction T1 INNER JOIN returns_security T2 ON T1.security_id = T2.id WHERE NOT(T2.accumulate_interest = 1 AND (T1.kind = '%s' OR T1.kind ='%s'))""" % (Transaction.INTEREST, Transaction.MATCH)
        if securities == None and accounts == None:
            arg = ()
        else:
            if securities == None:
                format_string = ','.join(['%s'] * len(accounts))
                sql = sql + """ AND account_id IN (%s)""" % (format_string)
                arg = tuple(accounts)
            else: 
                format_string = ','.join(['%s'] * len(securities))
                sql = sql + """ AND security_id IN (%s)""" % (format_string)
                arg = tuple(securities)
                
        if owner != None:
            sql = sql + """ AND owner_id = """ + str(owner)
        if beginDate != None and endDate != None:
            sql = sql + """ AND date BETWEEN CAST(%s AS DATE) AND CAST(%s AS DATE)"""
            arg =  arg + (beginDate.strftime('%Y-%m-%d'), endDate.strftime('%Y-%m-%d'))
        elif endDate != None:
            sql = sql + """ AND date BETWEEN CAST(%s AS DATE) AND CAST(%s AS DATE)"""
            arg = arg + ('1900-01-01', endDate.strftime('%Y-%m-%d'))
        
        sql = sql + """ GROUP BY date ORDER BY date"""
        arg = None if arg == "" else arg
        cursor.execute(sql, arg)

        if cursor.rowcount == 0:
            return None
        else:
            return dict_cursor(cursor)

    def getNum(self, beginDate = None, endDate = None, securities = None, accounts = None, owner = None):
        cursor = connection.cursor()
        sql = """SELECT security_id, SUM(num_transacted) AS num_transacted FROM returns_transaction T1 INNER JOIN returns_security T2 ON T1.security_id = T2.id WHERE T2.mark_to_market"""
        if securities == None and accounts == None:
            arg = ()
        else:
            if securities == None:
                format_string = ','.join(['%s'] * len(accounts))
                sql = sql + """ AND account_id IN (%s)""" % (format_string)
                arg = tuple(accounts)
            else: 
                format_string = ','.join(['%s'] * len(securities))
                sql = sql + """ AND security_id IN (%s)""" % (format_string)
                arg = tuple(securities)
        
        if owner != None:
            sql = sql + """ AND owner_id = """ + str(owner)
        if beginDate != None and endDate != None:
            sql = sql + """ AND date BETWEEN CAST(%s AS DATE) AND CAST(%s AS DATE)"""
            arg =  arg + (beginDate.strftime('%Y-%m-%d'), endDate.strftime('%Y-%m-%d'))
        elif endDate != None:
            sql = sql + """ AND date BETWEEN CAST(%s AS DATE) AND CAST(%s AS DATE)"""
            arg = arg + ('1900-01-01', endDate.strftime('%Y-%m-%d'))

        
        sql = sql + """ GROUP BY security_id ORDER BY security_id"""
        arg = None if arg == () else arg
        cursor.execute(sql, arg)

        if cursor.rowcount == 0:
            return None
        else:
            return dict_cursor(cursor)

    def getValue(self, beginDate = None, endDate = None, securities = None, accounts = None, owner= None):
        cursor = connection.cursor()
        sql1 = """SELECT security_id, -cashflow AS cashflow FROM returns_transaction T1 INNER JOIN returns_security T2 ON T1.security_id = T2.id WHERE (T2.accumulate_interest AND (T1.kind = '%s' OR T1.kind = '%s'))""" % (Transaction.INTEREST, Transaction.MATCH)
        sql2 = """SELECT security_id, cashflow-tax-expense AS cashflow FROM returns_transaction T3 INNER JOIN returns_security T4 ON T3.security_id = T4.id WHERE (NOT T4.mark_to_market AND (NOT T3.kind = '%s' AND NOT T3.kind = '%s'))""" % (Transaction.INTEREST, Transaction.MATCH)
        sql = ""
        arg = ()
        
        if owner != None:
            sql = sql + """ AND owner_id = """ + str(owner)
        if beginDate != None and endDate != None:
            sql = sql + """ AND date BETWEEN CAST(%s AS DATE) AND CAST(%s AS DATE)"""
            arg = (beginDate.strftime('%Y-%m-%d'), endDate.strftime('%Y-%m-%d'))
        elif endDate != None:
            sql = sql + """ AND date BETWEEN CAST(%s AS DATE) AND CAST(%s AS DATE)"""
            arg = ('1900-01-01', endDate.strftime('%Y-%m-%d'))
        if securities != None or accounts != None:
            if securities == None:
                format_string = ','.join(['%s'] * len(accounts))
                sql = sql + """ AND account_id IN (%s)""" % (format_string)
                arg = arg + tuple(accounts)
            else: 
                format_string = ','.join(['%s'] * len(securities))
                sql = sql + """ AND security_id IN (%s)""" % (format_string)
                arg = arg + tuple(securities)
                
        arg = arg + arg
        sql1 = sql1 + sql
        sql2 = sql2 + sql

        sql3 = """SELECT security_id, sum(cashflow) AS cashflow FROM ( """ + sql1 + """ UNION ALL """ + sql2 + """ ) AS T5 GROUP BY security_id"""
        arg = None if arg == () else arg
        cursor.execute(sql3, arg)

        if cursor.rowcount == 0:
            return None
        else:
            d = dict_cursor(cursor)
            if not d[0]:
                return None
            else:
                return d

@python_2_unicode_compatible
class Transaction(models.Model):
    # models a single transaction of a security
    SELL = 'SE'
    BUY = 'BU'
    INTEREST = 'IN'
    DIVIDEND = 'DI'
    MATCH = 'MA'
    CURRENT = 'CU'
    HISTORICAL = 'HI'
    TRANSACT_KIND_CHOICES = (
        (SELL, 'Sell'),
        (BUY, 'Buy'),
        (INTEREST, 'Interest'),
        (DIVIDEND, 'Dividend'),
        (MATCH, 'Company Match'),
    )

    date = models.DateField('transaction date',
                            db_index=True)
    kind = models.CharField('kind of transaction',
                            max_length = 2,
                            choices = TRANSACT_KIND_CHOICES,
                            default = SELL)
    security = models.ForeignKey(Security,
                                 on_delete = models.PROTECT)
    expense = MoneyField('expenses allocated to transaction',
                         max_digits = 10,
                         decimal_places = 2,
                         default = '0 EUR',
                         default_currency='EUR')
    tax = MoneyField('taxes allocated to transaction',
                     max_digits = 10,
                     decimal_places = 2,
                     default = '0 EUR',
                     default_currency='EUR')
    cashflow = MoneyField('cashflow during transaction (Neg.=Outgoing)',
                          max_digits = 10,
                          decimal_places = 2,
                          default_currency='EUR')
    account = models.ForeignKey(Account,
                                on_delete = models.PROTECT)
    num_transacted = models.DecimalField('number of securities exchanged (Neg.=Sold)',
                                         max_digits = 13,
                                         decimal_places = 5,
                                         default = 0)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,
                              default=2,
#                              on_delete=models.CASCADE)
)
    modifiedDate = models.DateField('last modified date',
                                    db_index=True)

    thobjects2 = TransactionManager2()
    thobjects = TransactionManager()
    objects = models.Manager()

    def __str__(self):
        return "%s: (%s) %s (%s) %s" % (self.date, self.kind, self.security.name, self.security.descrip, self.cashflow)

    def match(self, percentage):
    # Copy transaction and adjust
        self.pk = None
        self.kind = Transaction.MATCH
        self.cashflow = + Decimal(percentage) / Decimal(100.0) * abs(self.cashflow)

        return self

class HistValuationQuerySet(models.QuerySet):
    def security(self,securityID):
        return self.filter(security=securityID)
    
    def date(self,date):
        return self.filter(date__lte=date)

class HistValuationManager(models.Manager):
    def get_queryset(self):
        return HistValuationQuerySet(self.model, using=self._db)

    def security(self,securityID):
        return self.get_queryset().security(securityID)
    
    def date(self,date):
        return self.get_queryset().date(date)
    
    def getHistValuation(self,securityID, date):
        try:
            h = self.get_queryset().security(securityID).date(date).latest('date')
            return h.value
        except ObjectDoesNotExist:
            try:
                currency = Security.objects.get(id=securityID).currency
                return Money(0.0,currency=currency)
            except ObjectDoesNotExist:
                return Money(0.0,currency='EUR')

@python_2_unicode_compatible
class HistValuation(models.Model):
    # models a security at a date
    date = models.DateField('Valuation date',
                            db_index=True)
    security = models.ForeignKey(Security,
                                 on_delete = models.PROTECT,
                                 db_index=True)
    value = MoneyField('Valuation',
                       max_digits = 10,
                       decimal_places = 2,
                       default_currency='EUR')
    
    objects = HistValuationManager()
    
    def __str__(self):
        return "%s (%s): %s" % (self.security.name, self.date, self.value)
    
    def get_absolute_url(self):
        return reverse('views.transaction', args=[str(self.id)])

class InflationManager(models.Manager):
    def getHistoricalRateOfInflation(self):
        # calculate inflation rate for multiple time periods
        today = timezone.now().date()
        thisYear = date(today.year,1,1)
        prevYear = yearsago(1)
        fiveYear = yearsago(5)

        inflationYTD = self.rateOfInflation(beginDate = thisYear, endDate = today)
        inflationPrevYear = self.rateOfInflation(beginDate = prevYear, endDate = today)
        inflationFiveYear = self.rateOfInflation(beginDate = fiveYear, endDate = today)
        inflationOverall = self.rateOfInflation()

        return {'inYTD': inflationYTD, 
                'in1Y': inflationPrevYear, 
                'in5Y': inflationFiveYear, 
                'inInfY': inflationOverall, 
                }
    
    def rateOfInflation(self, beginDate = None, endDate = None):
        inflation = Inflation.objects.order_by('date')
        if beginDate is None: 
            inflation1 = inflation.first()
        else:
            inflation1 = inflation.filter(date__lte=beginDate).last()
        if endDate is None:
            inflation2 = inflation.last()
        else:
            inflation2 = inflation.filter(date__lte=endDate).last()
        
        if not inflation1 or not inflation2:
            print("Error: No data")
            inflationRate = ''
        else:
            solver = Solver()
            solver.addCashflow(inflation1.inflationIndex, inflation1.date)
            solver.addCashflow(-inflation2.inflationIndex, inflation2.date)
            
            try:
                inflationRate = solver.calcRateOfReturn()
            except RuntimeError as e:
                inflationRate = ''
                print("Error calculating inflation: {0}".format(e))
        
        return inflationRate

class Inflation(models.Model):
    # models inflation data
    date = models.DateField('Inflation date')
    inflationIndex = models.DecimalField('Inflation index',
                                         max_digits = 5,
                                         decimal_places = 2)
    country = CountryField()
    
    objects = InflationManager()
    
    def __str__(self):
        return "%s: %4.1f" % (self.date, self.inflationIndex)
    
    def get_absolute_url(self):
        return reverse('views.inflation', args=[str(self.id)])

def dict_cursor(cursor):
    description = cursor.description
    return [dict(zip([col[0] for col in description], row))
            for row in cursor.fetchall()]

class ValuationQuerySet(models.QuerySet):
    def getHistoricalRateOfReturn(self):
        # calculate internal rate of return for multiple time periods

        today = timezone.now().date()
        thisYear = date(today.year,1,1)
        prevYear = yearsago(1)
        fiveYear = yearsago(5)

        performanceYTD = self.getRateOfReturn(beginDate = thisYear, endDate = today)
        performancePrevYear = self.getRateOfReturn(beginDate = prevYear, endDate = today)
        performanceFiveYear = self.getRateOfReturn(beginDate = fiveYear, endDate = today)
        performanceOverall = self.getRateOfReturn()
        
        return {'rYTD': performanceYTD['rate'],
                'iYTD': performanceYTD['initial'],
                'tYTD': performanceYTD['final'],
                'r1Y': performancePrevYear['rate'],
                'i1Y': performancePrevYear['initial'],
                't1Y': performancePrevYear['final'],
                'r5Y': performanceFiveYear['rate'],
                'i5Y': performanceFiveYear['initial'],
                't5Y': performanceFiveYear['final'],
                'rInfY': performanceOverall['rate'],
                'iInfY': performanceOverall['initial'],
                'tInfY': performanceOverall['final']}

    def restrictDateRange(self, beginDate = None, endDate = None):
        qs = self.order_by('date')
        if endDate != None:
            qs = qs.filter(date__lte=endDate)
            
        if beginDate != None:
            qs = qs.filter(date__gte=beginDate)

        return qs
    
    def getRateOfReturn(self, beginDate = None, endDate = None):
        # calculate internal rate of return given the cashflows

        # limit query set to date range given
        qs = self.restrictDateRange(beginDate, endDate)
        
        # aggregate values per date
        qs = qs.values('date').annotate(sumBaseValue=Sum('base_value'),
                                        sumCurValue=Sum('cur_value'))

        
        # get value at beginning of interval
        try:
            base0 = self.filter(date__lt=beginDate).order_by('date')\
                        .values('date', 'cur_value_currency').annotate(sumBaseValue=Sum('base_value'),
                                                                        sumCurValue=Sum('cur_value'))\
                        .last()
            date0 = base0['date']
            baseValue0 = base0['sumBaseValue']
            initialValue0 = Money(base0['sumCurValue'], base0['cur_value_currency'])
        except:
        # if query empty --> baseValue must be zero
            date0 = None
            baseValue0 = 0.
            initialValue0 = 0.

        # get final value
        try:
            final = self.filter(date__gte=endDate).order_by('date')\
                        .values('date', 'cur_value_currency').annotate(sumCurValue=Sum('cur_value'))\
                        .first()
            finalValue = Money(final['sumCurValue'],final['cur_value_currency'])
            finalDate = final['date']
        except:
        # if query empty --> either no valuations at all or none at end date
            finalValue = 0.
            finalDate = None
            try:
                # take last valuation
                final = self.order_by('date')\
                            .values('date', 'cur_value_currency').annotate(sumCurValue=Sum('cur_value'))\
                            .last()
                finalValue = Money(final['sumCurValue'],final['cur_value_currency'])
                finalDate = final['date']
            except:
                pass
        
        solver = Solver()

        if date0 is not None:
            solver.addCashflow(initialValue0.amount, date0)
        
        # add date/cashflows to solver
        for v in qs:
            cashflow = float(v['sumBaseValue'])-float(baseValue0)
            if cashflow != 0.0:
                solver.addCashflow(cashflow, v['date'])
            baseValue0 = v['sumBaseValue']
        
        if finalDate is not None:
            # negative due to different sign conventions
            solver.addCashflow(-finalValue.amount, finalDate)

        try:
            r = solver.calcRateOfReturn()
        except:
            r = 'Error'
        
        return {'rate': r,
                'initial': initialValue0,
                'final': finalValue }
    
    def makeChart(self):
        # Collects information and processes it to show chart of valuation
        # requires queryset 
        valuations = self.order_by('date')
        
        xdata=[]
        y1data=[]
        y2data=[]
        currency = self.last().cur_value.currency
        for v in valuations:
            # must convert date to integer
            xdata.append(int(mktime(v.date.timetuple())*1000))
            # must convert Decimal to float
            y1data.append(float(v.cur_value.amount))
            y2data.append(float(v.base_value.amount))
        
        tooltip_date = "%b %Y"
        extra_serie={
            "tooltip": {"y_start": "", "y_end": currency},
            "date_format": tooltip_date
        }
        
        chartdata = {
            'x': xdata,
            'name1': 'Actual value', 'y1': y1data, 'extra1': extra_serie,
            'name2': 'Inflow - outflows', 'y2': y2data, 'extra2': extra_serie,
        }
        charttype = "lineWithFocusChart"
        chartcontainer = 'asset_history'
        data = {
            'charttype': charttype,
            'chartdata': chartdata,
            'chartcontainer': chartcontainer,
            'extra': {
                'x_is_date': True,
                'x_axis_format': '%b %Y',
                'tag_script_js': True,
                'jquery_on_ready': False,
            }
        }
        
        return data

class ValuationManager(models.Manager):
    def get_queryset(self):
        return ValuationQuerySet(self.model, using=self._db)
    
    def getRateOfReturn(self, beginDate = None, endDate = None):
        return self.get_queryset().getRateOfReturn(beginDate, endDate)
    
    def makeChart(self):
        return self.get_queryset().makeChart()

@python_2_unicode_compatible
class Valuation(models.Model):
    # abstract model to store historical valuation to be used to calculate rate of returns
    date = models.DateField('Valuation date',
                            db_index=True)
    cur_value = MoneyField('Current value',
                           max_digits = 10,
                           decimal_places = 2,
                           default_currency='EUR')
    base_value = MoneyField('Base value based on in- and outflows',
                            max_digits = 10,
                            decimal_places = 2,
                            default_currency='EUR')
    modifiedDate = models.DateField('Last modification',
                                    db_index=True)
    
    objects = ValuationManager()
    
    class Meta:
        abstract = True

@python_2_unicode_compatible
class SecurityValuation(Valuation):
    # models the current valuation and the base value (in-outflow excluding interest or dividends) of a security of a given owner for a given date 
    security = models.ForeignKey(Security,
                                 on_delete = models.PROTECT,
                                 db_index=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,
                              default=2)
    sum_num = models.DecimalField('sum of number of securities exchanged',
                                   max_digits = 13,
                                   decimal_places = 5,
                                   default = 0)
    
    def __str__(self):
        return "%s (%s): %s (%s)" % (self.security.name, self.date, self.cur_value, self.base_value)

@python_2_unicode_compatible
class AccountValuation(Valuation):
    # models the current valuation and the base value (in-outflow excluding interest or dividends) of an account for a given date 
    account = models.ForeignKey(Account,
                                on_delete = models.PROTECT,
                                db_index=True)
    
    def __str__(self):
        return "%s (%s): %s (%s)" % (self.account.name, self.date, self.cur_value, self.base_value)

class ExchangeToEUR(models.Model):
    # models currency exchange rate data
    date = models.DateField('Exchange date')
    USDperEUR = models.DecimalField('Exchange rate (USD/EUR)',
                                    max_digits = 7,
                                    decimal_places = 5)
    def __str__(self):
        return "%s: %2.5f" % (self.date, self.USDperEUR)
