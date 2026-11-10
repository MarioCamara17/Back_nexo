from django.contrib import admin

from .models import ChatMessage, ChatSession


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("role", "content", "intent", "payload", "created_at")
    can_delete = False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "last_place", "last_intent", "radius_km", "updated_at")
    list_filter = ("last_intent",)
    search_fields = ("id", "user__email", "last_place__name")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [ChatMessageInline]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("session", "role", "intent", "created_at")
    list_filter = ("role", "intent")
    search_fields = ("content", "session__id")
    readonly_fields = ("created_at",)
