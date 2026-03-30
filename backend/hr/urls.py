from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'departments', views.DepartmentViewSet)
router.register(r'employees', views.EmployeeViewSet)
router.register(r'leave-types', views.LeaveTypeViewSet)
router.register(r'leave-balances', views.LeaveBalanceViewSet)
router.register(r'leave-requests', views.LeaveRequestViewSet)
router.register(r'attendance', views.AttendanceViewSet)
router.register(r'payroll-periods', views.PayrollPeriodViewSet)
router.register(r'pay-slips', views.PaySlipViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
