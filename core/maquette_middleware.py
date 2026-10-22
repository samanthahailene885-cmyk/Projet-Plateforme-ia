import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse


# Ces adresses fournissent des données. Les pages, elles, restent la maquette.
DATA_PREFIXES = ('api/', 'admin/', 'media/', 'static/')


class MaquetteMiddleware:
    """Sert la maquette React pour chaque page, une fois construite."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.dist = Path(settings.BASE_DIR) / 'maquette' / 'dist'

    def __call__(self, request):
        if request.method not in ('GET', 'HEAD') or not self.dist.is_dir():
            return self.get_response(request)

        relative = request.path.lstrip('/')
        if self._is_data(relative):
            return self.get_response(request)

        root = self.dist.resolve()
        candidate = root if relative == '' else (self.dist / relative).resolve()
        if candidate != root and root not in candidate.parents:
            return self.get_response(request)
        if candidate.is_dir():
            candidate = candidate / 'index.html'
        if candidate.is_file():
            return self._file(candidate)

        index = root / 'index.html'
        if index.is_file() and self._wants_page(request):
            return self._file(index)
        return self.get_response(request)

    def _is_data(self, relative):
        path = relative.split('?', 1)[0]
        if path.startswith(DATA_PREFIXES):
            return True
        if path.startswith('dashboard/indicateurs.json') or path.startswith('dashboard/recherche'):
            return True
        if path.startswith('reports/synthese'):
            return True
        return path.endswith('/pdf') or path.endswith('/pdf/') or path.endswith('.pdf')

    def _wants_page(self, request):
        if request.path in ('', '/'):
            return True
        accept = request.META.get('HTTP_ACCEPT', '')
        primary = accept.split(',', 1)[0].split(';', 1)[0].strip().lower()
        return primary in ('text/html', 'application/xhtml+xml')

    def _file(self, candidate):
        content_type, _encoding = mimetypes.guess_type(candidate.name)
        response = FileResponse(candidate.open('rb'), content_type=content_type or 'application/octet-stream')
        if candidate.suffix == '.html':
            del response['Content-Disposition']
            response['Cache-Control'] = 'no-cache'
        else:
            response['Cache-Control'] = 'public, max-age=86400'
        return response
