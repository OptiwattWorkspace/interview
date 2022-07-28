import math
from datetime import datetime, timedelta
from typing import List
from abc import ABC, abstractmethod
from vehicles.models import Period, UsageRates, Vehicle


class ScheduleManager(ABC):
    HOURS_TO_FORECAST = 24
    DEFAULT_PERIOD_DURATION = 1

    vehicle: Vehicle
    periods: List[Period]

    def __init__(self, vehicle) -> None:
        self.vehicle = vehicle
        self.set_periods()
        self.set_period_charging_times()

    @staticmethod
    def manager_for_vehicle(vehicle: Vehicle):
        if vehicle.charging_plan == Vehicle.EMISSIONS_CHARGING_PLAN:
            return EmissionsScheduleManager(vehicle)
        elif vehicle.charging_plan == Vehicle.MONEY_CHARGING_PLAN:
            return FrugalScheduleManager(vehicle)
        elif vehicle.charging_plan == Vehicle.FAST_CHARGING_PLAN:
            return FastScheduleManager(vehicle)

    @staticmethod
    def get_usage_rate_from_datetime(dt: datetime) -> UsageRates:
        return UsageRates.objects.filter(hour_of_day=dt.hour, is_weekday=dt.isoweekday() < 6).first()

    @staticmethod
    def generate_forecasted_datetimes(hours_ahead: int) -> List[datetime]:
        delta = timedelta(hours=ScheduleManager.DEFAULT_PERIOD_DURATION)
        end_datetime = datetime.now() + timedelta(hours=hours_ahead)
        start_date = datetime.now().replace(minute=0, second=0, microsecond=0)
        dates = []
        while start_date < end_datetime:
            dates.append(start_date)
            start_date += delta
        return dates

    @abstractmethod
    def set_period_charging_times(self) -> None:
        raise NotImplementedError()

    def set_periods(self):
        datetimes = ScheduleManager.generate_forecasted_datetimes(
            hours_ahead=ScheduleManager.HOURS_TO_FORECAST)

        def datetime_to_period(dt: datetime) -> Period:
            return Period(start_time=dt,
                          end_time=dt +
                          timedelta(
                              hours=ScheduleManager.DEFAULT_PERIOD_DURATION),
                          should_charge=False,
                          usage_rates=self.get_usage_rate_from_datetime(dt),
                          estimated_battery_pct=self.vehicle.current_battery_pct)

        self.periods = list(map(datetime_to_period, datetimes))


class FastScheduleManager(ScheduleManager):
    def set_period_charging_times(self) -> None:
        hours_to_charge = math.ceil(self.vehicle.time_to_charge)
        if hours_to_charge > 0:
            for idx in range(len(self.periods)):
                if idx >= hours_to_charge:
                    self.periods[idx].estimated_battery_pct = self.vehicle.target_battery_pct
                else:
                    self.periods[idx].should_charge = True
                    hours_charged = idx + 1
                    percent_charged = ((self.vehicle.charger_kw * hours_charged) / self.vehicle.battery_capacity) * 100
                    self.periods[idx].estimated_battery_pct = min(self.vehicle.target_battery_pct, self.vehicle.current_battery_pct + percent_charged)


class FrugalScheduleManager(ScheduleManager):
    def set_period_charging_times(self) -> None:
        min_usage_rate = min(self.periods, key=lambda p: p.usage_rates.kwh_cost).usage_rates.kwh_cost
        hours_to_charge = math.ceil(self.vehicle.time_to_charge)
        hours_charged = 0
        if hours_to_charge > 0:
            for idx in range(len(self.periods)):
                if self.periods[idx].usage_rates.kwh_cost == min_usage_rate and hours_charged < hours_to_charge:
                    self.periods[idx].should_charge = True
                    hours_charged += 1
                percent_charged = ((self.vehicle.charger_kw * hours_charged) / self.vehicle.battery_capacity) * 100
                self.periods[idx].estimated_battery_pct = min(self.vehicle.target_battery_pct, self.vehicle.current_battery_pct + percent_charged)


class EmissionsScheduleManager(ScheduleManager):
    pass