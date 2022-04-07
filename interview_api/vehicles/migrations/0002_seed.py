# Generated by Django 4.0.1 on 2022-04-07 15:26

from django.db import migrations

class Migration(migrations.Migration):

    initial = True

    dependencies = [
      ('vehicles', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
        """
          INSERT INTO vehicles_vehicle (friendly_name, charging_plan, charger_kw, battery_capacity, target_battery_pct, current_battery_pct)
          VALUES
          ('Tesla Cybertruck', 'money_plan', 11, 200, 90, 31),
          ('Tesla Model 3', 'emissions_plan', 10, 82, 85, 35);

          INSERT INTO vehicles_usagerates (kwh_cost, hour_of_day, is_weekday)
          VALUES
          (0.03, 0, true),
          (0.03, 1, true),
          (0.03, 2, true),
          (0.03, 3, true),
          (0.03, 4, true),
          (0.06, 5, true),
          (0.06, 6, true),
          (0.06, 7, true),
          (0.06, 8, true),
          (0.11, 9, true),
          (0.11, 10, true),
          (0.11, 11, true),
          (0.11, 12, true),
          (0.24, 13, true),
          (0.24, 14, true),
          (0.24, 15, true),
          (0.24, 16, true),
          (0.24, 17, true),
          (0.24, 18, true),
          (0.24, 19, true),
          (0.24, 20, true),
          (0.24, 21, true),
          (0.1, 22, true),
          (0.1, 23, true),

          (0.11, 0, false),
          (0.11, 1, false),
          (0.11, 2, false),
          (0.11, 3, false),
          (0.11, 4, false),
          (0.11, 5, false),
          (0.11, 6, false),
          (0.11, 7, false),
          (0.11, 8, false),
          (0.11, 9, false),
          (0.11, 10, false),
          (0.11, 11, false),
          (0.11, 12, false),
          (0.2, 13, false),
          (0.2, 14, false),
          (0.2, 15, false),
          (0.2, 16, false),
          (0.2, 17, false),
          (0.2, 18, false),
          (0.2, 19, false),
          (0.2, 20, false),
          (0.2, 21, false),
          (0.11, 22, false),
          (0.11, 23, false);

          INSERT INTO vehicles_emissions (intensity, hour_of_day)
          VALUES
          (20, 0),
          (20, 1),
          (20, 2),
          (10, 3),
          (10, 4),
          (10, 5),
          (10, 6),
          (10, 7),
          (20, 8),
          (20, 9),
          (20, 10),
          (40, 11),
          (40, 12),
          (90, 13),
          (90, 14),
          (90, 15),
          (90, 16),
          (90, 17),
          (90, 18),
          (90, 19),
          (90, 20),
          (40, 21),
          (40, 22),
          (40, 23);
        """)
    ]
