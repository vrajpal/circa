import { useState, useEffect } from 'react';
import api from '../api';

function formatSpread(val) {
  if (val == null) return '—';
  return val > 0 ? `+${val}` : `${val}`;
}

export default function Consensus() {
  const [week, setWeek] = useState(1);
  const [contestType, setContestType] = useState('millions');
  const [picks, setPicks] = useState([]);
  const [locked, setLocked] = useState([]);
  const [games, setGames] = useState([]);
  const [oddsMap, setOddsMap] = useState({});

  const fetchData = () => {
    api.get('/consensus/picks', { params: { week, contest_type: contestType } })
      .then((res) => setPicks(res.data)).catch(() => {});
    api.get('/consensus/locked', { params: { week, contest_type: contestType } })
      .then((res) => setLocked(res.data)).catch(() => {});
    api.get('/schedule/games', { params: { week } }).then((res) => {
      setGames(res.data);
      res.data.forEach((g) => {
        api.get(`/odds/game/${g.id}/latest`).then((r) => {
          setOddsMap((prev) => ({ ...prev, [g.id]: r.data }));
        }).catch(() => {});
      });
    }).catch(() => {});
  };

  useEffect(fetchData, [week, contestType]);

  // Group picks by game
  const picksByGame = {};
  for (const pick of picks) {
    const gid = pick.game?.id;
    if (!gid) continue;
    if (!picksByGame[gid]) picksByGame[gid] = [];
    picksByGame[gid].push(pick);
  }

  const lockPick = async (gameId, teamId) => {
    try {
      await api.post('/consensus/lock', { game_id: gameId, picked_team_id: teamId, contest_type: contestType }, { params: { week } });
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to lock pick');
    }
  };

  const unlockPick = async (pickId) => {
    try {
      await api.delete(`/consensus/lock/${pickId}`);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to unlock');
    }
  };

  const lockedGameIds = new Set(locked.map((l) => l.game?.id));

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Consensus</h1>
        <div className="flex items-center gap-4">
          <div className="flex bg-gray-800 rounded-lg overflow-hidden">
            <button
              onClick={() => setContestType('millions')}
              className={`px-4 py-2 text-sm border-0 cursor-pointer ${
                contestType === 'millions' ? 'bg-emerald-600 text-white' : 'bg-transparent text-gray-400'
              }`}
            >
              Millions
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

      {/* Locked picks summary */}
      {locked.length > 0 && (
        <div className="mb-6 bg-emerald-900/20 border border-emerald-800 rounded-lg p-4">
          <h2 className="text-sm font-medium text-emerald-400 mb-3">Locked Picks ({locked.length}{contestType === 'millions' ? '/5' : '/1'})</h2>
          <div className="flex flex-wrap gap-3">
            {locked.map((lp) => (
              <div key={lp.id} className="flex items-center gap-2 bg-emerald-900/30 rounded-lg px-3 py-2">
                <span className="font-medium text-sm">{lp.picked_team?.abbreviation}</span>
                {lp.game && (
                  <span className="text-xs text-gray-400">
                    {lp.game.away_team.abbreviation} @ {lp.game.home_team.abbreviation}
                  </span>
                )}
                <button
                  onClick={() => unlockPick(lp.id)}
                  className="text-xs text-red-400 hover:text-red-300 bg-transparent border-0 cursor-pointer ml-2"
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Per-game breakdown */}
      {games.length === 0 ? (
        <div className="text-center text-gray-500 py-20">
          <p>No games for Week {week}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {games.map((game) => {
            const gamePicks = picksByGame[game.id] || [];
            const odds = oddsMap[game.id]?.[0];
            const isLocked = lockedGameIds.has(game.id);

            // Count picks per team
            const teamCounts = {};
            for (const p of gamePicks) {
              const abbr = p.picked_team?.abbreviation;
              if (!teamCounts[abbr]) teamCounts[abbr] = { count: 0, teamId: p.picked_team?.id, users: [] };
              teamCounts[abbr].count++;
              teamCounts[abbr].users.push(p);
            }

            if (gamePicks.length === 0 && !isLocked) return null;

            return (
              <div
                key={game.id}
                className={`bg-gray-900 border rounded-lg p-4 ${
                  isLocked ? 'border-emerald-800' : 'border-gray-800'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="font-medium">
                      {game.away_team.abbreviation} @ {game.home_team.abbreviation}
                    </span>
                    {odds && (
                      <span className="text-sm text-gray-500">
                        Spread: {formatSpread(odds.spread_home)} | O/U: {odds.total ?? '—'}
                      </span>
                    )}
                  </div>
                  {isLocked && (
                    <span className="text-xs bg-emerald-900/50 text-emerald-400 px-2 py-0.5 rounded">LOCKED</span>
                  )}
                </div>

                {/* User picks */}
                <div className="space-y-2">
                  {gamePicks.map((p) => (
                    <div key={p.id} className="flex items-start gap-3 text-sm">
                      <span className="text-gray-500 min-w-[80px]">{p.user?.username}</span>
                      <span className={`font-medium ${
                        p.picked_team?.id === game.home_team.id ? 'text-blue-400' : 'text-orange-400'
                      }`}>
                        {p.picked_team?.abbreviation}
                      </span>
                      {p.comment && <span className="text-gray-500 italic">"{p.comment}"</span>}
                    </div>
                  ))}
                </div>

                {/* Lock buttons */}
                {!isLocked && gamePicks.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-800 flex gap-2">
                    {Object.entries(teamCounts).map(([abbr, data]) => (
                      <button
                        key={abbr}
                        onClick={() => lockPick(game.id, data.teamId)}
                        className="text-xs bg-gray-800 border border-gray-700 text-gray-300 px-3 py-1.5 rounded cursor-pointer hover:border-emerald-600 hover:text-emerald-400"
                      >
                        Lock {abbr} ({data.count}/{gamePicks.length} votes)
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
