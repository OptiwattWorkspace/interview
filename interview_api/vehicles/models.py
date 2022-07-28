from django.db import models


class Vehicle(models.Model):
    EMISSIONS_CHARGING_PLAN = 'emissions_plan'
    MONEY_CHARGING_PLAN = 'money_plan'
    FAST_CHARGING_PLAN = 'fast_plan'
    CHARGING_PLANS = [
        (EMISSIONS_CHARGING_PLAN, 'Emissions Charging Plan'),
        (MONEY_CHARGING_PLAN, 'Money Charging Plan'),
        (FAST_CHARGING_PLAN, 'Fast Charging Plan'),
    ]

    friendly_name = models.CharField(max_length=255)
    charging_plan = models.CharField(choices=CHARGING_PLANS, max_length=100)
    charger_kw = models.DecimalField(max_digits=5, decimal_places=2)
    battery_capacity = models.IntegerField()
    target_battery_pct = models.IntegerField()
    current_battery_pct = models.IntegerField()

    @property
    def time_to_charge(self):
        battery_percent_difference = max(self.target_battery_pct - self.current_battery_pct, 0)
        kwh_dt = battery_percent_difference * self.battery_capacity / 100
        return kwh_dt / float(self.charger_kw)

class Emissions(models.Model):
    intensity = models.IntegerField()
    hour_of_day = models.IntegerField()

class UsageRates(models.Model):
    kwh_cost = models.DecimalField(max_digits=5, decimal_places=2)
    hour_of_day = models.IntegerField()
    is_weekday = models.BooleanField()


class Period(models.Model):
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    should_charge = models.BooleanField()
    usage_rates = models.ForeignKey(UsageRates, on_delete=models.PROTECT)
    estimated_battery_pct = models.IntegerField()

    class Meta:
        managed = False