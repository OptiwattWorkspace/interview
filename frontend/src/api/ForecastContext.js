import { createContext, useState, useEffect } from 'react';
import { GetForecast } from './endpoints';
import axios from 'axios';


export const ForecastContext = createContext({
  forecast: [],
  fetch: () => { }
});


export const ForecastContextProvider = ({ children }) => {
  const [data, setData] = useState([]);

  const fetchForecast = async () => {
    const response = await axios.get(GetForecast);
    setData(response.data);
  }

  useEffect(() => {
    fetchForecast();
  }, [])

  const { Provider } = ForecastContext;
  return (
    <Provider value={{forecast: data, fetch: fetchForecast}}>
      {children}
    </Provider>
  )
}