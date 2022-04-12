import './Vehicles.css'

import { useContext, useState } from 'react';
import { VehiclesContext } from '../../api/VehiclesContext';
import Card from '../Card';


const Vehicles = ({ selectedVehicleID, setSelectedVehicleID }) => {
  const { vehicles } = useContext(VehiclesContext);

  const onVehicleRadioChange = (e) => {
    console.log(parseInt(e.target.value))
    setSelectedVehicleID(parseInt(e.target.value));
  }

  return (
    <div className='vehiclesContentContainer'>
      {
        vehicles.map(vehicle => (
          <div className='vehiclesItem' key={vehicle.id}>
            <Card title={vehicle.friendly_name} className='vehicleCard'>
              <div className='vehiclesItemContent'>
                <img src={`/${vehicle.friendly_name}.png`} alt={vehicle.friendly_name} className='vehicleImage' />
                <input
                  type="radio"
                  value={vehicle.id}
                  checked={selectedVehicleID === vehicle.id}
                  onChange={onVehicleRadioChange}
                />
              </div>
            </Card>
          </div>
        ))
      }
    </div>
  );
}

export default Vehicles;
