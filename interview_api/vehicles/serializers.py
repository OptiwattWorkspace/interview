from dataclasses import fields
from rest_framework import serializers
from vehicles.models import Period, UsageRates

class UsageRatesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageRates
        fields = '__all__'

class PeriodSerializer(serializers.ModelSerializer):
    usage_rates = UsageRatesSerializer()
    class Meta:
        model = Period
        exclude = ('id', )

