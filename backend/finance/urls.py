from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'accounts', views.AccountViewSet)
router.register(r'fiscal-periods', views.FiscalPeriodViewSet)
router.register(r'journal-entries', views.JournalEntryViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('finance/trial-balance/', views.trial_balance_view, name='trial-balance'),
    path('finance/profit-loss/', views.profit_loss_view, name='profit-loss'),
    path('finance/balance-sheet/', views.balance_sheet_view, name='balance-sheet'),
    path('finance/account-ledger/<int:pk>/', views.account_ledger_view, name='account-ledger'),
]
