import { createContext, useState, useEffect } from 'react';
import { GetForecast } from './endpoints';
import axios from 'axios';


export const ForecastContext = createContext({
  forecasts: [],
  fetchForecast: (relatedVehicleID) => { }
});


export const ForecastContextProvider = ({ children }) => {
  const [forecasts, setForecasts] = useState([]);

  const fetchForecast = async (relatedVehicleID) => {
    const response = await axios.get(GetForecast(relatedVehicleID));
    setForecasts(forecasts.concat(response.data));
  };
  
  const { Provider } = ForecastContext;
  return (
    <Provider value={{forecasts, fetchForecast}}>
      {children}
    </Provider>
  );
}