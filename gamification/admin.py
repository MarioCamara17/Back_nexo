from django.contrib import admin

# Register your models here.

from .models import TrainStation, StationVisit


@admin.register(TrainStation)
class TrainStationAdmin(admin.ModelAdmin):
    list_display = ('name', 'municipality', 'order', 'checkin_radius_m', 'checkin_enabled', 'active')
    search_fields = ('name', 'municipality')


@admin.register(StationVisit)
class StationVisitAdmin(admin.ModelAdmin):
    list_display = ('user', 'station', 'visited_at', 'distance_m', 'accuracy_m')
    readonly_fields = ('user', 'station', 'visited_at', 'distance_m', 'accuracy_m')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
