from rest_framework import serializers
from vehicles.models import Period, UsageRates, Vehicle

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = '__all__'

class UsageRatesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageRates
        fields = '__all__'

class PeriodSerializer(serializers.ModelSerializer):
    usage_rates = UsageRatesSerializer()
    class Meta:
        model = Period
        exclude = ('id', )

