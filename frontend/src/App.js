import './App.css';

import { ForecastContextProvider } from './api/ForecastContext';
import Forecast from './components/Forecast/';


function App() {
  return (
    <ForecastContextProvider>
      <div className='app'>
        <div className='appContainer'>
          <Forecast />
        </div>
      </div>
    </ForecastContextProvider>
  );
}

export default App;
