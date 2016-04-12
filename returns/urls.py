from django.conf.urls import url

from . import views

app_name = 'returns'
urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^all_accounts/$', views.all_accounts, name='all_accounts'),
    url(r'^transaction/(?P<transaction_id>[0-9]+)/$', views.transaction, name='transaction'),
    url(r'^transaction/new/$', views.transaction_new, name='transaction_new'),
    url(r'^transaction/(?P<transaction_id>[0-9]+)/edit/$', views.transaction_edit, name='transaction_edit'),
    url(r'^account/(?P<account_id>[0-9]+)/$', views.account, name='account'),
    url(r'^account/new/$', views.account_new, name='account_new'),
    url(r'^account/(?P<account_id>[0-9]+)/edit$', views.account_edit, name='account_edit'),
    url(r'^security/(?P<security_id>[0-9]+)/$', views.security, name='security'),
    url(r'^security/new/$', views.security_new, name='security_new'),
    url(r'^security/(?P<security_id>[0-9]+)/edit$', views.security_edit, name='security_edit'), 
    url(r'^timeperiod/$', views.timeperiod, name='timeperiod'),
    url(r'^add_interest/(?P<security_id>[0-9]+)$', views.add_interest, name='add_interest'), 
    url(r'^add_hist_data/$', views.add_hist_data, name='add_hist_data'),
]
