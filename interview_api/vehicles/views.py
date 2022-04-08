from django.views.generic import ListView
from vehicles.classes.schedule_manager import ScheduleManager
from django.http import JsonResponse

from vehicles.models import Period, Vehicle
from vehicles.serializers import PeriodSerializer, VehicleSerializer

class ChargeForecastView(ListView):
    model = Period

    def get(self, request, format=None):
        vehicle = Vehicle.objects.first()
        schedule_manager = ScheduleManager.manager_for_vehicle(vehicle)
        periods = schedule_manager.periods
        serialized_vehicle = VehicleSerializer(vehicle)
        serialized_periods = PeriodSerializer(periods, many=True)
        response = {
            'vehicle': serialized_vehicle.data,
            'periods': serialized_periods.data
        }
        return JsonResponse(response, safe=False)