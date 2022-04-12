
const BaseURL = 'http://localhost:8000';
export const GetVehicles = `${BaseURL}/vehicles/`;
export const GetForecast = (vehicleID) => `${GetVehicles}${vehicleID}/forecast/`
