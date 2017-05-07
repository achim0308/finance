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
from .processTransaction2 import constructCompleteInfo2, gatherData, addHistoricalPerformance, addSegmentPerformance, calcInterest, match, updateSecurityValuation, updateAccountValuation, getReturns
from .forms import AccountForm, SecurityForm, TransactionForm, TransactionFormForSuperuser, HistValuationForm, AddInterestForm, AddInterestFormForSuperuser, InflationForm

@login_required
def index(request):
    account_list = Account.objects.order_by('name')
    
    security_list = Security.objects.order_by('kind','name')
    security_valuations = SecurityValuation.objects.filter(date__gte=timezone.now())
    
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
    for a in account_list:
        try:
            account_values[a.id] = AccountValuation.objects.filter(account_id=a).order_by('-date')[0].cur_value
        except:
            account_values[a.id] = Money(amount=0.0,currency='EUR')
    
    # add information about security values
    security_values = {}
    for s in security_list:
        try:
            amount = security_valuations.filter(security_id=s.id).aggregate(Sum('cur_value'))['cur_value__sum']
            security_values[s.id] =  Money(
                amount=amount,
                currency=Security.objects.get(pk=s.id).currency
            )
        except:
            security_values[s.id] = Money(amount=0.0,currency='EUR')
    
    info = {'account_list': account_list, 
            'account_values': account_values,
            'security_list': security_list, 
            'security_values': security_values,
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
        data['transaction_list'] = Transaction.thobjects2.transactionHistory()
    else:
        cur_user = request.user.id
        valuation = valuation.filter(owner_id=cur_user)
        data['transaction_list'] = Transaction.thobjects2.transactionHistory(owner=cur_user)
    
    data['inflation'] = Inflation.objects.rateOfInflation()    

    data['histPerf'] = valuation.getHistoricalRateOfReturn()
    data['histPerf'].update(Inflation.objects.getHistoricalRateOfInflation())

    data['returns'] = data['histPerf']['rInfY']
    data['total'] = data['histPerf']['tInfY']

    # need to calculate information sector specific
    data['segPerf'] = {}
    total = 0
    for kind in Security.SEC_KIND_CHOICES:
        securities = Security.objects.kinds([kind[0]])
        valuation = SecurityValuation.objects.filter(security__in=securities)
        data['segPerf'][kind[0]] = valuation.getHistoricalRateOfReturn()
        total = total + float(data['segPerf'][kind[0]]['tYTD'].amount)

    for kind in Security.SEC_KIND_CHOICES:
        data['segPerf'][kind[0]]['frac'] = float(data['segPerf'][kind[0]]['tYTD'].amount) / total * 100.0

    # need to add function for charts

    # Prepare data for pie chart
    listOfAssets = []
    xdata = []
    for kind in Security.SEC_KIND_CHOICES:
        listOfAssets.append(kind[0])
        xdata.append(kind[1])
    ydata = [float(data['segPerf'][s]['tYTD'].amount) for s in listOfAssets]
    
    chartdata = {'x': xdata, 'y1': ydata}
    charttype = 'pieChart'
    chartcontainer = 'asset_allocation'

    data['chart_asset_alloc'] = {
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

    # prepare data for bar chart
    catdata = xdata
    xdata = ["YTD", "1 Yr", "5 Yrs", "Overall"]
    listOfTimes = ["rYTD", "r1Y", "r5Y", "rInfY"]
    
    ydata = {}
    for s in listOfAssets:
        ydata[s] = [data['segPerf'][s][t] for t in listOfTimes]

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
    data['chart_asset_perf'] = {
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
    
    return render(request, 'returns/all_accounts.html', data)

@login_required
def account(request, account_id):
    account = get_object_or_404(Account, pk=account_id)
    valuation = AccountValuation.objects.filter(account_id=account_id)

    data = {}
    data['account'] = account
    data['inflation'] = Inflation.objects.rateOfInflation()
    data['transaction_list'] = Transaction.thobjects2.transactionHistory(accounts=[account_id])

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
        data['transaction_list'] = Transaction.thobjects2.transactionHistory(securities=[security.id])
    else:
        cur_user = request.user.id
        valuation = valuation.filter(owner_id=cur_user)
        data['transaction_list'] = Transaction.thobjects2.transactionHistory(securities=[security.id], owner=cur_user)

    data['histPerf'] = valuation.getHistoricalRateOfReturn()
    data['histPerf'].update(Inflation.objects.getHistoricalRateOfInflation())

    data['cur_num'] = valuation.order_by('date').last().sum_num.normalize
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
            {'accounts': Account.objects.all().order_by('name'), 'securities': Security.objects.all().order_by('name'), 'kinds': sorted(Security.SEC_KIND_CHOICES, key=lambda tup:tup[1])})
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
        # do calculations

        begin_date = datetime.strptime(begin_date, "%m/%d/%Y").date()
        end_date = datetime.strptime(end_date, "%m/%d/%Y").date()
        if request.user.is_superuser:
            info = gatherData(accounts=selected_account, securities=selected_security,
                              kind=selected_kind, beginDate = begin_date,
                              endDate = end_date)
        else:
            info = gatherData(accounts=selected_account, securities=selected_security,
                              kind=selected_kind, beginDate = begin_date,
                              endDate = end_date, owner = request.user.id)
        
        return render(request, 'returns/select2.html', info)

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
                matched_transaction = match(transaction, request.POST['match'])
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
            currency = Security.objects.get(pk=transaction.security.id).currency
            t, created = Transaction.objects.update_or_create(
                    date = transaction.date,
                    security_id = transaction.security.id,
                    account_id = transaction.account.id,
                    kind = Transaction.INTEREST,
                    defaults = {
                        'cashflow': calcInterest(transaction.security.id, 
                                                 transaction.date),
                        'tax': Money(amount=0.0,currency=currency),
                        'expense': Money(amount=0.0,currency=currency),
                        'num_transacted': 0.0,
                        'modifiedDate': timezone.now().date(),
                        'owner': Account.objects.get(pk=transaction.account.id).owner
                    },
                )
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
    return redirect('returns:index')

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
