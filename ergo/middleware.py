from django.conf import settings

class CSPMiddleware:
    """
    Middleware para adicionar o header Content-Security-Policy em todas as requisições.
    Isso aumenta significativamente a segurança contra ataques XSS.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Só aplicamos a política rígida se estivermos em produção (DEBUG=False)
        # Em desenvolvimento, o Debug Toolbar e outros scripts podem ser bloqueados pelo CSP.
        if not getattr(settings, 'DEBUG', True):
            # Política:
            # - default-src 'self': Permite tudo que vier do próprio domínio.
            # - script-src 'self' 'unsafe-inline' 'unsafe-eval': Permite scripts do domínio, scripts inline (ex: JS nas tags <script>) e eval (usado por bibliotecas como Chart.js).
            # - style-src 'self' 'unsafe-inline': Permite CSS do domínio e styles inline (<div style="...">).
            # - img-src 'self' data: https:: Permite imagens do domínio, em base64 (data:) e urls https.
            # - font-src 'self' data:: Permite carregar fontes do próprio site.
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "frame-ancestors 'none';" # Impede que o site seja colocado em iFrames (Clickjacking)
            )
            response['Content-Security-Policy'] = csp
            
        return response
