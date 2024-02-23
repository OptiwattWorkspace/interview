from vehicles.models import Vehicle

def test_time_to_charge_happy_path():
    vehicle = Vehicle(charging_plan=Vehicle.FAST_CHARGING_PLAN,
                      charger_kw=1,
                      battery_capacity=100,
                      target_battery_pct=80,
                      current_battery_pct=75)
    assert vehicle.time_to_charge == 5.0

