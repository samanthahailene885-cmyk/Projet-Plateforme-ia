from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailOrUsernameModelBackend(ModelBackend):
    """Connexion par nom d'utilisateur ou par adresse e-mail."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        user = UserModel.objects.filter(username__iexact=username).first()
        if user is None:
            matches = UserModel.objects.filter(email__iexact=username)
            user = matches.first() if matches.count() == 1 else None
        if user is None:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
