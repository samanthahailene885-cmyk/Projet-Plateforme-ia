from django.contrib import admin
from .models import DailyPlan, Task, TaskDocument


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'assigned_to', 'priority', 'status', 'due_date')
    list_filter = ('status', 'priority')
    search_fields = ('title', 'description')


@admin.register(TaskDocument)
class TaskDocumentAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'task', 'file_size', 'uploaded_by', 'created_at')


@admin.register(DailyPlan)
class DailyPlanAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'objective')
