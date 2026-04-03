import { useState, useEffect } from 'react';
import api from '../api';
import GameCard from '../components/GameCard';

export default function Schedule() {
  const [games, setGames] = useState([]);
  const [teams, setTeams] = useState([]);
  const [week, setWeek] = useState(1);
  const [teamFilter, setTeamFilter] = useState('');
  const [oddsMap, setOddsMap] = useState({});

  useEffect(() => {
    api.get('/schedule/teams').then((res) => setTeams(res.data)).catch(() => {});
  }, []);

  useEffect(() => {
    const params = { week };
    if (teamFilter) params.team = teamFilter;
    api.get('/schedule/games', { params }).then((res) => {
      setGames(res.data);
      // Fetch latest odds for each game
      res.data.forEach((game) => {
        api.get(`/odds/game/${game.id}/latest`).then((oddsRes) => {
          setOddsMap((prev) => ({ ...prev, [game.id]: oddsRes.data }));
        }).catch(() => {});
      });
    }).catch(() => {});
  }, [week, teamFilter]);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Schedule</h1>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setWeek(Math.max(1, week - 1))}
              className="bg-gray-800 border border-gray-700 text-gray-300 px-3 py-1.5 rounded text-sm cursor-pointer hover:bg-gray-700"
            >
              &larr;
            </button>
            <span className="text-sm font-medium min-w-[80px] text-center">Week {week}</span>
            <button
              onClick={() => setWeek(Math.min(18, week + 1))}
              className="bg-gray-800 border border-gray-700 text-gray-300 px-3 py-1.5 rounded text-sm cursor-pointer hover:bg-gray-700"
            >
              &rarr;
            </button>
          </div>
          <select
            value={teamFilter}
            onChange={(e) => setTeamFilter(e.target.value)}
            className="bg-gray-800 border border-gray-700 text-gray-300 px-3 py-1.5 rounded text-sm"
          >
            <option value="">All Teams</option>
            {teams.map((t) => (
              <option key={t.id} value={t.abbreviation}>{t.abbreviation} — {t.name}</option>
            ))}
          </select>
        </div>
      </div>

      {games.length === 0 ? (
        <div className="text-center text-gray-500 py-20">
          <p className="text-lg">No games found for Week {week}</p>
          <p className="text-sm mt-2">Try fetching schedule data first</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {games.map((game) => (
            <GameCard key={game.id} game={game} odds={oddsMap[game.id]} />
          ))}
        </div>
      )}
    </div>
  );
}
