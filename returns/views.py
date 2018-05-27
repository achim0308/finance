from datetime import datetime, date, timedelta
from time import mktime

from django.shortcuts import render, get_object_or_404, redirect, render_to_response
from django.template import RequestContext
#from django.http import HttpResponse, Http404
from django.utils import timezone

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from django.db.models import Sum

from moneyed import Money, get_currency

from .models import Transaction, Account, Security, Inflation, SecurityValuation, AccountValuation
from .processTransaction2 import updateSecurityValuation, updateAccountValuation, makeBarChartSegPerf, makePieChartSegPerf
from .forms import AccountForm, SecurityForm, TransactionForm, TransactionFormForSuperuser, HistValuationForm, AddInterestForm, AddInterestFormForSuperuser, InflationForm
from .utilities import yearsago, last_day_of_month


@login_required
def index(request):
    account_list = Account.objects.order_by('name')
    
    security_list = Security.objects.order_by('kind','name')
    security_valuations = SecurityValuation.objects.mostRecent()
    
    transaction_list = Transaction.thobjects2.recent()
    
    # restrict to data for current user
    if not request.user.is_superuser:
        curUser = request.user.id
        # Get list of accounts of that have transactions for the current user
        account_list = account_list.accountOwnedBy(curUser)
        
        # Get list of securities that have transactions for the current user
        security_list = security_list.securityOwnedBy(curUser)
        security_valuations = security_valuations.filter(owner=curUser)
        transaction_list = transaction_list.owner(curUser)
    
    # add information about account values
    account_values = {}
    account_delta = {}
    account_delta_amount = {}
    account_inactive = {}
    for a in account_list:
        try:
            account_values[a.id] = AccountValuation.objects.filter(account_id=a.id).order_by('-date')[0].cur_value
        except:
            account_values[a.id] = Money(amount=0.0,currency=a.currency)
        if account_values[a.id].amount == 0:
            account_inactive[a.id] = True
            try:
                account_delta[a.id] = -AccountValuation.objects.filter(account_id=a.id).order_by('-date')[0].base_value
            except:
                account_delta[a.id] = Money(amount=0.0,currency=a.currency)
        else:
            account_inactive[a.id] = False
            account_delta[a.id] = account_values[a.id] - AccountValuation.objects.filter(account_id=a.id).order_by('-date')[0].base_value
        account_delta_amount[a.id] = account_delta[a.id].amount
    account_total = sum(account_values[a.id] for a in account_list)
    account_total_delta = sum(account_delta[a.id] for a in account_list)
    
    # add information about security values
    security_values = {}
    security_delta = {}
    security_inactive = {}
    for s in security_list:
        try:
            amount = security_valuations.filter(security_id=s.id).aggregate(Sum('cur_value'))['cur_value__sum']
            security_values[s.id] =  Money(
                amount = amount,
                currency = s.currency
            )
        except:
            security_values[s.id] = Money(amount=0.0,currency=s.currency)
        if security_values[s.id].amount == 0:
            security_inactive[s.id] = True
            try:
                security_delta[s.id] = Money(
                    amount = -security_valuations.filter(security_id=s.id).aggregate(Sum('base_value'))['base_value__sum'],
                    currency = s.currency
                )
            except:
                security_delta[s.id] = Money(amount=0.0,currency=s.currency)
        else:
            security_inactive[s.id] = False
            amount = amount - security_valuations.filter(security_id=s.id).aggregate(Sum('base_value'))['base_value__sum']
            security_delta[s.id] =  Money(
                amount = amount,
                currency = s.currency
            )
        security_delta_amount = security_delta[s.id].amount
    
    info = {'account_list': account_list, 
            'account_values': account_values,
            'account_delta': account_delta,
            'account_delta_amount': account_delta_amount,
            'account_total': account_total,
            'account_total_delta': account_total_delta,
            'account_inactive': account_inactive,
            'security_list': security_list, 
            'security_values': security_values,
            'security_delta': security_delta,
            'security_delta_amount': security_delta_amount,
            'security_inactive': security_inactive,
            'transaction_list': transaction_list}
    return render(request, 'returns/index.html', info)

@login_required
def transaction(request, transaction_id):
    if request.user.is_superuser:
        transaction = get_object_or_404(Transaction, pk=transaction_id)
    else:
        transaction = get_object_or_404(Transaction, pk=transaction_id,
                                        owner=request.user.id)
    return render(request, 'returns/transaction.html', {'transaction': transaction})

@login_required
def all_accounts(request):
    valuation = SecurityValuation.objects.all()
    data = {}
    
    if request.user.is_superuser:
        data['transaction_list'] = Transaction.thobjects2.transactionHistoryWithRelated()
    else:
        cur_user = request.user.id
        valuation = valuation.filter(owner_id=cur_user)
        data['transaction_list'] = Transaction.thobjects2.transactionHistoryWithRelated(owner=cur_user)
    
    data['inflation'] = Inflation.objects.rateOfInflation()    

    data['histPerf'] = valuation.getHistoricalRateOfReturn()
    data['histPerf'].update(Inflation.objects.getHistoricalRateOfInflation())

    data['returns'] = data['histPerf']['rInfY']
    data['total'] = data['histPerf']['tInfY']

    # need to calculate information sector specific
    data['segPerf'] = {}
    total = 0
    try:
        for kind in Security.SEC_KIND_CHOICES:
            securities = Security.objects.kinds([kind[0]])
            valuation1 = valuation.filter(security__in=securities)
            data['segPerf'][kind[1]] = valuation1.getHistoricalRateOfReturn()
            # only store if there is a current value to store
            try:
                total = total + float(data['segPerf'][kind[1]]['tYTD'].amount)
            except:
                pass
            
        for kind in Security.SEC_KIND_CHOICES:
            try:
                data['segPerf'][kind[1]]['frac'] = float(data['segPerf'][kind[1]]['tYTD'].amount) / total * 100.0
            except:
                data['segPerf'][kind[1]] = 0
    
        # Prepare data for pie chart
        data['chart_asset_alloc'] = makePieChartSegPerf(data['segPerf'])
        
        # prepare data for bar chart
        data['chart_asset_perf'] = makeBarChartSegPerf(data['segPerf'])

    except:
        data['segPerf'] = None

    # prepare data for line chart
    data['chart_asset_history'] = valuation.makeChart()

    return render(request, 'returns/all_accounts.html', data)

@login_required
def account(request, account_id):
    account = get_object_or_404(Account, pk=account_id)
    valuation = AccountValuation.objects.filter(account_id=account_id)

    data = {}
    data['account'] = account
    data['inflation'] = Inflation.objects.rateOfInflation()
    data['transaction_list'] = Transaction.thobjects2.transactionHistoryWithRelated(accounts=[account_id])

    data['histPerf'] = valuation.getHistoricalRateOfReturn()
    data['histPerf'].update(Inflation.objects.getHistoricalRateOfInflation())
    
    data['returns'] = data['histPerf']['rInfY']
    data['total'] = data['histPerf']['tInfY']
        
    data['chart_asset_history'] = valuation.makeChart()

    return render(request, 'returns/account.html', data)

@login_required
def security(request, security_id):
    security = get_object_or_404(Security, pk=security_id)
    valuation = SecurityValuation.objects.filter(security_id=security_id)
    data = {}
    data['security'] = security
    data['inflation'] = Inflation.objects.rateOfInflation()
    
    if request.user.is_superuser:
        data['transaction_list'] = Transaction.thobjects2.transactionHistoryWithRelated(securities=[security.id])
    else:
        cur_user = request.user.id
        valuation = valuation.filter(owner_id=cur_user)
        data['transaction_list'] = Transaction.thobjects2.transactionHistoryWithRelated(securities=[security.id], owner=cur_user)

    data['histPerf'] = valuation.getHistoricalRateOfReturn()
    data['histPerf'].update(Inflation.objects.getHistoricalRateOfInflation())

    try:
        data['cur_num'] = valuation.order_by('date').last().sum_num.normalize
    except:
        pass
    data['returns'] = data['histPerf']['rInfY']
    data['total'] = data['histPerf']['tInfY']

    data['chart_asset_history'] = valuation.makeChart()
        
    return render(request, 'returns/security.html', data)

@login_required
def timeperiod(request):

    try:
        begin_date = request.GET['from']
        end_date = request.GET['to']
        selected_kind = request.GET.getlist('kind')
        if selected_kind == []:
            selected_kind = None
        selected_account = request.GET.getlist('account')
        if selected_account == []:
            selected_account = None
        selected_security = request.GET.getlist('security')
        if selected_security == []:
            selected_security = None
    except:
        if request.user.is_superuser:
            return render(request, 'returns/timeperiod.html',
                          {'accounts': Account.objects.all().order_by('name'),
                           'securities': Security.objects.all().order_by('name'),
                           'kinds': sorted(Security.SEC_KIND_CHOICES, key=lambda tup:tup[1])
                          })
        else:
            curUser = request.user.id
            # Get list of accounts that have transactions for the current user
            account_list = Account.objects.accountOwnedBy(curUser).order_by('name')
            # Get list of securities that have transactions for the current user
            security_list = Security.objects.securityOwnedBy(curUser).order_by('name')
            
            return render(request, 'returns/timeperiod.html', 
                          {'accounts': account_list, 'securities': security_list,
                           'kinds': sorted(Security.SEC_KIND_CHOICES,
                                           key=lambda tup:tup[1])
                          })
    else:
        data = {}
    
        # do calculations
        begin_date = datetime.strptime(begin_date, "%m/%d/%Y").date()
        end_date = datetime.strptime(end_date, "%m/%d/%Y").date()

        data['beginDate'] = begin_date
        data['endDate'] = end_date
        
        if selected_kind is not None:
            selected_security = Security.objects.kinds(selected_kind).order_by('kind')
            valuation = SecurityValuation.objects.filter(security_id__in=selected_security)
            data['selected_kinds'] = True
            data['security_list'] = selected_security
        elif selected_account is not None:
            valuation = AccountValuation.objects.filter(account_id__in=selected_account)
            data['selected_accounts'] = True
            data['account_list'] = Account.objects.filter(id__in=selected_account)
        elif selected_security is not None:
            valuation = SecurityValuation.objects.filter(security_id__in=selected_security)
            data['selected_securities'] = True
            data['security_list'] = Security.objects.filter(id__in=selected_security)
        else:
            return render(request, 'returns/select2.html', info)

        if request.user.is_superuser:
            data['transaction_list'] = Transaction.thobjects2\
                                                  .transactionHistoryWithRelated(beginDate = begin_date, endDate = end_date,
                                                                                 securities = selected_security,
                                                                                 accounts = selected_account)
        else:
            cur_user = request.user.id
            if selected_account is None: 
                valuation = valuation.filter(owner=cur_user)
            data['transaction_list'] = Transaction.thobjects2\
                                                  .transactionHistoryWithRelated(beginDate = begin_date, endDate = end_date,
                                                                                 securities = selected_security,
                                                                                 accounts = selected_account,
                                                                                 owner=cur_user)
    
        data['inflation'] = Inflation.objects.rateOfInflation(beginDate = begin_date, endDate = end_date)

        rateOfReturn = valuation.getRateOfReturn(beginDate = begin_date, endDate = end_date)
        
        data['returns'] = rateOfReturn['rate']
        data['total'] = rateOfReturn['final']

        # prepare data for line chart
        data['chart_asset_history'] = valuation.makeChart()

        return render(request, 'returns/select2.html', data)

@login_required
def transaction_new(request):
    if request.method == "POST":
        if request.user.is_superuser:
            form = TransactionFormForSuperuser(request.POST)
        else:
            form = TransactionForm(request.user,request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            if not request.user.is_superuser:
                transaction.owner = request.user
            transaction.modifiedDate = timezone.now()
            transaction.save()

            if float(request.POST['match']) > 0:
                matched_transaction = transaction.match(request.POST['match'])
                matched_transaction.save()
            # return redirect('returns:transaction', transaction_id=transaction.id)
            return redirect('returns:transaction_new')
    else:
        if request.user.is_superuser:
            form = TransactionFormForSuperuser()
        else:
            form = TransactionForm(request.user)

    return render(request, 'returns/transaction_edit.html', {'form': form})

@login_required
def transaction_edit(request, transaction_id):
    transaction = get_object_or_404(Transaction, pk=transaction_id)
    if request.method == "POST":
        if request.user.is_superuser:
            form = TransactionFormTransactionFormForSuperuser(request.POST, instance=transaction)
        else:
            form = TransactionForm(request.user, request.POST, instance=transaction)
        if form.is_valid():
            transaction = form.save(commit=False)
            if not request.user.is_superuser:
                transaction.owner = request.user
            transaction.modifiedDate = timezone.now()
            transaction.save()
            return redirect('returns:transaction', transaction_id=transaction.id)
    else:
        form = TransactionForm(request.user, instance=transaction)
    return render(request, 'returns/transaction_edit.html', {'form': form})

@login_required
def account_new(request):
    if request.method == "POST":
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save()
            return redirect('returns:account', account_id=account.id)
    else:
        form = AccountForm()
    return render(request, 'returns/account_edit.html', {'form': form})

@login_required
def account_edit(request, account_id):
    account = get_object_or_404(Account, pk=account_id)
    if request.method == "POST":
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            account = form.save()
            return redirect('returns:account', account_id=account.id)
    else:
        form = AccountForm(instance=account)
    return render(request, 'returns/account_edit.html', {'form': form})

@login_required
def security_new(request):
    if request.method == "POST":
        form = SecurityForm(request.POST)
        if form.is_valid():
            security = form.save()
            return redirect('returns:security', security_id=security.id)
    else:
        form = SecurityForm()
    return render(request, 'returns/security_edit.html', {'form': form})

@login_required
def security_edit(request, security_id):
    security = get_object_or_404(Security, pk=security_id)
    if request.method == "POST":
        form = SecurityForm(request.POST, instance=security)
        if form.is_valid():
            security = form.save()
            return redirect('returns:security', security_id=security.id)
    else:
        form = SecurityForm(instance=security)
    return render(request, 'returns/security_edit.html', {'form': form})

@login_required
def add_interest(request, security_id):
    security = get_object_or_404(Security, pk=security_id)
    if request.method == "POST":
        if request.user.is_superuser:
            form = AddInterestFormForSuperuser(request.POST)
        else:
            form = AddInterestForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            currency = security.currency
            owner = Account.objects.get(pk=transaction.account.id).owner
            t, created = Transaction.objects.update_or_create(
                    date = transaction.date,
                    security_id = transaction.security.id,
                    account_id = transaction.account.id,
                    kind = Transaction.INTEREST,
                    defaults = {
                        'cashflow': security.calcInterest(transaction.date, owner),
                        'tax': Money(amount=0.0,currency=currency),
                        'expense': Money(amount=0.0,currency=currency),
                        'num_transacted': 0.0,
                        'modifiedDate': timezone.now().date(),
                        'owner': owner
                    },
                )

            # update security valuations 
            updateSecurityValuation(owner)
            return redirect('returns:transaction', transaction_id=t.id)
    else:
        today = timezone.now().date()
        Jan1 = date(today.year,1,1)
    
        if request.user.is_superuser:
            form = AddInterestFormForSuperuser(initial={'security':security_id,
                                                        'date': Jan1})
        else:
            form = AddInterestForm(initial={'security':security_id, 'date': Jan1})
    return render(request, 'returns/add_interest.html', {'form': form})

def add_hist_data(request):
    # all tasks for cron job
    # get current quote
    Security.objects.saveCurrentMarkToMarketValue()
    # update security and account valuations
    for u in User.objects.all():
        updateSecurityValuation(u)
    updateAccountValuation()

    return render(request, 'returns/add_hist_data.html')   
#    return redirect('returns:index')

@login_required
def inflation(request, inflation_id):
    inflation = get_object_or_404(Inflation, pk=inflation_id)
    return render(request, 'returns/inflation.html', {'inflation': inflation})

@login_required
def inflation_latest(request):
    return inflation(request, Inflation.objects.order_by('-id')[:1])

@login_required
def inflation_new(request):
    if request.method == "POST":
        form = InflationForm(request.POST)
        if form.is_valid():
            inflation = form.save()
            return redirect('returns:inflation', inflation_id=inflation.id)
    else:
        form = InflationForm()
    return render(request, 'returns/inflation_edit.html', {'form': form})

@login_required
def inflation_edit(request, inflation_id):
    security = get_object_or_404(Inflation, pk=inflation_id)
    if request.method == "POST":
        form = InflationForm(request.POST, instance=inflation)
        if form.is_valid():
            inflation = form.save()
            return redirect('returns:security', inflation_id=inflation.id)
    else:
        form = InflationForm(instance=inflation)
    return render(request, 'returns/inflation_edit.html', {'form': form})

def handler404(request):
    response = render_to_response('404.html', {},
                                  context_instance=RequestContext(request))
    response.status_code = 404
    return response


def handler500(request):
    response = render_to_response('500.html', {},
                                  context_instance=RequestContext(request))
    response.status_code = 500
    return response
