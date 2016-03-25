from django import forms
from django.core.exceptions import ValidationError

from .models import Account, Security, Transaction, HistValuation

class AccountForm(forms.ModelForm):

    class Meta:
        model = Account
        fields = ('name',)

class SecurityForm(forms.ModelForm):

    def clean(self):
        if (self.cleaned_data.get('mark_to_market') == True and self.cleaned_data.get('accumulate_interest') == True):
            self.add_error('mark_to_market', 
                           ValidationError("Security inconsistently labeled both mark to market and accumulates interest."))
        elif (self.cleaned_data.get('mark_to_market') == True and self.cleaned_data.get('url') == ''):
            self.add_error('url',
                           ValidationError("Need url for a mark to market security to get current prices."))
        if (self.cleaned_data.get('kind') == Security.TAGESGELD and self.cleaned_data.get('accumulates_interest') == False):
            self.add_error('kind',
                           ValidationError("Inconsistent selection. This security should accumulate interest."))
        if ((self.cleaned_data.get('kind') == Security.AKTIE or
             self.cleaned_data.get('kind') == Security.AKTIENETF or
             self.cleaned_data.get('kind') == Security.BONDS or
             self.cleaned_data.get('kind') == Security.BONDSETF)
             and self.cleaned_data.get('mark_to_market') == False):
            self.add_error('kind',
                           ValidationError("Inconsistent selection. This security should be marked to market."))
    class Meta:
        model = Security
        fields = ('name', 'descrip', 'url', 'kind', 'mark_to_market', 'accumulate_interest')

class TransactionForm(forms.ModelForm):

    def clean(self):
        if (self.cleaned_data.get('kind') == Transaction.BUY):
            if self.cleaned_data.get('cashflow') > 0.0:
                self.add_error('cashflow',
                               ValidationError("Cashflow must be negative."))
            if self.cleaned_data.get('num_transacted') < 0.0:
                self.add_error('num_transacted',
                               ValidationError("Number of exchanged securities must be positive."))
        elif (self.cleaned_data.get('kind') == Transaction.SELL):
            if self.cleaned_data.get('cashflow') < 0.0:
                self.add_error('cashflow',
                               ValidationError("Cashflow must be positive."))
            if self.cleaned_data.get('num_transacted') > 0.0:
                self.add_error('num_transacted',
                               ValidationError("Number of exchanged securities must be negative."))
        elif (self.cleaned_data.get('kind') == Transaction.INTEREST or 
              self.cleaned_data.get('kind') == Transaction.DIVIDEND):
            if self.cleaned_data.get('cashflow') < 0.0:
                self.add_error('cashflow', ValidationError("Cashflow must be positive."))
            if self.cleaned_data.get('num_transacted') != 0.0:
                self.add_error('num_transacted', ValidationError("Number of exchanged securities must be zero."))
        if (self.cleaned_data.get('expense') > 0.0):
            self.add_error('expense',
                           ValidationError("Expenses must be non-positive."))
        if (self.cleaned_data.get('tax') > 0.0):
            self.add_error('tax', 
                           ValidationError("Taxes must be non-positive."))

        return self.cleaned_data

    class Meta:
        model = Transaction
        fields = ('date', 'kind', 'security', 'cashflow', 'expense', 'tax', 'account', 'num_transacted',)
        widgets = {'date': forms.DateInput(attrs={'class':'datepicker'}),}
        
class HistValuationForm(forms.ModelForm):

    class Meta:
        model = HistValuation
        fields = ('date','security', 'value',)
        widgets = {'date': forms.DateInput(attrs={'class':'datepicker'}),}
