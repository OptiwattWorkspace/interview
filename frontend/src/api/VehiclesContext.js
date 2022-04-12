import { createContext, useState, useEffect } from 'react';
import { GetVehicles } from './endpoints';
import axios from 'axios';


export const VehiclesContext = createContext([]);


export const VehiclesContextProvider = ({ children }) => {
  const [vehicles, setVehicles] = useState([]);

  const fetchVehicles = async () => {
    const response = await axios.get(GetVehicles);
    setVehicles(response.data);
  };

  useEffect(() => {
    fetchVehicles();
  }, []);

  const { Provider } = VehiclesContext;
  return (
    <Provider value={{vehicles, fetchVehicles}}>
      {children}
    </Provider>
  );
};
