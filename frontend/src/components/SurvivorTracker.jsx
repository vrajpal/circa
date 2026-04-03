import { useState, useEffect } from 'react';
import api from '../api';

export default function SurvivorTracker() {
  const [usedTeams, setUsedTeams] = useState([]);

  useEffect(() => {
    api.get('/picks/survivor/used').then((res) => setUsedTeams(res.data)).catch(() => {});
  }, []);

  if (usedTeams.length === 0) return null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-2">Used Survivor Teams</h3>
      <div className="flex flex-wrap gap-2">
        {usedTeams.map((team) => (
          <span
            key={team.id}
            className="text-xs bg-red-900/40 text-red-400 px-2 py-1 rounded"
          >
            {team.abbreviation}
          </span>
        ))}
      </div>
      <p className="text-xs text-gray-500 mt-2">{32 - usedTeams.length} teams remaining</p>
    </div>
  );
}
