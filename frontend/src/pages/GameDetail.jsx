import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api';
import OddsChart from '../components/OddsChart';
import MatchupStats from '../components/MatchupStats';

export default function GameDetail() {
  const { id } = useParams();
  const [game, setGame] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [matchup, setMatchup] = useState(null);

  useEffect(() => {
    api.get(`/schedule/games/${id}`).then((res) => {
      setGame(res.data);
      const g = res.data;
      api.get('/team-stats/matchup', {
        params: { home: g.home_team.abbreviation, away: g.away_team.abbreviation, season: g.season, week: g.week }
      }).then((r) => setMatchup(r.data)).catch(() => {});
    }).catch(() => {});
    api.get(`/odds/game/${id}`).then((res) => setSnapshots(res.data)).catch(() => {});
  }, [id]);

  if (!game) return <div className="p-6 text-gray-500">Loading...</div>;

  const opening = snapshots.filter((s) => s.is_opening);
  const latest = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <Link to="/schedule" className="text-sm text-gray-500 hover:text-gray-300 no-underline">&larr; Back to Schedule</Link>

      <div className="mt-4 bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold">{game.away_team.abbreviation} @ {game.home_team.abbreviation}</h1>
            <p className="text-sm text-gray-500">
              Week {game.week} &middot; {new Date(game.game_time).toLocaleString('en-US', {
                weekday: 'long', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit'
              })}
            </p>
          </div>
          {game.slate !== 'regular' && (
            <span className="bg-amber-900/50 text-amber-400 px-3 py-1 rounded text-sm">{game.slate}</span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-gray-800/50 rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-1">Opening Line</p>
            <p className="text-lg font-medium">
              {opening.length > 0 ? (opening[0].spread_home > 0 ? `+${opening[0].spread_home}` : opening[0].spread_home) : '—'}
            </p>
            <p className="text-xs text-gray-500">{opening[0]?.source}</p>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-1">Current Line</p>
            <p className="text-lg font-medium">
              {latest ? (latest.spread_home > 0 ? `+${latest.spread_home}` : latest.spread_home) : '—'}
            </p>
            <p className="text-xs text-gray-500">{latest?.source}</p>
          </div>
        </div>

        <OddsChart snapshots={snapshots} />
      </div>

      <MatchupStats matchup={matchup} />
    </div>
  );
}
