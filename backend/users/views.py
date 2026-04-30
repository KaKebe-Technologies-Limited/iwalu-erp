import logging
from django.db import connection, transaction
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, authentication_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, UserInvitation
from .serializers import (
    UserSerializer, UserCreateSerializer, RegisterSerializer,
    InviteUserSerializer, AcceptInviteSerializer, UserInvitationSerializer,
)
from .permissions import IsAdmin, IsAdminOrManager
from .role_permissions import get_permissions_for_role
from .email import send_invitation_email

logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrManager()]
        if self.action in ('activate', 'deactivate'):
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            return Response(
                {'error': 'You cannot deactivate yourself.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response({'status': 'User deactivated.'})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=['is_active'])
        return Response({'status': 'User activated.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_permissions(request):
    """
    Return the dashboard sections and fine-grained actions the current
    user's role is allowed to access. The frontend uses this to build
    the sidebar and feature gates dynamically.
    """
    return Response(get_permissions_for_role(request.user.role))


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    refresh = RefreshToken.for_user(user)
    return Response({
        'user': UserSerializer(user).data,
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAdminOrManager])
def invite_user(request):
    """
    Invite a new staff member by email. The invite is scoped to the current
    tenant (captured from the subdomain context). Role cannot be admin — admins
    are created only via tenant registration.
    """
    serializer = InviteUserSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    if data['role'] == 'admin':
        return Response(
            {'error': 'Cannot invite users with the admin role.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(email__iexact=data['email']).exists():
        return Response(
            {'error': 'A user with this email already exists.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tenant_schema = connection.schema_name
    expires_at = timezone.now() + timedelta(hours=48)

    invitation, created = UserInvitation.objects.update_or_create(
        email=data['email'],
        tenant_schema=tenant_schema,
        defaults={
            'role': data['role'],
            'invited_by_id': request.user.pk,
            'expires_at': expires_at,
            'accepted_at': None,
        },
    )

    try:
        send_invitation_email(invitation, request)
    except Exception:
        logger.exception('Failed to send invitation email to %s', data['email'])

    return Response(
        UserInvitationSerializer(invitation).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def list_invitations(request):
    """List all invitations for the current tenant."""
    tenant_schema = connection.schema_name
    invitations = UserInvitation.objects.filter(tenant_schema=tenant_schema)
    return Response(UserInvitationSerializer(invitations, many=True).data)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def accept_invite(request):
    """
    Accept an email invitation and create the user account.
    Must be called from the tenant's subdomain — the token's tenant_schema
    is verified against the current connection schema.
    """
    serializer = AcceptInviteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        invitation = UserInvitation.objects.get(token=data['token'])
    except UserInvitation.DoesNotExist:
        return Response({'error': 'Invalid invitation token.'}, status=status.HTTP_400_BAD_REQUEST)

    if invitation.tenant_schema != connection.schema_name:
        return Response({'error': 'Invalid invitation token.'}, status=status.HTTP_400_BAD_REQUEST)

    if invitation.is_expired:
        return Response(
            {'error': 'This invitation has expired. Ask an admin to resend it.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if invitation.is_accepted:
        return Response(
            {'error': 'This invitation has already been used.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(email__iexact=invitation.email).exists():
        return Response(
            {'error': 'A user with this email already exists.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        user = User.objects.create(
            email=invitation.email,
            username=data['username'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            phone_number=data.get('phone_number', ''),
            role=invitation.role,
            is_active=True,
        )
        user.set_password(data['password'])
        user.save()

        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=['accepted_at'])

    refresh = RefreshToken.for_user(user)
    return Response({
        'user': UserSerializer(user).data,
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }, status=status.HTTP_201_CREATED)
