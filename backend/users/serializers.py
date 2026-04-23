from rest_framework import serializers
from .models import User, UserInvitation


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name',
                  'phone_number', 'role', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserCreateSerializer(serializers.ModelSerializer):
    """Used by admin/manager to create users with any role."""
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'first_name', 'last_name',
                  'phone_number', 'role']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user


class RegisterSerializer(serializers.ModelSerializer):
    """Public self-registration. Role is always the default (cashier)."""
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'first_name', 'last_name',
                  'phone_number']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user


class InviteUserSerializer(serializers.Serializer):
    """Issued by an admin/manager to invite a new staff member by email."""
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)

    def validate_email(self, value):
        return value.lower().strip()


class UserInvitationSerializer(serializers.ModelSerializer):
    """Read serializer for listing invitations."""
    is_pending = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserInvitation
        fields = ['id', 'email', 'role', 'is_pending', 'accepted_at', 'expires_at', 'created_at']
        read_only_fields = fields


class AcceptInviteSerializer(serializers.Serializer):
    """Submitted by the invitee to accept an invitation and create their account."""
    token = serializers.UUIDField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value
