import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import api from '../api';
import GameCard from '../components/GameCard';
import SurvivorTracker from '../components/SurvivorTracker';

export default function Picks() {
  const { user } = useAuth();
  const [week, setWeek] = useState(1);
  const [contestType, setContestType] = useState('millions');
  const [games, setGames] = useState([]);
  const [picks, setPicks] = useState([]);
  const [oddsMap, setOddsMap] = useState({});
  const [comment, setComment] = useState('');
  const [pendingPick, setPendingPick] = useState(null);
  const [warning, setWarning] = useState(null);

  useEffect(() => {
    api.get('/schedule/games', { params: { week } }).then((res) => {
      setGames(res.data);
      res.data.forEach((game) => {
        api.get(`/odds/game/${game.id}/latest`).then((oddsRes) => {
          setOddsMap((prev) => ({ ...prev, [game.id]: oddsRes.data }));
        }).catch(() => {});
      });
    }).catch(() => {});
  }, [week]);

  useEffect(() => {
    api.get('/picks/', { params: { week, contest_type: contestType, user_id: user?.id } })
      .then((res) => setPicks(res.data))
      .catch(() => {});
  }, [week, contestType, user]);

  const handlePick = async (game, team) => {
    // Check slate warning for survivor
    if (contestType === 'survivor') {
      try {
        const warnRes = await api.get('/picks/survivor/slate-warning', { params: { picked_team_id: team.id } });
        if (warnRes.data) {
          setWarning(warnRes.data);
        } else {
          setWarning(null);
        }
      } catch { setWarning(null); }
    }
    setPendingPick({ game, team });
  };

  const confirmPick = async () => {
    if (!pendingPick) return;
    try {
      await api.post('/picks/', {
        game_id: pendingPick.game.id,
        picked_team_id: pendingPick.team.id,
        contest_type: contestType,
        comment: comment || null,
      });
      // Refresh picks
      const res = await api.get('/picks/', { params: { week, contest_type: contestType, user_id: user?.id } });
      setPicks(res.data);
      setPendingPick(null);
      setComment('');
      setWarning(null);
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to save pick');
    }
  };

  const myPickForGame = (gameId) => picks.find((p) => p.game?.id === gameId);

  const millionsPicks = picks.filter((p) => p.contest_type === 'millions');

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">My Picks</h1>
        <div className="flex items-center gap-4">
          <div className="flex bg-gray-800 rounded-lg overflow-hidden">
            <button
              onClick={() => setContestType('millions')}
              className={`px-4 py-2 text-sm border-0 cursor-pointer ${
                contestType === 'millions' ? 'bg-emerald-600 text-white' : 'bg-transparent text-gray-400'
              }`}
            >
              Millions ({millionsPicks.length}/5)
            </button>
            <button
              onClick={() => setContestType('survivor')}
              className={`px-4 py-2 text-sm border-0 cursor-pointer ${
                contestType === 'survivor' ? 'bg-emerald-600 text-white' : 'bg-transparent text-gray-400'
              }`}
            >
              Survivor
            </button>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setWeek(Math.max(1, week - 1))}
              className="bg-gray-800 border border-gray-700 text-gray-300 px-3 py-1.5 rounded text-sm cursor-pointer"
            >
              &larr;
            </button>
            <span className="text-sm font-medium min-w-[80px] text-center">Week {week}</span>
            <button
              onClick={() => setWeek(Math.min(18, week + 1))}
              className="bg-gray-800 border border-gray-700 text-gray-300 px-3 py-1.5 rounded text-sm cursor-pointer"
            >
              &rarr;
            </button>
          </div>
        </div>
      </div>

      {contestType === 'survivor' && <SurvivorTracker />}

      {/* Pending pick confirmation */}
      {pendingPick && (
        <div className="mb-6 bg-gray-900 border border-emerald-800 rounded-lg p-4">
          <p className="text-sm mb-2">
            Pick <strong className="text-emerald-400">{pendingPick.team.abbreviation}</strong> in{' '}
            {pendingPick.game.away_team.abbreviation} @ {pendingPick.game.home_team.abbreviation}?
          </p>
          {warning && (
            <div className="mb-3 bg-amber-900/30 border border-amber-800 rounded-lg p-3">
              <p className="text-sm text-amber-400">{warning.message}</p>
              {warning.remaining_teams?.length > 0 && (
                <p className="text-xs text-amber-500 mt-1">
                  Remaining: {warning.remaining_teams.map((t) => t.abbreviation).join(', ')}
                </p>
              )}
            </div>
          )}
          <textarea
            placeholder="Why this pick? (optional)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 mb-2 resize-none"
            rows={2}
          />
          <div className="flex gap-2">
            <button
              onClick={confirmPick}
              className="bg-emerald-600 hover:bg-emerald-500 text-white text-sm px-4 py-1.5 rounded border-0 cursor-pointer"
            >
              Confirm
            </button>
            <button
              onClick={() => { setPendingPick(null); setWarning(null); setComment(''); }}
              className="bg-transparent border border-gray-700 text-gray-400 text-sm px-4 py-1.5 rounded cursor-pointer hover:border-gray-500"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {games.length === 0 ? (
        <div className="text-center text-gray-500 py-20">
          <p>No games for Week {week}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {games.map((game) => (
            <GameCard
              key={game.id}
              game={game}
              odds={oddsMap[game.id]}
              pickMode
              userPick={myPickForGame(game.id)}
              onPick={handlePick}
            />
          ))}
        </div>
      )}
    </div>
  );
}
