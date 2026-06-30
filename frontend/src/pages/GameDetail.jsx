import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api';
import OddsChart from '../components/OddsChart';
import MatchupStats from '../components/MatchupStats';

function formatSpread(val) {
  if (val == null) return '—';
  return val > 0 ? `+${val}` : `${val}`;
}

function formatMoneyline(val) {
  if (val == null) return '—';
  return val > 0 ? `+${val}` : `${val}`;
}

export default function GameDetail() {
  const { id } = useParams();
  const [game, setGame] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [matchup, setMatchup] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    api.get(`/schedule/games/${id}`).then((res) => {
      setGame(res.data);
      const g = res.data;
      api.get('/team-stats/matchup', {
        params: { home: g.home_team.abbreviation, away: g.away_team.abbreviation, season: g.season, week: g.week }
      }).then((r) => setMatchup(r.data)).catch(() => {});
    }).catch(() => {});
    api.get(`/odds/game/${id}`).then((res) => setSnapshots(res.data)).catch(() => {});
    api.get(`/schedule/games/${id}/result`).then((res) => setResult(res.data)).catch(() => {});
  }, [id]);

  if (!game) return <div className="p-6 text-gray-500">Loading...</div>;

  const opening = snapshots.filter((s) => s.is_opening);
  const closing = snapshots.find((s) => s.line_type === 'closing');
  const latest = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null;
  const graded = result && result.id;

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

        {/* Final result (shown once the game has been graded) */}
        {graded && (
          <div className="mb-6 bg-gray-800/50 border border-gray-700 rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-2">Final</p>
            <div className="flex items-center gap-6">
              <p className="text-2xl font-bold">
                {game.away_team.abbreviation} {game.score_away ?? '—'} &ndash; {game.score_home ?? '—'} {game.home_team.abbreviation}
              </p>
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              <span className="bg-gray-900 border border-gray-700 rounded px-2 py-1">
                SU: <span className="text-gray-100 font-medium">{result.su_winner?.abbreviation ?? 'Tie'}</span>
              </span>
              <span className="bg-gray-900 border border-gray-700 rounded px-2 py-1">
                ATS (vs {formatSpread(result.closing_spread_home)}):{' '}
                <span className="text-emerald-400 font-medium">{result.ats_winner?.abbreviation ?? 'Push'}</span>
              </span>
              {result.total_result && (
                <span className="bg-gray-900 border border-gray-700 rounded px-2 py-1">
                  Total (vs {result.closing_total ?? '—'}):{' '}
                  <span className="text-blue-400 font-medium capitalize">{result.total_result}</span>
                </span>
              )}
            </div>
          </div>
        )}

        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-gray-800/50 rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-1">Opening Line</p>
            <p className="text-lg font-medium">{formatSpread(opening[0]?.spread_home)}</p>
            <p className="text-xs text-gray-500">{opening[0]?.source}</p>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-1">Current Line</p>
            <p className="text-lg font-medium">{formatSpread(latest?.spread_home)}</p>
            <p className="text-xs text-gray-500">{latest?.source}</p>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-1">Closing Line</p>
            <p className="text-lg font-medium">{formatSpread(closing?.spread_home)}</p>
            {closing && (
              <p className="text-xs text-gray-500 flex items-center gap-1 flex-wrap">
                <span>
                  ML {formatMoneyline(closing.moneyline_home)} / {formatMoneyline(closing.moneyline_away)}
                </span>
                {closing.moneyline_derived && (
                  <span
                    className="bg-amber-900/50 text-amber-400 px-1.5 py-0.5 rounded text-[10px]"
                    title="Moneyline derived from the spread (model estimate), not a real book price"
                  >
                    derived
                  </span>
                )}
              </p>
            )}
          </div>
        </div>

        <OddsChart snapshots={snapshots} />
      </div>

      <MatchupStats matchup={matchup} />
    </div>
  );
}
