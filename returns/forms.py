>0;256;0cfrom django import forms
from django.core.exceptions import ValidationError
from django_countries.widgets import CountrySelectWidget

from .models import Account, Security, Transaction, HistValuation, Inflation

class AccountForm(forms.ModelForm):

    class Meta:
        model = Account
        fields = ('name', 'owner', 'currency', 'active')

class SecurityForm(forms.ModelForm):

    def clean(self):
        if (self.cleaned_data.get('mark_to_market') == True and 
            self.cleaned_data.get('accumulate_interest') == True):
            self.add_error('mark_to_market', 
                           ValidationError("Security inconsistently labeled both mark to market and accumulates interest."))
        elif (self.cleaned_data.get('mark_to_market') == True and 
              self.cleaned_data.get('url') == ''):
            self.add_error('url',
                           ValidationError("Need url for a mark to market security to get current prices."))

        if (self.cleaned_data.get('kind') == Security.TAGESGELD and 
            self.cleaned_data.get('accumulates_interest') == False):
            self.add_error('kind',
                           ValidationError("Inconsistent selection. This security should accumulate interest."))

        if ((self.cleaned_data.get('kind') == Security.AKTIE or 
             self.cleaned_data.get('kind') == Security.AKTIENETF or 
#             self.cleaned_data.get('kind') == Security.BONDS or 
             self.cleaned_data.get('kind') == Security.BONDSETF)
             and self.cleaned_data.get('mark_to_market') == False):
            self.add_error('kind',
                           ValidationError("Inconsistent selection. This security should be marked to market."))

        if (self.cleaned_data.get('accumulate_interest') == False and 
            self.cleaned_data.get('calc_interest') != 0.0):
            self.add_error('calc_interest', 
                           ValidationError("Inconsistent. Fixed interest can only be used with a security that accumulates interest."))

        elif (self.cleaned_data.get('accumulate_interest') == True and 
            self.cleaned_data.get('calc_interest') < 0.0):
            self.add_error('calc_interest', 
                           ValidationError("Inconsistent. Fixed interest should be positive."))

        elif (self.cleaned_data.get('accumulate_interest') == True and 
            self.cleaned_data.get('calc_interest') > 0.0 and 
            self.cleaned_data.get('kind') != Security.ALTERSVORSORGE):
            self.add_error('kind', 
                           ValidationError("Inconsistent. Fixed interest can only be used with Altersvorsorge."))

        return self.cleaned_data

    class Meta:
        model = Security
        fields = ('name', 'descrip', 'kind', 'symbol', 'url', 'mark_to_market', 'accumulate_interest', 'calc_interest', 'currency', 'active',)

class TransactionForm(forms.ModelForm):
    def __init__(self,owner,*args,**kwargs):
        super (TransactionForm,self ).__init__(*args,**kwargs) # populates the form
        self.fields['account'].queryset = Account.objects.filter(owner=owner).active()
        self.fields['security'].queryset = Security.objects.active()
        
    def clean(self):
        if (self.cleaned_data.get('kind') == Transaction.BUY):
            if self.cleaned_data.get('cashflow').amount > 0.0:
                self.add_error('cashflow',
                               ValidationError("Cashflow must be negative."))
            if self.cleaned_data.get('num_transacted') < 0.0:
                self.add_error('num_transacted',
                               ValidationError("Number of exchanged securities must be positive."))
        elif (self.cleaned_data.get('kind') == Transaction.SELL):
            if self.cleaned_data.get('cashflow').amount < 0.0:
                self.add_error('cashflow',
                               ValidationError("Cashflow must be positive."))
            if self.cleaned_data.get('num_transacted') > 0.0:
                self.add_error('num_transacted',
                               ValidationError("Number of exchanged securities must be negative."))
        elif (self.cleaned_data.get('kind') == Transaction.INTEREST or 
              self.cleaned_data.get('kind') == Transaction.DIVIDEND):
            if self.cleaned_data.get('cashflow').amount < 0.0:
                self.add_error('cashflow', ValidationError("Cashflow must be positive."))
            if self.cleaned_data.get('num_transacted') != 0.0:
                self.add_error('num_transacted', ValidationError("Number of exchanged securities must be zero."))
        elif (self.cleaned_data.get('kind') == Transaction.INTEREST or 
              self.cleaned_data.get('kind') == Transaction.DIVIDEND or
              self.cleaned_data.get('kind') == Transaction.MATCH):
            if self.cleaned_data.get('cashflow').amount != 0.0:
                self.add_error('cashflow', ValidationError("Cashflow must be zero."))
            if self.cleaned_data.get('num_transacted') < 0.0:
                self.add_error('num_transacted', ValidationError("Number of exchanged securities must be non-negative."))
        elif (self.cleaned_data.get('kind') == Transaction.WRITE_DOWN):
            if self.cleaned_data.get('cashflow').amount <= 0.0:
                self.add_error('cashflow', ValidationError("Cashflow must be positive."))
            if self.cleaned_data.get('security').mark_to_market == True:
                self.add_error('security', ValidationError("Cannot write down mark_to_market security"))
        if (self.cleaned_data.get('expense').amount > 0.0):
            self.add_error('expense',
                           ValidationError("Expenses must be non-positive."))
        if (self.cleaned_data.get('tax').amount > 0.0):
            self.add_error('tax', 
                           ValidationError("Taxes must be non-positive."))

        return self.cleaned_data

    class Meta:
        model = Transaction
        fields = ('date', 'kind', 'security', 'cashflow', 'expense', 'tax', 'account', 'num_transacted',)
        widgets = {'date': forms.DateInput(attrs={'class':'datepicker'}),}

class TransactionFormForSuperuser(TransactionForm):
    def __init__(self,*args,**kwargs):
        super (TransactionForm,self ).__init__(*args,**kwargs) # populates the form

    class Meta:
        model = Transaction
        fields = ('date', 'kind', 'security', 'cashflow', 'expense', 'tax', 'account', 'num_transacted', 'owner',)
        widgets = {'date': forms.DateInput(attrs={'class':'datepicker'}),}
        
class HistValuationForm(forms.ModelForm):

    class Meta:
        model = HistValuation
        fields = ('date','security', 'value',)
        widgets = {'date': forms.DateInput(attrs={'class':'datepicker'}),}

class AddInterestForm(forms.ModelForm):
    
    class Meta:
        model = Transaction
        fields = ('date', 'security', 'account',)
        widgets = {'date': forms.DateInput(attrs={'class':'datepicker'}),}

class AddInterestFormForSuperuser(forms.ModelForm):
    
    class Meta:
        model = Transaction
        fields = ('date', 'security', 'account', 'owner',)
        widgets = {'date': forms.DateInput(attrs={'class':'datepicker'}),}

class InflationForm(forms.ModelForm):
    
    class Meta:
        model = Inflation
        fields = ('date', 'inflationIndex', 'country',)
        widgets = {'date': forms.DateInput(attrs={'class':'datepicker'}),
                   'country': CountrySelectWidget()}
