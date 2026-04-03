import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export default function OddsChart({ snapshots }) {
  if (!snapshots || snapshots.length === 0) {
    return <p className="text-gray-500 text-sm">No odds data available</p>;
  }

  // Group by source, build chart data by time
  const bySource = {};
  for (const snap of snapshots) {
    if (!bySource[snap.source]) bySource[snap.source] = [];
    bySource[snap.source].push({
      time: new Date(snap.captured_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric' }),
      spread: snap.spread_home,
      total: snap.total,
    });
  }

  const sources = Object.keys(bySource);
  const colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6'];

  // Flatten into chart data with source-keyed spread values
  const timeMap = new Map();
  for (const snap of snapshots) {
    const time = new Date(snap.captured_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric' });
    if (!timeMap.has(time)) timeMap.set(time, { time });
    timeMap.get(time)[`${snap.source}_spread`] = snap.spread_home;
    timeMap.get(time)[`${snap.source}_total`] = snap.total;
  }
  const chartData = Array.from(timeMap.values());

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium text-gray-400 mb-2">Spread (Home)</h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData}>
            <XAxis dataKey="time" tick={{ fontSize: 11, fill: '#6b7280' }} />
            <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} domain={['auto', 'auto']} />
            <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 8 }} />
            <Legend />
            {sources.map((src, i) => (
              <Line
                key={src}
                type="monotone"
                dataKey={`${src}_spread`}
                name={src}
                stroke={colors[i % colors.length]}
                dot={false}
                strokeWidth={2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div>
        <h3 className="text-sm font-medium text-gray-400 mb-2">Total (O/U)</h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData}>
            <XAxis dataKey="time" tick={{ fontSize: 11, fill: '#6b7280' }} />
            <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} domain={['auto', 'auto']} />
            <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 8 }} />
            <Legend />
            {sources.map((src, i) => (
              <Line
                key={src}
                type="monotone"
                dataKey={`${src}_total`}
                name={src}
                stroke={colors[i % colors.length]}
                dot={false}
                strokeWidth={2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
