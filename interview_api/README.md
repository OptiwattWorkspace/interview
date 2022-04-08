# Charge Scheduling
In short, charge scheduling returns a set of hourly time periods that specify whether or not the vehicle will charge, based on a boolean flag called `should_charge`. Here is an example scheduling period:
```json
{
  "usage_rates": {
    "id": 1,
    "kwh_cost": "0.1",
    "hour_of_day": 1,
    "is_weekday": true
  },
  "start_time": "2022-04-08T15:00:00Z",
  "end_time": "2022-04-08T16:00:00Z",
  "should_charge": true,
  "estimated_battery_pct": 50
}
```

Charge scheduling behavior is determined by the charging plan that is selected for a vehicle, stored as the `charging_plan` property of the `Vehicle` model.
The types of plans are described below.

## Fast Scheduler 🏃‍♀️
This scheduler doesn't care about anything besides charging as fast as possible. Given a target battery percent, this plan starts charging until the target is reached.

## Frugal Scheduler 💸
This scheduler is all about it's money. Given a target battery percent, this plan will charge during the lowest cost periods in order to meet the target percent.

## Emissions Scheduler 🌳
This scheduler is saving the planet. Given a target battery percent, this plan  will only charge during periods in which the emission intensity is within below the maximum intensity threshold, attempting to reach the target percent.
The maximum intensity threshold is defined as the minimum intensity of the periods in the next 24 hours, plus 30% of the range of the emissions of the periods.


