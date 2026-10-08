from datetime import timedelta

from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from authentication.models import User
from notifications.models import Notification

from .models import Message

ONLINE_AFTER = timedelta(minutes=15)
PROBLEM_DRAFT = 'Bonjour, je souhaite signaler un problème : '
MEETING_DRAFT = 'Bonjour, pourrais-je vous rencontrer dans votre bureau lorsque vous serez disponible ?'
WEEKDAYS_SHORT = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
WEEKDAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
MONTHS = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]


def person_name(user):
    return (user.get_full_name() or '').strip() or user.username


def initials(user):
    letters = f'{(user.first_name[:1] if user.first_name else "")}{(user.last_name[:1] if user.last_name else "")}'
    return letters.upper() or user.username[:2].upper()


def is_online(user):
    if not user or not user.last_login:
        return False
    return timezone.now() - user.last_login <= ONLINE_AFTER


def manager():
    return User.objects.filter(role='admin', is_active=True).order_by('pk').first()


def clock_label(moment):
    local = timezone.localtime(moment)
    today = timezone.localdate()
    if local.date() == today:
        return local.strftime('%H:%M')
    if local.date() == today - timedelta(days=1):
        return 'Hier'
    if today - timedelta(days=6) <= local.date() < today:
        return WEEKDAYS_SHORT[local.weekday()]
    return local.strftime('%d/%m')


def full_day_label(moment):
    local = timezone.localtime(moment)
    return f'{WEEKDAYS[local.weekday()]} {local.day} {MONTHS[local.month - 1]} {local.year}'


def portrait(user):
    if user is None:
        return '', ''
    photo = ''
    if user.photo:
        try:
            photo = user.photo.url
        except Exception:
            photo = ''
    subtitle = 'Responsable' if user.is_admin() else 'Employé'
    try:
        profile = user.employee_profile
    except Exception:
        profile = None
    if profile is not None:
        job = profile.get_position_display()
        subtitle = f'{job} · {profile.department}' if profile.department else job
    return photo, subtitle


def size_label(size):
    if not size:
        return ''
    if size < 1024:
        return f'{size} o'
    if size < 1024 * 1024:
        return f'{size / 1024:.1f} Ko'
    return f'{size / (1024 * 1024):.1f} Mo'


def thread_qs(employee):
    return Message.objects.filter(
        Q(sender=employee, receiver__role='admin') | Q(receiver=employee, sender__role='admin')
    ).select_related('sender', 'receiver')


def user_can_open(user, employee):
    if employee is None or employee.role != 'employee' or not employee.is_active:
        return False
    if user.is_admin():
        return True
    return user.pk == employee.pk


def mark_thread_read(user, employee):
    now = timezone.now()
    if user.is_admin():
        Message.objects.filter(
            sender=employee,
            receiver__role='admin',
            read_at__isnull=True,
        ).update(read_at=now)
        Notification.objects.filter(
            user=user,
            is_read=False,
            link=conversation_link(employee),
        ).update(is_read=True)
        return
    Message.objects.filter(
        receiver=user,
        sender__role='admin',
        read_at__isnull=True,
    ).update(read_at=now)
    inbox_url = reverse('messaging:inbox')
    Notification.objects.filter(
        user=user,
        is_read=False,
        link__startswith=inbox_url,
    ).update(is_read=True)


def conversation_link(partner):
    if partner is None:
        return reverse('messaging:inbox')
    return f"{reverse('messaging:inbox')}?avec={partner.pk}"


def notify_message(message):
    preview = (message.message or '').strip() or message.attachment_label or 'Pièce jointe'
    preview = preview[:180]
    if message.sender.role == 'admin':
        Notification.objects.create(
            user=message.receiver,
            title='Nouveau message du responsable',
            message=preview,
            notification_type='info',
            link='/messages/',
        )
        return
    from employees.models import Employee
    employee = Employee.objects.filter(user=message.sender).first()
    name = person_name(message.sender)
    title = f'Nouveau message de {name}'[:200]
    link = f'/messages/?avec={employee.pk}' if employee else '/messages/'
    for admin in User.objects.filter(role='admin', is_active=True):
        Notification.objects.create(
            user=admin,
            title=title,
            message=preview,
            notification_type='info',
            link=link,
        )


def _preview(message):
    text = (message.message or '').strip()
    if text:
        return text if len(text) <= 72 else f'{text[:69]}...'
    if message.attachment:
        return message.attachment_label
    return ''


def conversation_rows(user):
    if user.is_admin():
        people = list(
            User.objects.filter(role='employee', is_active=True)
            .select_related('employee_profile')
            .order_by('first_name', 'last_name', 'username')
        )
        ids = [person.pk for person in people]
        latest = {}
        if ids:
            for item in Message.objects.filter(
                Q(sender_id__in=ids, receiver__role='admin') | Q(receiver_id__in=ids, sender__role='admin')
            ).select_related('sender', 'receiver').order_by('-created_at'):
                employee_id = item.sender_id if item.sender.role == 'employee' else item.receiver_id
                if employee_id not in latest:
                    latest[employee_id] = item
        unread = {
            row['sender_id']: row['n']
            for row in Message.objects.filter(
                sender_id__in=ids,
                receiver__role='admin',
                read_at__isnull=True,
            ).values('sender_id').annotate(n=Count('id'))
        } if ids else {}
        rows = []
        for person in people:
            last = latest.get(person.pk)
            photo, subtitle = portrait(person)
            rows.append({
                'user': person,
                'name': person_name(person),
                'initials': initials(person),
                'photo': photo,
                'subtitle': subtitle,
                'online': is_online(person),
                'preview': _preview(last) if last else '',
                'when': clock_label(last.created_at) if last else '',
                'sort': last.created_at if last else None,
                'unread': unread.get(person.pk, 0),
                'url': conversation_link(person),
            })
        rows.sort(key=lambda row: (row['sort'] is None, -(row['sort'].timestamp() if row['sort'] else 0), row['name'].lower()))
        return rows

    boss = manager()
    if boss is None:
        return []
    last = thread_qs(user).order_by('-created_at').first()
    unread = Message.objects.filter(receiver=user, sender__role='admin', read_at__isnull=True).count()
    photo, subtitle = portrait(boss)
    return [{
        'user': boss,
        'name': person_name(boss),
        'role': 'Responsable',
        'initials': initials(boss),
        'photo': photo,
        'subtitle': subtitle or 'Responsable',
        'online': is_online(boss),
        'preview': _preview(last) if last else '',
        'when': clock_label(last.created_at) if last else '',
        'sort': last.created_at if last else None,
        'unread': unread,
        'url': conversation_link(boss),
    }]


def resolve_employee(user, raw):
    """Retourne l'employé de la conversation demandée, ou (None, erreur)."""
    if not raw:
        return None, ''
    try:
        partner_id = int(raw)
    except (TypeError, ValueError):
        return None, "Impossible d'ouvrir cette conversation."
    if user.is_admin():
        employee = User.objects.filter(pk=partner_id, role='employee', is_active=True).first()
        if employee is None:
            return None, 'Vous ne pouvez pas consulter cette conversation.'
        return employee, ''
    if user.role != 'employee':
        return None, 'Vous ne pouvez pas consulter cette conversation.'
    partner = User.objects.filter(pk=partner_id, is_active=True).first()
    if partner is None or partner.role != 'admin':
        return None, 'Vous ne pouvez pas consulter cette conversation.'
    return user, ''
