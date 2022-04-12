import './Forecast.css';

import { useContext, useEffect } from 'react';
import { ForecastContext } from '../../api/ForecastContext';
import ForecastChart from '../ForecastChart';
import Card from '../Card';


const ForecastResponses = ({ periods, vehicle }) => {
  return (
    <div className='responses'>
      <div>
        <Card title='Vehicle'>
          <pre>
            {JSON.stringify(vehicle, null, 2)}
          </pre>
        </Card>
      </div>
      <div>
        <Card title='Periods'>
          <pre>
            {JSON.stringify(periods, null, 2)}
          </pre>
        </Card>
      </div>
    </div>
  );
}


const ForecastChartCard = ({ periods, vehicle }) => {
  return (
    <Card title='ChargeForecast'>
      <div className="chartContainer">
        <ForecastChart periods={periods} vehicle={vehicle} />
      </div>
    </Card>
  );
}


const Forecast = ({ relatedVehicleID }) => {
  const { forecasts, fetchForecast } = useContext(ForecastContext);

  const forecast = forecasts.find(forecast => forecast.vehicle.id === relatedVehicleID);

  useEffect(() => {
    if (!forecast && relatedVehicleID) {
      fetchForecast(relatedVehicleID);
    }
  }, [forecast, relatedVehicleID])

  if (!forecast) {
    return (<></>)
  }

  return (
    <div>
      <ForecastChartCard {...forecast} />
      <ForecastResponses {...forecast} />
    </div>
  );
}

export default Forecast;
