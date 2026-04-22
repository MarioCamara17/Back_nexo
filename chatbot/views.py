from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
from places.models import Place


class ChatbotView(APIView):
    def post(self, request):
        message = request.data.get("message", "").strip()

        if not message:
            return Response(
                {"error": "No se recibió ningún mensaje"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            places = Place.objects.all()

            if not places.exists():
                return Response(
                    {"reply": "No hay lugares cargados en el mapa actualmente."},
                    status=status.HTTP_200_OK
                )

            place_names = [place.name for place in places]
            message_lower = message.lower()

            # Respuesta directa para preguntas simples sobre disponibilidad
            if (
                "qué lugares" in message_lower
                or "que lugares" in message_lower
                or "lugares disponibles" in message_lower
                or "qué sitios" in message_lower
                or "que sitios" in message_lower
                or "sitios disponibles" in message_lower
            ):
                return Response(
                    {"reply": "Los lugares disponibles son: " + ", ".join(place_names) + "."},
                    status=status.HTTP_200_OK
                )

            places_text = ""
            for place in places:
                description = (place.description or "").strip()
                places_text += f"- {place.name}: {description}\n"

            payload = {
                "model": "phi3",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Eres NEXO, un asistente turístico de Tabasco.\n"
                            "Tu única fuente de información son los lugares listados abajo.\n\n"
                            f"{places_text}\n"
                            "REGLAS ESTRICTAS:\n"
                            "1. SOLO puedes mencionar lugares de la lista.\n"
                            "2. NO inventes lugares, rutas ni datos.\n"
                            "3. Si el usuario pide algo fuera de la lista, responde exactamente: "
                            "'No tengo información de ese lugar dentro del mapa actual.'\n"
                            "4. Responde siempre en español.\n"
                            "5. Responde de forma breve, clara y natural.\n"
                            "6. No agregues encabezados, etiquetas, notas internas ni símbolos extraños.\n"
                            "7. Si el usuario pide recomendaciones, elige solo de la lista.\n"
                            "8. Si el usuario pide una ruta, arma la ruta solo con lugares de la lista.\n"
                            "9. No escribas símbolos como ## ni instrucciones internas.\n"
                            "10. Si preguntan qué lugares hay disponibles, enumera únicamente los nombres."
                        )
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": 0.2,
                    "num_predict": 120
                }
            }

            ollama_response = requests.post(
                "http://127.0.0.1:11434/api/chat",
                json=payload,
                timeout=180
            )
            ollama_response.raise_for_status()

            data = ollama_response.json()
            reply = data.get("message", {}).get("content", "").strip()

            # Limpieza de texto basura del modelo
            if "##" in reply:
                reply = reply.split("##")[0].strip()

            frases_bloqueadas = [
                "Instrucción",
                "restricciones",
                "Eres NEXO",
            ]

            for frase in frases_bloqueadas:
                if frase in reply:
                    reply = reply.split(frase)[0].strip()

            if not reply:
                reply = "No pude generar una respuesta clara en este momento."

            return Response({"reply": reply}, status=status.HTTP_200_OK)

        except requests.exceptions.RequestException as e:
            print("ERROR DE CONEXIÓN CON OLLAMA:", repr(e))
            return Response(
                {"reply": "No pude conectarme con el motor de IA local."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            print("ERROR GENERAL DEL CHATBOT:", repr(e))
            return Response(
                {"reply": "Error en el servidor."},
                status=status.HTTP_200_OK
            )