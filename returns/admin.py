from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from import_export import resources

from .models import Transaction, Account, Security, HistValuation, Inflation, SecurityValuation, AccountValuation

class TransactionResource(resources.ModelResource):
    class Meta:
        model = Transaction

class TransactionAdmin(ImportExportModelAdmin):
    resource_class = TransactionResource
    pass

admin.site.register(Transaction, TransactionAdmin)

class AccountResource(resources.ModelResource):
    class Meta:
        model = Account

class AccountAdmin(ImportExportModelAdmin):
    resource_class = AccountResource
    pass

admin.site.register(Account, AccountAdmin)

class SecurityResource(resources.ModelResource):
    class Meta:
        model = Security

class SecurityAdmin(ImportExportModelAdmin):
    resource_class = SecurityResource
    pass

admin.site.register(Security, SecurityAdmin)

class HistValuationResource(resources.ModelResource):
    class Meta:
        model = HistValuation

class HistValuationAdmin(ImportExportModelAdmin):
    resource_class = HistValuationResource
    pass

admin.site.register(HistValuation, HistValuationAdmin)

class InflationResource(resources.ModelResource):
    class Meta:
        model = Inflation

class InflationAdmin(ImportExportModelAdmin):
    resource_class = InflationResource
    pass

admin.site.register(Inflation, InflationAdmin)

class SecurityValuationResource(resources.ModelResource):
    class Meta:
        model = SecurityValuation

class SecurityValuationAdmin(ImportExportModelAdmin):
    resource_class = SecurityValuationResource
    pass

admin.site.register(SecurityValuation, SecurityValuationAdmin)

class AccountValuationResource(resources.ModelResource):
    class Meta:
        model = AccountValuation

class AccountValuationAdmin(ImportExportModelAdmin):
    resource_class = AccountValuationResource
    pass

admin.site.register(AccountValuation, SecurityValuationAdmin)