from django.views.generic import ListView
from vehicles.classes.schedule_manager import ScheduleManager
from django.http import JsonResponse

from vehicles.models import Period, Vehicle
from vehicles.serializers import PeriodSerializer

class ChargeForecastView(ListView):
    model = Period

    def get(self, request, format=None):
        vehicle = Vehicle.objects.first()
        periods = ScheduleManager(vehicle=vehicle).periods
        serialized = PeriodSerializer(periods, many=True)
        return JsonResponse(serialized.data, safe=False)