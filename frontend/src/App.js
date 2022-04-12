import './App.css';

import { ForecastContextProvider } from './api/ForecastContext';
import { VehiclesContextProvider } from './api/VehiclesContext';
import Dashboard from './components/Dashboard';


function App() {
  return (
    <VehiclesContextProvider>
      <ForecastContextProvider>
        <div className='app'>
          <div className='appContainer'>
            <Dashboard />
          </div>
        </div>
      </ForecastContextProvider>
    </VehiclesContextProvider>
  );
}

export default App;
