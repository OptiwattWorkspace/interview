from django.db import models


class Vehicle(models.Model):
    EMISSIONS_CHARGING_PLAN = 'emissions_plan'
    MONEY_CHARGING_PLAN = 'money_plan'
    CHARGING_PLANS = [
        (EMISSIONS_CHARGING_PLAN, 'Emissions Charging Plan'),
        (MONEY_CHARGING_PLAN, 'Money Charging Plan'),
    ]

    friendly_name = models.CharField(max_length=255)
    charging_plan = models.CharField(choices=CHARGING_PLANS, max_length=100)
    charger_kw = models.DecimalField(max_digits=5, decimal_places=2)
    battery_capacity = models.IntegerField()
    target_battery_pct = models.IntegerField()
    current_battery_pct = models.IntegerField()

class Emissions(models.Model):
    intensity = models.IntegerField()
    hour_of_day = models.IntegerField()

class UsageRates(models.Model):
    kwh_cost = models.DecimalField(max_digits=5, decimal_places=2)
    hour_of_day = models.IntegerField()
    is_weekday = models.BooleanField()