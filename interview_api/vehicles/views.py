from vehicles.classes.schedule_manager import ScheduleManager
from django.http import JsonResponse
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.decorators import action

from vehicles.models import Vehicle
from vehicles.serializers import PeriodSerializer, VehicleSerializer


class VehicleViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin):
    model = Vehicle
    serializer_class = VehicleSerializer
    queryset = Vehicle.objects.all()

    @action(detail=True, methods=['get'])
    def forecast(self, request, pk=None):
        vehicle = Vehicle.objects.get(pk=pk)
        schedule_manager = ScheduleManager.manager_for_vehicle(vehicle)
        periods = schedule_manager.periods
        serialized_vehicle = VehicleSerializer(vehicle)
        serialized_periods = PeriodSerializer(periods, many=True)
        response = {
            'vehicle': serialized_vehicle.data,
            'periods': serialized_periods.data
        }
        return JsonResponse(response, safe=False)