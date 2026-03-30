from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Only admin users."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class IsAdminOrManager(BasePermission):
    """Admin or manager users."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in ('admin', 'manager')
        )


class IsCashierOrAbove(BasePermission):
    """Admin, manager, cashier, or attendant. Excludes accountant."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in ('admin', 'manager', 'cashier', 'attendant')
        )


class IsAccountant(BasePermission):
    """Accountant role only."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'accountant'


class IsAccountantOrAbove(BasePermission):
    """Admin, manager, or accountant."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in ('admin', 'manager', 'accountant')
        )
