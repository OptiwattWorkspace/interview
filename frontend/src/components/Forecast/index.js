import './Forecast.css';

import { useContext } from 'react';
import { ForecastContext } from '../../api/ForecastContext';
import ForecastChart from '../ForecastChart';


const ForecastResponses = ({ periods, vehicle }) => {
  return (
    <div className='responses'>
      <div>
        <div className='card'>
          <h1 className='cardHeader'>Vehicle</h1>
          <pre>
            {JSON.stringify(vehicle, null, 2)}
          </pre>
        </div>
      </div>
      <div>
        <div className='card'>
          <h1 className='cardHeader'>Periods</h1>
          <pre>
            {JSON.stringify(periods, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}


const ForecastChartCard = ({ periods }) => {
  return (
    <div className='card'>
      <h1 className='cardHeader'>Forecast</h1>
      <div className="chartContainer">
        <ForecastChart periods={periods} />
      </div>
    </div>
  );
}


const Forecast = () => {
  const { forecast, fetchForecast } = useContext(ForecastContext);

  const { periods, vehicle } = forecast;

  return (
    <div>
      <ForecastChartCard periods={periods} />
      <ForecastResponses {...forecast } />
    </div>
  );
}

export default Forecast;
