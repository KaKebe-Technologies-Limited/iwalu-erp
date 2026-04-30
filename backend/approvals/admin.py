from django.contrib import admin
from .models import ApprovalPolicy, ApprovalRequest, ApprovalAction

@admin.register(ApprovalPolicy)
class ApprovalPolicyAdmin(admin.ModelAdmin):
    list_display = ('name', 'resource_type', 'min_amount', 'max_amount', 'is_active')
    list_filter = ('resource_type', 'is_active')
    search_fields = ('name', 'description')

class ApprovalActionInline(admin.TabularInline):
    model = ApprovalAction
    extra = 0
    readonly_fields = ('actor_id', 'level', 'action', 'comment', 'created_at')
    can_delete = False

@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'resource_type', 'resource_id', 'amount', 'status', 'requested_at')
    list_filter = ('resource_type', 'status')
    search_fields = ('resource_id', 'notes')
    inlines = [ApprovalActionInline]
    readonly_fields = ('approval_chain_state', 'requested_by_id', 'requested_at', 'resolved_at')

@admin.register(ApprovalAction)
class ApprovalActionAdmin(admin.ModelAdmin):
    list_display = ('approval_request', 'actor_id', 'level', 'action', 'created_at')
    list_filter = ('action', 'level')
    readonly_fields = ('approval_request', 'actor_id', 'level', 'action', 'comment', 'created_at')
