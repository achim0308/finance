from django.urls import re_path

from . import views

app_name = 'returns'
urlpatterns = [
    re_path(r'^$', views.index, name='index'),
    re_path(r'^all_accounts/$', views.all_accounts, name='all_accounts'),
    re_path(r'^transaction/(?P<transaction_id>[0-9]+)/$', views.transaction, name='transaction'),
    re_path(r'^transaction/new/$', views.transaction_new, name='transaction_new'),
    re_path(r'^transaction/(?P<transaction_id>[0-9]+)/edit/$', views.transaction_edit, name='transaction_edit'),
    re_path(r'^account/(?P<account_id>[0-9]+)/$', views.account, name='account'),
    re_path(r'^account/new/$', views.account_new, name='account_new'),
    re_path(r'^account/(?P<account_id>[0-9]+)/edit$', views.account_edit, name='account_edit'),
    re_path(r'^security/(?P<security_id>[0-9]+)/$', views.security, name='security'),
    re_path(r'^security/new/$', views.security_new, name='security_new'),
    re_path(r'^security/(?P<security_id>[0-9]+)/edit$', views.security_edit, name='security_edit'), 
    re_path(r'^timeperiod/$', views.timeperiod, name='timeperiod'),
    re_path(r'^add_interest/(?P<security_id>[0-9]+)$', views.add_interest, name='add_interest'), 
    re_path(r'^add_hist_data/$', views.add_hist_data, name='add_hist_data'),
    re_path(r'^inflation/latest/$', views.inflation_latest, name='inflation_latest'),
    re_path(r'^inflation/new/$', views.inflation_new, name='inflation_new'),
    re_path(r'^inflation/(?P<inflation_id>[0-9]+)/$', views.inflation, name='inflation'),
    re_path(r'^inflation/(?P<inflation_id>[0-9]+)/edit$', views.inflation_edit, name='inflation_edit'),
]
