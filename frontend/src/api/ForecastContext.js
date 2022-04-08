import { createContext, useState, useEffect } from 'react';
import { GetForecast } from './endpoints';
import axios from 'axios';


export const ForecastContext = createContext({
  forecast: [],
  fetch: () => { }
});


export const ForecastContextProvider = ({ children }) => {
  const [forecast, setForecast] = useState([]);

  const fetchForecast = async () => {
    const response = await axios.get(GetForecast);
    setForecast(response.data);
  }

  useEffect(() => {
    fetchForecast();
  }, [])

  const { Provider } = ForecastContext;
  return (
    <Provider value={{forecast, fetchForecast}}>
      {children}
    </Provider>
  )
}