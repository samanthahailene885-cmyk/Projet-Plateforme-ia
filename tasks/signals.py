from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from projects.progress import attach_project_if_missing, sync_project_progress
from tasks.models import Task


@receiver(pre_save, sender=Task)
def remember_previous_project(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_project_id = None
        return
    instance._previous_project_id = (
        Task.objects.filter(pk=instance.pk).values_list('project_id', flat=True).first()
    )


@receiver(post_save, sender=Task)
def update_project_after_save(sender, instance, **kwargs):
    project_id = attach_project_if_missing(instance) or instance.project_id
    sync_project_progress(project_id)
    previous = getattr(instance, '_previous_project_id', None)
    if previous and previous != instance.project_id:
        sync_project_progress(previous)


@receiver(post_delete, sender=Task)
def update_project_after_delete(sender, instance, **kwargs):
    sync_project_progress(instance.project_id)
