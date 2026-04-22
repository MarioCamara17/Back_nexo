from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
from places.models import Place   # 👈 IMPORTANTE

class ChatbotView(APIView):
    def post(self, request):
        message = request.data.get('message', '').strip()

        if not message:
            return Response(
                {'error': 'No se recibió ningún mensaje'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 🔥 AQUÍ VA TU CÓDIGO
            places = Place.objects.all()

            places_text = ""
            for place in places:
                places_text += f"- {place.name}: {place.description}\n"

            # 🔥 DESPUÉS VA EL PAYLOAD
            payload = {
                "model": "phi3",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Eres NEXO, un asistente turístico de Tabasco.\n"
                            "SOLO puedes recomendar los siguientes lugares:\n\n"
                            f"{places_text}\n\n"
                            "REGLAS:\n"
                            "- No inventes lugares.\n"
                            "- Solo usa los lugares listados.\n"
                            "- Si no existe, dilo claramente.\n"
                        )
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                "stream": False,
                "keep_alive": "10m"
            }

            ollama_response = requests.post(
                "http://127.0.0.1:11434/api/chat",
                json=payload,
                timeout=180
            )

            ollama_response.raise_for_status()
            data = ollama_response.json()

            reply = data["message"]["content"]

            return Response({'reply': reply}, status=status.HTTP_200_OK)

        except Exception as e:
            print("ERROR:", repr(e))
            return Response(
                {'reply': 'Error en el servidor.'},
                status=status.HTTP_200_OK
            )