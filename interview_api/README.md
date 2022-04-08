# Charge Scheduling
Charge scheduling behavior is determined by the charging plan that is selected for a vehicle, stored as the `charging_plan` property of the `Vehicle` model.
The types of plans are described below.

## Fast Scheduler 🏃‍♀️
This scheduler doesn't care about anything besides charging as fast as possible. Given a target battery percent, this plan starts charging until the target is reached.

## Frugal Scheduler 💸
This scheduler is all about it's money. Given a target battery percent, this plan will charge during the lowest cost periods in order to meet the target percent.

## Emissions Scheduler 🌳
This scheduler is saving the planet. Given a target battery percent, this plan  will only charge during periods in which the emission intensity is within below the maximum intensity threshold, attempting to reach the target percent.
The maximum intensity threshold is defined as the minimum intensity of the periods in the next 24 hours, plus 30% of the range of the emissions of the periods.


