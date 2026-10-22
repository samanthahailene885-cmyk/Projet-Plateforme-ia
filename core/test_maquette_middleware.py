import tempfile
from pathlib import Path

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from core.maquette_middleware import MaquetteMiddleware


class MaquetteMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.dist = Path(tempfile.mkdtemp())
        (self.dist / 'index.html').write_text('<!doctype html><title>RACIN</title>', encoding='utf-8')
        assets = self.dist / 'assets'
        assets.mkdir()
        (assets / 'app.js').write_text('console.log(1)', encoding='utf-8')
        self.middleware = MaquetteMiddleware(lambda request: HttpResponse('ancienne page'))
        self.middleware.dist = self.dist

    def test_browser_pages_use_the_maquette(self):
        for path in ('/', '/login/', '/dashboard/', '/employees/', '/decision-ai/assistant/'):
            response = self.middleware(self.factory.get(path, HTTP_ACCEPT='text/html,application/xhtml+xml'))
            self.assertContains(response, 'RACIN')
            self.assertNotContains(response, 'ancienne page')

    def test_data_requests_stay_on_django(self):
        for path in ('/api/session/', '/dashboard/indicateurs.json', '/reports/synthese/', '/media/rapport.pdf'):
            response = self.middleware(self.factory.get(path, HTTP_ACCEPT='*/*'))
            self.assertContains(response, 'ancienne page')

    def test_built_assets_are_served_from_the_maquette(self):
        response = self.middleware(self.factory.get('/assets/app.js', HTTP_ACCEPT='*/*'))
        self.assertContains(response, 'console.log(1)')
