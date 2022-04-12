import { useState } from 'react';
import Forecast from '../Forecast';
import Vehicles from '../Vehicles';


const Dashboard = () => {
  const [ selectedVehicleID, setSelectedVehicleID ] = useState();

  return (
    <>
      <Vehicles selectedVehicleID={selectedVehicleID} setSelectedVehicleID={setSelectedVehicleID} />
      <Forecast relatedVehicleID={selectedVehicleID} />
    </>
  );
}

export default Dashboard;
