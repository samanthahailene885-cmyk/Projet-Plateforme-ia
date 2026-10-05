import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse


class MaquetteMiddleware:
    """Sert la maquette React à la racine quand elle a été construite."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.dist = Path(settings.BASE_DIR) / 'maquette' / 'dist'

    def __call__(self, request):
        if request.method not in ('GET', 'HEAD') or not self.dist.is_dir():
            return self.get_response(request)
        relative = request.path.lstrip('/')
        root = self.dist.resolve()
        candidate = root if relative == '' else (self.dist / relative).resolve()
        if candidate != root and root not in candidate.parents:
            return self.get_response(request)
        if candidate.is_dir():
            candidate = candidate / 'index.html'
        if candidate.is_file():
            content_type, _encoding = mimetypes.guess_type(candidate.name)
            response = FileResponse(candidate.open('rb'), content_type=content_type or 'application/octet-stream')
            if candidate.suffix == '.html':
                del response['Content-Disposition']
                response['Cache-Control'] = 'no-cache'
            else:
                response['Cache-Control'] = 'public, max-age=86400'
            return response
        return self.get_response(request)
