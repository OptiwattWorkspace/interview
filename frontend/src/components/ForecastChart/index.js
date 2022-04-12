import React, { memo } from 'react';
import { 
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
  ReferenceLine
} from 'recharts';


const formatChargeStartTime = (startTimeStr) => {
  const date = new Date(startTimeStr);
  const hourSuffix = date.getHours() > 12 ? 'PM' : 'AM';
  const hour = date.getHours() % 12;
  return [0, 3, 6, 9].includes(hour) ? `${hour === 0 ? 12 : hour}${hourSuffix}` : '';
}

const legendValues = [
  {
    color: '#AF4BFB',
    type: 'rect',
    value: 'Idle'
  },
  {
    color: '#97FB4B',
    type: 'rect',
    value: 'Charging'
  },
  {
    color: 'red',
    type: 'line',
    value: 'Target Charge'
  }
]

const ForecastChart = ({ periods, vehicle }) => {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart
        width={500}
        height={300}
        data={periods}
        margin={{
          top: 5,
          right: 30,
          left: 20,
          bottom: 5,
        }}
      >
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="start_time"
          angle={-25}
          textAnchor="end"
          tickFormatter={formatChargeStartTime}
          padding={{ bottom: 200 }}
        />
        <YAxis />
        <Tooltip />
        <Legend payload={legendValues} />
        <Bar dataKey="estimated_battery_pct" fill='#AF4BFB'>
          {
            periods && periods.map((period, index) => (
              <Cell key={index} fill={period.should_charge ? '#97FB4B' : '#AF4BFB'} />
            ))
          }
        </Bar>
        <ReferenceLine y={vehicle.target_battery_pct} stroke="red" strokeWidth={2} strokeDasharray="3 1" />
      </BarChart>
    </ResponsiveContainer>
  );
};

export default memo(ForecastChart);
