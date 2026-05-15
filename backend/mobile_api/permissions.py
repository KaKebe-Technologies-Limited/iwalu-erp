from rest_framework.permissions import BasePermission


def _get_token_payload(request):
    """
    Safely extract the payload dict from a SimpleJWT AccessToken.
    Returns an empty dict if request.auth is absent or not a JWT.
    """
    auth = request.auth
    if auth is None:
        return {}
    payload = getattr(auth, 'payload', None)
    if payload is None:
        return {}
    return dict(payload)


class IsMobileClient(BasePermission):
    """
    Allows access only when the JWT was issued by MobileTokenObtainPairView,
    i.e. payload['client'] == 'mobile'.
    """
    message = "This endpoint requires a mobile-issued JWT."

    def has_permission(self, request, view):
        payload = _get_token_payload(request)
        return payload.get('client') == 'mobile'


class IsNotMobileClient(BasePermission):
    """
    Blocks access when the JWT was issued by MobileTokenObtainPairView.
    Use on sensitive endpoints (finance, HR, payroll, assets, user admin)
    to prevent a stolen mobile token from reaching privileged data.
    """
    message = "Mobile tokens are not permitted on this endpoint."

    def has_permission(self, request, view):
        payload = _get_token_payload(request)
        return payload.get('client') != 'mobile'
