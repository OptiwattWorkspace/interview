import React, { memo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';


const formatChargeStartTime = (startTimeStr) => {
  const date = new Date(startTimeStr);
  const hourSuffix = date.getHours() > 12 ? 'PM' : 'AM';
  const hour = date.getHours() % 12;
  return [0, 3, 6, 9].includes(hour) ? `${hour === 0 ? 12 : hour}${hourSuffix}` : '';
}

const barFill = percent => `rgba(175, 75, 251, ${percent/100})`;

const ForecastChart = ({ periods }) => {
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
        <XAxis dataKey="start_time" tickFormatter={formatChargeStartTime} />
        <YAxis />
        <Tooltip />
        <Legend />
        <Bar dataKey="estimated_battery_pct">
          {
            periods && periods.map((period, index) => <Cell key={index} fill={barFill(period.estimated_battery_pct)} />)
          }
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};

export default ForecastChart;
