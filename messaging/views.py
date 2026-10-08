from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .files import validate_message_file
from .models import Message
from .services import (
    MEETING_DRAFT,
    PROBLEM_DRAFT,
    conversation_link,
    conversation_rows,
    full_day_label,
    initials,
    is_online,
    manager,
    mark_thread_read,
    notify_message,
    person_name,
    portrait,
    resolve_employee,
    size_label,
    thread_qs,
    user_can_open,
)


def _decorate(item, viewer):
    item.mine = item.sender_id == viewer.pk
    item.sender_name = person_name(item.sender)
    item.initials = initials(item.sender)
    item.photo, _subtitle = portrait(item.sender)
    item.file_size = size_label(item.attachment_size)
    item.day = timezone.localtime(item.created_at).date().isoformat()
    item.day_label = full_day_label(item.created_at)
    return item


def _person_card(user, role):
    photo, subtitle = portrait(user) if user else ('', '')
    return {
        'user': user,
        'name': person_name(user) if user else role,
        'initials': initials(user) if user else role[:1],
        'photo': photo,
        'subtitle': subtitle or role,
        'online': is_online(user),
        'role': role,
    }


@login_required
@require_http_methods(['GET', 'POST'])
def inbox(request):
    try:
        return _inbox(request)
    except DatabaseError:
        return render(request, 'messaging/inbox.html', {
            'load_error': True,
            'rows': [],
            'thread': [],
            'chat_unread': 0,
            'my_initials': '',
            'my_photo': '',
        })


def _inbox(request):
    if request.method == 'POST':
        return _send(request)

    raw = request.GET.get('avec')
    employee, error = resolve_employee(request.user, raw)
    if error:
        messages.error(request, error)
        return redirect('messaging:inbox')
    if employee is None and not request.user.is_admin():
        boss = manager()
        if boss is not None:
            return redirect(conversation_link(boss))

    rows = conversation_rows(request.user)
    has_any_message = any(row['sort'] for row in rows)
    thread = []
    active = None
    if employee and user_can_open(request.user, employee):
        mark_thread_read(request.user, employee)
        thread = [_decorate(item, request.user) for item in thread_qs(employee)]
        rows = conversation_rows(request.user)
        if request.user.is_admin():
            active = _person_card(employee, 'Employé')
        else:
            active = _person_card(manager(), 'Responsable')
    my_photo, _my_job = portrait(request.user)
    return render(request, 'messaging/inbox.html', {
        'rows': rows,
        'thread': thread,
        'active': active,
        'has_any_message': has_any_message,
        'problem_draft': PROBLEM_DRAFT,
        'meeting_draft': MEETING_DRAFT,
        'load_error': False,
        'chat_unread': sum(row['unread'] for row in rows),
        'my_initials': initials(request.user),
        'my_photo': my_photo,
    })


def _send(request):
    employee, error = resolve_employee(request.user, request.POST.get('avec'))
    if error or employee is None or not user_can_open(request.user, employee):
        messages.error(request, error or 'Vous ne pouvez pas envoyer ce message.')
        return redirect('messaging:inbox')

    text = (request.POST.get('message') or '').strip()
    uploaded = request.FILES.get('attachment')
    if not text and uploaded is None:
        messages.error(request, 'Écrivez un message avant de l\'envoyer.')
        return redirect(conversation_link(employee if request.user.is_admin() else manager()))
    if len(text) > 4000:
        messages.error(request, 'Le message est trop long.')
        return redirect(conversation_link(employee if request.user.is_admin() else manager()))

    size = 0
    if uploaded is not None:
        try:
            validate_message_file(uploaded)
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
            return redirect(conversation_link(employee if request.user.is_admin() else manager()))
        size = uploaded.size or 0

    if request.user.is_admin():
        receiver = employee
    else:
        receiver = manager()
        if receiver is None:
            messages.error(request, 'Aucun responsable n\'est disponible pour recevoir votre message.')
            return redirect('messaging:inbox')

    item = Message(
        sender=request.user,
        receiver=receiver,
        message=text,
        attachment_size=size,
    )
    if uploaded is not None:
        item.attachment = uploaded
    item.save()
    notify_message(item)
    if not request.user.is_admin() and text.startswith(PROBLEM_DRAFT):
        detail = text[len(PROBLEM_DRAFT):].strip()
        try:
            employee = request.user.employee_profile
        except Exception:
            employee = None
        if detail and employee is not None:
            from tasks.models import Difficulty
            Difficulty.objects.create(
                employee=employee,
                description=detail[:2000],
                reported_on=timezone.localdate(),
                status='open',
                priority='medium',
            )
    target = employee if request.user.is_admin() else receiver
    return redirect(conversation_link(target))


@login_required
def message_file(request, pk):
    item = Message.objects.select_related('sender', 'receiver').filter(pk=pk).first()
    if item is None or not item.attachment:
        raise Http404
    employee = item.sender if item.sender.role == 'employee' else item.receiver
    if not user_can_open(request.user, employee):
        messages.error(request, 'Vous ne pouvez pas ouvrir ce fichier.')
        return redirect('messaging:inbox')
    handle = item.attachment.open('rb')
    response = FileResponse(handle, as_attachment=True, filename=item.attachment_label)
    return response
