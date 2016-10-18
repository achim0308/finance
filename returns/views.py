from datetime import datetime, date, timedelta

from django.shortcuts import render, get_object_or_404, redirect
#from django.http import HttpResponse, Http404
from django.utils import timezone

from django.contrib.auth.decorators import login_required

from .models import Transaction, Account, Security, Inflation
from .processTransaction2 import addNewMarkToMarketData, constructCompleteInfo2, gatherData, addHistoricalPerformance, addSegmentPerformance, calcInterest, match
from .forms import AccountForm, SecurityForm, TransactionForm, TransactionFormForSuperuser, HistValuationForm, AddInterestForm, AddInterestFormForSuperuser, InflationForm

@login_required
def index(request):
    if request.user.is_superuser:
        account_list = Account.objects.order_by('name')
        security_list = Security.objects.order_by('name')
        latest_transaction_list = Transaction.objects.filter(date__gt=timezone.now()+timedelta(days=-30)).order_by('-date')
    else:
        cur_user = request.user
        # Get list of accounts of that have transactions for the current user
        pk_accounts = Transaction.objects.filter(owner=cur_user.id).values_list('account', flat=True)
        account_list = Account.objects.filter(pk__in=pk_accounts).order_by('name')
        
        # Get list of securities that have transactions for the current user
        pk_securities = Transaction.objects.filter(owner=cur_user.id).values_list('security', flat=True)
        security_list = Security.objects.filter(pk__in=pk_securities).order_by('name')

        latest_transaction_list = Transaction.objects.filter(date__gt=timezone.now()+timedelta(days=-30), owner=cur_user.id).order_by('-date')
    
    info = {'account_list': account_list, 
            'security_list': security_list, 
            'latest_transaction_list': latest_transaction_list}
    return render(request, 'returns/index.html', info)

@login_required
def transaction(request, transaction_id):
    if request.user.is_superuser:
        transaction = get_object_or_404(Transaction, pk=transaction_id)
    else:
        transaction = get_object_or_404(Transaction, pk=transaction_id, owner=request.user.id)
    return render(request, 'returns/transaction.html', {'transaction': transaction})

@login_required
def all_accounts(request):
    if request.user.is_superuser:
        info = gatherData()
        info['histPerf'] = addHistoricalPerformance()
        info['segPerf'] = addSegmentPerformance()
    else:
        cur_user = request.user.id
        info = gatherData(owner = cur_user)
        info['histPerf'] = addHistoricalPerformance(owner = cur_user)
        info['segPerf'] = addSegmentPerformance(owner = cur_user)
    return render(request, 'returns/all_accounts.html', info)

@login_required
def account(request, account_id):
    account = get_object_or_404(Account, pk=account_id)
    
    if request.user.is_superuser:
        info = gatherData(accounts = [account_id])
        info['histPerf'] = addHistoricalPerformance(accounts = [account_id])
    else:
        cur_user = request.user.id
        info = gatherData(accounts = [account_id], owner = cur_user)
        info['histPerf'] = addHistoricalPerformance(accounts = [account_id], owner = cur_user)
 
    info['account'] = account

    return render(request, 'returns/account.html', info)

@login_required
def security(request, security_id):
    security = get_object_or_404(Security, pk=security_id)

    if request.user.is_superuser:
        info = gatherData(securities = [security_id])
        info['histPerf'] = addHistoricalPerformance(securities = [security_id])
    else:
        cur_user = request.user.id
        info = gatherData(securities = [security_id], owner = cur_user)
        info['histPerf'] = addHistoricalPerformance(securities = [security_id], owner = cur_user)
    info['security'] = security

    return render(request, 'returns/security.html', info)

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
            return render(request, 'returns/timeperiod.html', {'accounts': Account.objects.all().order_by('name'), 'securities': Security.objects.all().order_by('name'), 'kinds': sorted(Security.SEC_KIND_CHOICES, key=lambda tup:tup[1])})
        else:
            cur_user = request.user
            # Get list of accounts that have transactions for the current user
            pk_accounts = Transaction.objects.filter(owner=cur_user.id).values_list('account', flat=True)
            account_list = Account.objects.filter(pk__in=pk_accounts).order_by('name')
        
            # Get list of securities that have transactions for the current user
            pk_securities = Transaction.objects.filter(owner=cur_user.id).values_list('security', flat=True)
            security_list = Security.objects.filter(pk__in=pk_securities).order_by('name')

            return render(request, 'returns/timeperiod.html', {'accounts': account_list, 'securities': security_list, 'kinds': sorted(Security.SEC_KIND_CHOICES, key=lambda tup:tup[1])})
    else:
        # do calculations

        begin_date = datetime.strptime(begin_date, "%m/%d/%Y").date()
        end_date = datetime.strptime(end_date, "%m/%d/%Y").date()
        if request.user.is_superuser:
            info = gatherData(accounts=selected_account, securities=selected_security, kind=selected_kind, beginDate = begin_date, endDate = end_date)
        else:
            info = gatherData(accounts=selected_account, securities=selected_security, kind=selected_kind, beginDate = begin_date, endDate = end_date, owner = request.user.id)
        
        return render(request, 'returns/select2.html', info)

@login_required
def transaction_new(request):
    if request.method == "POST":
        if request.user.is_superuser:
            form = TransactionFormForSuperuser(request.POST)
        else:
            form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            if not request.user.is_superuser:
                transaction.owner = request.user
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
            form = TransactionForm()

    return render(request, 'returns/transaction_edit.html', {'form': form})

@login_required
def transaction_edit(request, transaction_id):
    transaction = get_object_or_404(Transaction, pk=transaction_id)
    if request.method == "POST":
        if request.user.is_superuser:
            form = TransactionFormTransactionFormForSuperuser(request.POST, instance=transaction)
        else:
            form = TransactionForm(request.POST, instance=transaction)
        if form.is_valid():
            transaction = form.save(commit=False)
            if not request.user.is_superuser:
                transaction.owner = request.user
            transaction.save()
            return redirect('returns:transaction', transaction_id=transaction.id)
    else:
        form = TransactionForm(instance=transaction)
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
            transaction.kind = Transaction.INTEREST
            transaction.cashflow = calcInterest(transaction.security.id,transaction.date)
            transaction.tax = 0.0
            transaction.expense = 0.0
            transaction.num_transacted = 0.0
            if not request.user.is_superuser:
                transaction.owner = request.user
            transaction.save()
            return redirect('returns:transaction', transaction_id=transaction.id)
    else:
        today = timezone.now().date()
        Jan1 = date(today.year,1,1)
    
        if request.user.is_superuser:
            form = AddInterestFormForSuperuser(initial={'security':security_id, 'date': Jan1})
        else:
            form = AddInterestForm(initial={'security':security_id, 'date': Jan1})
    return render(request, 'returns/add_interest.html', {'form': form})

def add_hist_data(request):
    addNewMarkToMarketData()
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
