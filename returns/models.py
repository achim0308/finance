from datetime import datetime, date

from django.db import connection, models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible

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

    def __str__(self):
        return "%s (%s)" % (self.name, self.descrip)
        
@python_2_unicode_compatible
class Account(models.Model):
    # models an account
    name = models.CharField('name of account',
                            max_length = 40)
    def __str__(self):
        return self.name

class TransactionManager(models.Manager):
    def getTransactionHistory(self, beginDate = None, endDate = None, securities = None, accounts = None):

        cursor = connection.cursor()
        if securities == None and accounts == None:
            sql = """SELECT T1.id, DATE_FORMAT(date,'%m/%d/%Y') tdate, T1.kind, security_id, name AS security_name, expense, tax, cashflow, account_id, num_transacted FROM returns_transaction T1 INNER JOIN returns_security T2 ON T1.security_id = T2.id"""
            arg = ()
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
        if beginDate != None and endDate != None:
            sql = sql + """ AND date BETWEEN CAST(%s AS DATE) AND CAST(%s AS DATE)"""
            arg =  arg + (beginDate.strftime('%Y-%m-%d'), endDate.strftime('%Y-%m-%d'))
        
        sql = sql + """ ORDER BY date"""
        arg = None if arg == () else arg

        cursor.execute(sql, arg)
        
        return dict_cursor(cursor)

    def getCashflow(self, beginDate = None, endDate = None, securities = None, accounts = None):

        cursor = connection.cursor()
        sql = """SELECT date, SUM(cashflow) AS cashflow FROM returns_transaction T1 INNER JOIN returns_security T2 ON T1.security_id = T2.id WHERE NOT(T2.accumulate_interest = 1 AND T1.kind = '%s')""" % (Transaction.INTEREST)
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
        if beginDate != None and endDate != None:
            sql = sql + """ AND date BETWEEN CAST(%s AS DATE) AND CAST(%s AS DATE)"""
            arg =  arg + (beginDate.strftime('%Y-%m-%d'), endDate.strftime('%Y-%m-%d'))
        
        sql = sql + """ GROUP BY date ORDER BY date"""
        arg = None if arg == "" else arg
        cursor.execute(sql, arg)

        if cursor.rowcount == 0:
            return None
        else:
            return dict_cursor(cursor)

    def getNum(self, beginDate = None, endDate = None, securities = None, accounts = None):
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
        if beginDate != None and endDate != None:
            sql = sql + """ AND date BETWEEN CAST(%s AS DATE) AND CAST(%s AS DATE)"""
            arg =  arg + (beginDate.strftime('%Y-%m-%d'), endDate.strftime('%Y-%m-%d'))
        
        sql = sql + """ GROUP BY security_id ORDER BY security_id"""
        arg = None if arg == () else arg
        cursor.execute(sql, arg)

        if cursor.rowcount == 0:
            return None
        else:
            return dict_cursor(cursor)

    def getValue(self, beginDate = None, endDate = None, securities = None, accounts = None):
        cursor = connection.cursor()
        sql1 = """SELECT security_id, -cashflow AS cashflow FROM returns_transaction T1 INNER JOIN returns_security T2 ON T1.security_id = T2.id WHERE (T2.accumulate_interest AND T1.Kind = '%s')""" % (Transaction.INTEREST)
        sql2 = """SELECT security_id, cashflow AS cashflow FROM returns_transaction T3 INNER JOIN returns_security T4 ON T3.security_id = T4.id WHERE (NOT T4.mark_to_market AND NOT T3.Kind = '%s')""" % (Transaction.INTEREST)
        sql = ""
        arg = ()
        if beginDate != None and endDate != None:
            sql = sql + """ AND date BETWEEN CAST(%s AS DATE) AND CAST(%s AS DATE)"""
            arg = (beginDate.strftime('%Y-%m-%d'), endDate.strftime('%Y-%m-%d'))
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
    CURRENT = 'CU'
    HISTORICAL = 'HI'
    TRANSACT_KIND_CHOICES = (
        (SELL, 'SE'),
        (BUY, 'BU'),
        (INTEREST, 'IN'),
        (DIVIDEND, 'DI'),
    )

    date = models.DateField('transaction date')
    kind = models.CharField('kind of transaction',
                            max_length = 2,
                            choices = TRANSACT_KIND_CHOICES,
                            default = SELL)
    security = models.ForeignKey(Security,
                                 on_delete = models.PROTECT)
    expense = models.DecimalField('expenses allocated to transaction',
                                  max_digits = 10,
                                  decimal_places = 2,
                                  default = 0)
    tax = models.DecimalField('taxes allocated to transaction',
                              max_digits = 10,
                              decimal_places = 2,
                              default = 0)
    cashflow = models.DecimalField('cashflow during transaction (Neg.=Outgoing)',
                                   max_digits = 10,
                                   decimal_places = 2)
    account = models.ForeignKey(Account,
                                on_delete = models.PROTECT)
    num_transacted = models.DecimalField('number of securities exchanged (Neg.=Sold)',
                                         max_digits = 13,
                                         decimal_places = 5,
                                         default = 0)

    thobjects = TransactionManager()
    objects = models.Manager()

    def __str__(self):
        return "%s: (%s) %s (%s) EUR %10.2f" % (self.date, self.kind, self.security.name, self.security.descrip, self.cashflow)

    def is_recent_transaction(self):
        return timezone.now() >= self.date >= timezone.now() - datetime.timedelta(months=3)

@python_2_unicode_compatible
class HistValuation(models.Model):
    # models a security at a date
    date = models.DateField('Valuation date')
    security = models.ForeignKey(Security,
                                 on_delete = models.PROTECT)
    value = models.DecimalField('Valuation',
                                   max_digits = 10,
                                   decimal_places = 2)

    def __str__(self):
        return "%s (%s): EUR %10.2f" % (self.security.name, self.date, self.value)

def dict_cursor(cursor):
    description = cursor.description
    return [dict(zip([col[0] for col in description], row))
            for row in cursor.fetchall()]
