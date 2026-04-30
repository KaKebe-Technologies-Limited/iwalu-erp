from rest_framework import serializers
from .models import ApprovalPolicy, ApprovalRequest, ApprovalAction
from users.models import User

class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'role']

class ApprovalPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalPolicy
        fields = '__all__'

    def validate_approval_levels(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("approval_levels must be a list")
        for level in value:
            if not all(k in level for k in ('level', 'role', 'min_approvers')):
                raise serializers.ValidationError(
                    "Each level must contain 'level', 'role', and 'min_approvers'"
                )
        return value

class ApprovalActionSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalAction
        fields = '__all__'
        read_only_fields = ['actor_id', 'level', 'created_at']

    def get_actor_name(self, obj):
        try:
            user = User.objects.get(id=obj.actor_id)
            return user.get_full_name() or user.username
        except User.DoesNotExist:
            return f"User #{obj.actor_id}"

class ApprovalRequestSerializer(serializers.ModelSerializer):
    actions = ApprovalActionSerializer(many=True, read_only=True)
    requested_by_name = serializers.SerializerMethodField()
    pending_level_details = serializers.SerializerMethodField()
    resource_display = serializers.CharField(source='get_resource_type_display', read_only=True)

    class Meta:
        model = ApprovalRequest
        fields = '__all__'
        read_only_fields = ['status', 'resolved_at', 'approval_chain_state', 'requested_at']

    def get_requested_by_name(self, obj):
        try:
            user = User.objects.get(id=obj.requested_by_id)
            return user.get_full_name() or user.username
        except User.DoesNotExist:
            return f"User #{obj.requested_by_id}"

    def get_pending_level_details(self, obj):
        level = obj.pending_level
        if level is None:
            return None
        
        level_data = next((l for l in obj.approval_chain_state if l['level'] == level), None)
        if not level_data:
            return None

        # Get names of potential approvers
        approver_ids = obj.get_approvers_at_level(level)
        approvers = User.objects.filter(id__in=approver_ids)
        pending_from = [u.get_full_name() or u.username for u in approvers]

        return {
            "level": level,
            "role": level_data.get('role'),
            "description": level_data.get('description', ''),
            "min_approvers": level_data.get('min_approvers', 1),
            "approved_count": level_data.get('approved_count', 0),
            "pending_from": pending_from
        }
