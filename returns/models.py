from datetime import datetime, date
from decimal import *
from moneyed import Money, get_currency
from djmoney.models.fields import MoneyField, CurrencyField
from djmoney.forms.widgets import CURRENCY_CHOICES
from django_countries.fields import CountryField

from django.conf import settings
from django.db import connection, models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible

import requests

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
        (TAGESGELD,'TAGESGELD'),
        (AKTIE, 'AKTIE'),
        (AKTIENETF, 'AKTIEN-ETF'),
        (BONDSETF, 'BONDS-ETF'),
        (BONDS, 'BOND'),
        (ALTERSVORSORGE, 'ALTERSVORSORGE'),
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
    def __str__(self):
        return "%s (%s)" % (self.name, self.descrip)

    def markToMarket(self):
    # screen scraping based on yahoo website
        if not self.mark_to_market:
            raise RuntimeError('Security not marked to market prices')
        try:
            data = requests.get(self.url)
            value = Decimal(data.content)
            price = Money(amount=value,currency=get_currency(code=self.currency))
        except:
            raise RuntimeError('Trouble getting data')
        
        return price

    class Meta:
        ordering = ['name']
        
@python_2_unicode_compatible
class Account(models.Model):
    # models an account
    name = models.CharField('name of account',
                            max_length = 40)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,
                              default=2,
#                              on_delete=models.CASCADE)
	)
	
    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class TransactionManager(models.Manager):
    def getTransactionHistory(self, beginDate = None, endDate = None, securities = None, accounts = None, owner = None):

        cursor = connection.cursor()
        if securities == None and accounts == None:
            sql = """SELECT T1.id, DATE_FORMAT(date,'%m/%d/%Y') tdate, T1.kind, security_id, name AS security_name, expense, tax, cashflow, account_id, num_transacted FROM returns_transaction T1 INNER JOIN returns_security T2 ON T1.security_id = T2.id"""
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

    thobjects = TransactionManager()
    objects = models.Manager()

    def __str__(self):
        return "%s: (%s) %s (%s) %s" % (self.date, self.kind, self.security.name, self.security.descrip, self.cashflow)

    def is_recent_transaction(self):
        return timezone.now() >= self.date >= timezone.now() - datetime.timedelta(months=3)

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
