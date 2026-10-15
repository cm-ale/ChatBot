# Guía de Integración en Core (Django) y Docker Compose

Esta guía detalla los cambios puntuales necesarios en el resto del monorepo para conectar `services/webchat` con `services/core`.

---

## 1. Configuración en `docker-compose.yml`

En el bloque existente de `webchat`, agregar la variable de entorno `CORE_SERVICE_TOKEN`:

```yaml
  webchat:
    build:
      context: ./services/webchat
      dockerfile: Dockerfile
    profiles: ["webchat"]
    ports:
      - "8006:8006"
    environment:
      - CORE_URL=http://core:8000
      - CORE_SERVICE_TOKEN=${WEBCHAT_SERVICE_TOKEN}
      - DB_SCHEMA=webchat
      - PORT=8006
    depends_on:
      - core
      - postgres
```

En el archivo `.env` del monorepo, definir:
```env
WEBCHAT_SERVICE_TOKEN=<token_generado_en_admin_panel>
```

---

## 2. Salida desde Core hacia Webchat cuando un Operador Humano Responde

Cuando un operador responde desde el Operators Desk (`POST /conversaciones/{id}/responder/`), Core despacha el mensaje saliente. Para el canal `WEBCHAT`, Core debe enviar un `POST /messages/send` a `services/webchat`.

### Cliente en Core: `services/core/conversations/webchat_client.py`

```python
import logging
import requests
from django.conf import settings
from platform_admin.models import ServiceToken

logger = logging.getLogger(__name__)

def enviar_mensaje_webchat(visitor_id: str, texto: str) -> bool:
    """
    Envía un mensaje saliente de operador humano hacia el visitante en services/webchat.
    """
    webchat_url = getattr(settings, "WEBCHAT_SERVICE_URL", "http://webchat:8006")
    endpoint = f"{webchat_url}/messages/send"
    
    # Obtener el token activo para WEBCHAT
    token_obj = ServiceToken.objects.filter(
        servicio=ServiceToken.Servicio.WEBCHAT, 
        activo=True
    ).first()
    
    if not token_obj or not token_obj.token_plano:
        logger.error("[WebchatClient] No se encontró ServiceToken activo para WEBCHAT")
        return False

    headers = {
        "Authorization": f"Service-Token {token_obj.token_plano}",
        "Content-Type": "application/json"
    }
    payload = {
        "visitor_id": visitor_id,
        "texto": texto
    }

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=5)
        return response.status_code == 200
    except requests.RequestException as e:
        logger.error(f"[WebchatClient] Error enviando mensaje a webchat: {e}")
        return False
```

---

## 3. Endpoint Interno en Core para Historial de Conversación (Opcional recomendado)

Para que el visitante recupere sus mensajes al recargar la página directamente desde la base de datos de Core:

### Vista en `services/core/conversations/internal_views.py`:

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from platform_admin.service_auth import ServiceTokenAuthentication
from conversations.models import Contacto, Conversacion, Mensaje

class InternalHistorialMensajesView(APIView):
    """
    Permite a los Channel Gateways (como Webchat) obtener el historial reciente
    de un visitante anónimo autenticado mediante Service-Token.
    """
    authentication_classes = [ServiceTokenAuthentication]
    permission_classes = []

    def get(self, request):
        org_id = request.query_params.get("organization_id")
        canal = request.query_params.get("canal")
        contact_externo_id = request.query_params.get("contact_externo_id")

        if not all([org_id, canal, contact_externo_id]):
            return Response(
                {"error": "Faltan parámetros obligatorios"},
                status=status.HTTP_400_BAD_REQUEST
            )

        contacto = Contacto.objects.filter(
            organization_id=org_id,
            canal=canal,
            identificador_externo=contact_externo_id
        ).first()

        if not contacto:
            return Response({"mensajes": []})

        conversacion = Conversacion.objects.filter(contacto=contacto).order_by("-fecha_creacion").first()
        if not conversacion:
            return Response({"mensajes": []})

        mensajes_qs = Mensaje.objects.filter(conversacion=conversacion).order_by("fecha_envio")[:50]
        
        historial = [
            {
                "id": m.id,
                "origen": "visitante" if m.es_entrante else "bot",
                "texto": m.texto,
                "fecha": m.fecha_envio.isoformat()
            }
            for m in mensajes_qs
        ]

        return Response({"mensajes": historial})
```

Registrar la ruta en `services/core/conversations/urls.py`:
```python
path("api/core/internal/mensajes/", InternalHistorialMensajesView.as_view(), name="internal-historial"),
```
