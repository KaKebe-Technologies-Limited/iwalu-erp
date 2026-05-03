from rest_framework import serializers
from .models import Project, ProjectTask, ProjectExpense, ProjectTimeEntry


class ProjectSerializer(serializers.ModelSerializer):
    budget_remaining = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    is_over_budget = serializers.BooleanField(read_only=True)
    budget_utilisation_pct = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'project_number', 'name', 'description', 'status',
            'manager_id', 'start_date', 'end_date', 'budget', 'actual_cost',
            'budget_remaining', 'is_over_budget', 'budget_utilisation_pct',
            'approval_request', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['project_number', 'status', 'actual_cost', 'approval_request', 'created_at', 'updated_at']

    def validate(self, data):
        start = data.get('start_date', getattr(self.instance, 'start_date', None))
        end = data.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': 'End date cannot be before start date.'})
        return data


class ProjectTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectTask
        fields = [
            'id', 'project', 'title', 'description', 'assigned_to_id',
            'created_by_id', 'status', 'priority', 'due_date',
            'completed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by_id', 'completed_at', 'created_at', 'updated_at']

    def validate_project(self, value):
        if self.instance and self.instance.project_id != value.id:
            raise serializers.ValidationError("Cannot change the project of an existing task.")
        return value


class ProjectExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectExpense
        fields = [
            'id', 'project', 'description', 'category', 'amount',
            'expense_date', 'incurred_by_id', 'approved_by_id',
            'receipt_number', 'journal_entry_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['incurred_by_id', 'approved_by_id', 'journal_entry_id', 'created_at', 'updated_at']

    def validate_project(self, value):
        if self.instance and self.instance.project_id != value.id:
            raise serializers.ValidationError("Cannot change the project of an existing expense.")
        return value


class ProjectTimeEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectTimeEntry
        fields = [
            'id', 'project', 'task', 'staff_id', 'date',
            'hours', 'description', 'created_at'
        ]
        read_only_fields = ['staff_id', 'created_at']
        extra_kwargs = {'task': {'required': False}}

    def validate_project(self, value):
        if self.instance and self.instance.project_id != value.id:
            raise serializers.ValidationError("Cannot change the project of an existing time entry.")
        return value
