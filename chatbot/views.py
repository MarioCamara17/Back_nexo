import logging
import math
from uuid import UUID

from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .agent import NexoAgent, AgentError
from .models import ChatMessage, ChatSession


logger = logging.getLogger(__name__)


MENU = [
    {
        "id": "nearby",
        "label": "¿Qué hay cerca de mi ubicación actual?",
        "group": "Exploración",
    },
    {
        "id": "popular",
        "label": "¿Cuáles son los lugares más destacados o populares?",
        "group": "Exploración",
    },
    {
        "id": "itinerary",
        "label": (
            "¿Qué lugares cercanos puedo visitar "
            "y cuánto duran sus rutas?"
        ),
        "group": "Exploración",
    },
    {
        "id": "history",
        "label": "¿Cuál es la historia de este lugar?",
        "group": "Historia y cultura",
    },
    {
        "id": "legends",
        "label": "¿Existen datos curiosos o leyendas sobre este lugar?",
        "group": "Historia y cultura",
    },
    {
        "id": "directions",
        "label": "¿Cómo llego a este lugar desde donde estoy?",
        "group": "Rutas y logística",
    },
    {
        "id": "logistics",
        "label": "¿Cuáles son los horarios y costos de entrada?",
        "group": "Rutas y logística",
    },
    {
        "id": "filter",
        "label": "¿Cómo puedo filtrar el mapa por categoría?",
        "group": "Ayuda de NEXO",
    },
    {
        "id": "favorites",
        "label": "¿Cómo guardo lugares y recorridos?",
        "group": "Ayuda de NEXO",
    },
]


class ChatRequest(serializers.Serializer):
    message = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1200,
    )

    intent = serializers.ChoiceField(
        choices=[item["id"] for item in MENU] + ["menu"],
        required=False,
        allow_blank=True,
    )

    place_id = serializers.UUIDField(required=False)

    latitude = serializers.FloatField(
        min_value=-90,
        max_value=90,
        required=False,
    )

    longitude = serializers.FloatField(
        min_value=-180,
        max_value=180,
        required=False,
    )

    radius_km = serializers.FloatField(
        min_value=0.5,
        max_value=100,
        required=False,
    )

    minutes = serializers.IntegerField(
        min_value=1,
        max_value=1440,
        required=False,
    )

    session_id = serializers.UUIDField(required=False)

    context = serializers.JSONField(required=False)

    def validate(self, attrs):
        for field in ("latitude", "longitude", "radius_km"):
            if field in attrs and not math.isfinite(attrs[field]):
                raise serializers.ValidationError({
                    field: "Introduce un número finito."
                })

        if not (attrs.get("message") or "").strip() and not attrs.get("intent"):
            raise serializers.ValidationError({
                "message": "Escribe una consulta o selecciona una opción."
            })

        return attrs


class ChatbotView(APIView):
    """Consultas públicas de información turística.

    El asistente acepta tanto preguntas libres (``message``) como las
    intenciones predefinidas del menú antiguo (``intent``). Guardar
    favoritos y rutas sigue utilizando sus APIs autenticadas.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        session_id = self._parse_uuid(request.query_params.get("session_id"))
        session = self._get_session(request, session_id)
        result = NexoAgent(
            session,
            request,
            {"message": "", "intent": "menu"},
        ).respond()
        result["menu"] = MENU

        if request.query_params.get("history") in {"1", "true", "yes"}:
            result["history"] = self._history(session)

        return Response(result)

    def post(self, request):
        serializer = ChatRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        session = self._get_session(request, data.get("session_id"))
        message_text = (data.get("message") or "").strip()
        intent = data.get("intent") or ""

        ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_USER,
            content=message_text or intent,
            intent=intent,
            payload={
                "intent": intent,
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "radius_km": data.get("radius_km"),
                "place_id": str(data["place_id"]) if data.get("place_id") else None,
            },
        )

        try:
            result = NexoAgent(session, request, data).respond()
        except AgentError as exc:
            return Response(exc.detail, status=exc.status_code)
        except Exception:
            logger.exception("Error inesperado del asistente NEXO")
            return Response(
                {
                    "reply": (
                        "Tuve un problema interno al preparar la respuesta. "
                        "Vuelve a intentarlo en un momento."
                    ),
                    "kind": "error",
                    "places": [],
                    "actions": [],
                    "suggestions": [],
                    "session_id": str(session.pk),
                },
                status=500,
            )

        ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_ASSISTANT,
            content=result.get("reply", ""),
            intent=str(result.get("meta", {}).get("intent", ""))[:40],
            payload=result,
        )

        return Response(result)

    def delete(self, request):
        session_id = self._parse_uuid(
            request.query_params.get("session_id")
            or request.data.get("session_id")
        )

        if session_id is None:
            return Response(
                {"detail": "Indica el identificador de la conversación."},
                status=400,
            )

        session = ChatSession.objects.filter(pk=session_id).first()

        if session is None:
            return Response(status=204)

        if session.user_id and (
            not request.user.is_authenticated
            or session.user_id != request.user.pk
        ):
            return Response(status=403)

        session.delete()
        return Response(status=204)

    @staticmethod
    def _parse_uuid(value) -> UUID | None:
        if not value:
            return None
        try:
            return UUID(str(value))
        except (ValueError, TypeError, AttributeError):
            return None

    def _get_session(self, request, session_id: UUID | None) -> ChatSession:
        user = request.user if request.user.is_authenticated else None

        if session_id is not None:
            session = ChatSession.objects.filter(pk=session_id).first()

            if session is not None:
                if session.user_id and (
                    user is None or session.user_id != user.pk
                ):
                    # No se reutiliza una conversación de otra cuenta.
                    return ChatSession.objects.create(user=user)

                if user is not None and session.user_id is None:
                    session.user = user
                    session.save(update_fields=["user", "updated_at"])

                return session

            return ChatSession.objects.create(pk=session_id, user=user)

        return ChatSession.objects.create(user=user)

    @staticmethod
    def _history(session: ChatSession) -> list[dict]:
        return [
            {
                "role": message.role,
                "content": message.content,
                "intent": message.intent,
                "created_at": message.created_at.isoformat(),
            }
            for message in session.messages.all()[:30]
        ]
