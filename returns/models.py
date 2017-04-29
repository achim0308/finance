from datetime import datetime, date, timedelta
from decimal import *
from moneyed import Money
from djmoney.models.fields import MoneyField, CurrencyField
from djmoney.forms.widgets import CURRENCY_CHOICES
from django_countries.fields import CountryField

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection, models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible

import requests

class SecurityQuerySet(models.QuerySet):
    def securityOwnedBy(self,ownerID):
        pk_securities = Transaction.thobjects2.owner(ownerID) \
                                              .values_list('security', flat=True)
        return self.filter(pk__in=pk_securities)
    
class SecurityManager(models.Manager):
    def get_queryset(self):
        return SecurityQuerySet(self.model, using=self._db)
    
    def securityOwnedBy(self,ownerID):
        return self.get_queryset().securityOwnedBy(ownerID)

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
        return self.filter(date__gte = timezone.now()+timedelta(days=-30))
    
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
        if not securities is None:
            transactions = transactions.securities(securities)
        if not accounts is None:
            transactions = transactions.accounts(accounts)
        
        return th
    
    def cashflow(self, beginDate = None, endDate = None,
                       securities = None, accounts = None, owner = None):
    # sum daily cashflows of all transactions relevant for cashflows 
        cashflows = self.transactionHistory(beginDate, endDate, securities, accounts)
        cashflows = cashflows.notCashflowRelevant()
        
        # construct sum
        cashflows = cashflows.values('date') \
                             .annotate(sumCashflow=Sum('cashflow'))
        
        return cashflows

    def num(self, beginDate = None, endDate = None,
                  securities = None, accounts = None, owner = None):
    # sum transacted securities
        numSecurities = self.transactionHistory(beginDate, endDate, securities, accounts)
        numSecurities = numSecurities.markToMarket()
        
        # construct sum
        numSecurities = numSecurities.values('security_id') \
                                     .annotate(sumNumTransacted=Sum('num_transacted'))
        
        return numSecurities
    
    def curValue(self, beginDate = None, endDate = None,
                       securities = None, accounts = None, owner = None):
    # sum transacted securities
        curValues = self.transactionHistory(beginDate, endDate, securities, accounts)
        
        curValues1 = curValues.accumulatingSecuritiesInterestAndMatch()
        curValues2 = curValues.nonMarkToMarketInAndOutflows()
        
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
        
        return values
    
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

        sql3 = """SELECT security_id, sum(cashflow) AS cashflow FROM ( """ + sql1 + """ UNION ALL """ + sql2 + """ ) AS T5"""
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

class HistValuationQuerySet(models.QuerySet):
    def security(self,securityID):
        return self.filter(secrity=securityID)
    
    def date(self,date):
        return self.filter(date__lte=date)

class HistValuationManager(models.Manager):
    def get_queryset(self):
        return HistValuationQuerySet(self.model, using=self._db)

    def security(self,securityID):
        return self.get_queryset.security(securityID)
    
    def date(self,date):
        return self.get_queryset.date(date)
    
    def getHistValuation(self,securityID, date):
        try:
            h = self.get_queryset.security(securityID).date(date).earliest('date')
            return h.value
        except ObjectDoesNotExist:
            try:
                currency = Security.objects.get(id=securityID)
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
    
    objects = HistValuationManager
    
    def __str__(self):
        return "%s (%s): %s" % (self.security.name, self.date, self.value)

class Inflation(models.Model):
    # models inflation data
    date = models.DateField('Inflation date')
    inflationIndex = models.DecimalField('Inflation index',
                                         max_digits = 5,
                                         decimal_places = 2)
    country = CountryField()

    def __str__(self):
        return "%s: %4.1f" % (self.date, self.inflationIndex)

def dict_cursor(cursor):
    description = cursor.description
    return [dict(zip([col[0] for col in description], row))
            for row in cursor.fetchall()]

@python_2_unicode_compatible
class SecurityValuation(models.Model):
    # models the current valuation and the base value (in-outflow excluding interest or dividends) of a security of a given owner for a given date 
    date = models.DateField('Valuation date',
                            db_index=True)
    security = models.ForeignKey(Security,
                                 on_delete = models.PROTECT,
                                 db_index=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,
                              default=2)
    cur_value = MoneyField('Current value',
                           max_digits = 10,
                           decimal_places = 2,
                           default_currency='EUR')
    base_value = MoneyField('Base value based on in- and outflows',
                            max_digits = 10,
                            decimal_places = 2,
                            default_currency='EUR')
    sum_num = models.DecimalField('sum of number of securities exchanged',
                                   max_digits = 13,
                                   decimal_places = 5,
                                   default = 0)
    modifiedDate = models.DateField('Last modification',
                                    db_index=True)

    def __str__(self):
        return "%s (%s): %s (%s)" % (self.security.name, self.date, self.cur_value, self.base_value)

@python_2_unicode_compatible
class AccountValuation(models.Model):
    # models the current valuation and the base value (in-outflow excluding interest or dividends) of an account for a given date 
    date = models.DateField('Valuation date',
                            db_index=True)
    account = models.ForeignKey(Account,
                                on_delete = models.PROTECT,
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
