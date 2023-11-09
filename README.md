# API Specification

### Vehicle PATH Endpoint

#### List Vehicles

- **URL**: `/vehicles/`
- **Method**: `GET`
- **Description**: Retrieve a list of all vehicles.
- **Response**: A JSON array of vehicle objects.

#### Retrieve Vehicle

- **URL**: `/vehicles/{id}/`
- **Method**: `GET`
- **Description**: Retrieve a single vehicle by its ID.
- **URL Parameters**: `id=[integer]`, the unique identifier of the vehicle.
- **Response**: A JSON object representing the vehicle.

#### Vehicle Charging Forecast

- **URL**: `/vehicles/{id}/forecast/`
- **Method**: `GET`
- **Description**: Retrieve the charging forecast for a specific vehicle.
- **URL Parameters**: `id=[integer]`, the unique identifier of the vehicle.
- **Response**: A JSON object with the vehicle data and associated charging periods.

**Note**: Replace `{id}` with the actual ID of the vehicle you wish to query.

### Update Vehicle Charging Plan

- **URL**: `/vehicles/{id}/`
- **Method**: `PATCH`
- **Description**: Update the charging plan for a specific vehicle.
- **URL Parameters**: `id=[integer]`, the unique identifier of the vehicle.
- Data Parameters (JSON Body)

  - **Content-Type**: `application/json`
  - **Body**:
    ```json
    {
      "charging_plan": "selected_plan"
    }
    ```

    Replace `selected_plan` with one of the following values depending on the desired charging plan:

    - `"emissions_plan"` for Emissions Charging Plan
    - `"money_plan"` for Money Charging Plan
    - `"fast_plan"` for Fast Charging Plan

    The request body should only contain the fields that are intended to be updated.
- **Response**: A JSON object representing the updated vehicle.

**Example**:
```json
{
  "charging_plan": "fast_plan"
}
```

Ensure that you only send the fields that you want to update. This request will only update the `charging_plan` field of the vehicle with the provided ID.
