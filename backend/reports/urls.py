from django.urls import path
from . import views

urlpatterns = [
    path('reports/sales-summary/', views.sales_summary, name='sales-summary'),
    path('reports/sales-by-outlet/', views.sales_by_outlet, name='sales-by-outlet'),
    path('reports/sales-by-product/', views.sales_by_product, name='sales-by-product'),
    path('reports/sales-by-payment-method/', views.sales_by_payment_method, name='sales-by-payment-method'),
    path('reports/hourly-sales/', views.hourly_sales, name='hourly-sales'),
    path('reports/stock-levels/', views.stock_levels, name='stock-levels'),
    path('reports/stock-movement/', views.stock_movement, name='stock-movement'),
    path('reports/shift-summary/', views.shift_summary, name='shift-summary'),
    path('reports/dashboard/', views.dashboard, name='reports-dashboard'),
]
