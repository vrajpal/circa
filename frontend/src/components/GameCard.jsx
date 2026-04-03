import { Link } from 'react-router-dom';

function formatSpread(val) {
  if (val == null) return '—';
  return val > 0 ? `+${val}` : `${val}`;
}

function formatTime(dt) {
  return new Date(dt).toLocaleString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export default function GameCard({ game, odds, onPick, pickMode, userPick }) {
  const latestOdds = odds?.[0];

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-700 transition-colors">
      <div className="flex justify-between items-start mb-2">
        <span className="text-xs text-gray-500">{formatTime(game.game_time)}</span>
        {game.slate !== 'regular' && (
          <span className="text-xs bg-amber-900/50 text-amber-400 px-2 py-0.5 rounded">
            {game.slate}
          </span>
        )}
      </div>

      <Link to={`/game/${game.id}`} className="no-underline">
        <div className="space-y-2">
          <div className={`flex justify-between items-center ${
            pickMode && userPick?.picked_team?.id === game.away_team.id ? 'bg-emerald-900/30 -mx-2 px-2 py-1 rounded' : ''
          }`}>
            <span className="font-medium text-gray-100">{game.away_team.abbreviation}</span>
            <span className="text-sm text-gray-400">
              {latestOdds ? formatSpread(-(latestOdds.spread_home)) : '—'}
            </span>
          </div>
          <div className={`flex justify-between items-center ${
            pickMode && userPick?.picked_team?.id === game.home_team.id ? 'bg-emerald-900/30 -mx-2 px-2 py-1 rounded' : ''
          }`}>
            <span className="font-medium text-gray-100">{game.home_team.abbreviation}</span>
            <span className="text-sm text-gray-400">
              {latestOdds ? formatSpread(latestOdds.spread_home) : '—'}
            </span>
          </div>
        </div>
      </Link>

      {latestOdds && (
        <div className="mt-2 pt-2 border-t border-gray-800 flex justify-between text-xs text-gray-500">
          <span>O/U {latestOdds.total ?? '—'}</span>
          <span>{latestOdds.source}</span>
        </div>
      )}

      {pickMode && onPick && (
        <div className="mt-3 flex gap-2">
          <button
            onClick={() => onPick(game, game.away_team)}
            className={`flex-1 text-xs py-1.5 rounded border cursor-pointer transition-colors ${
              userPick?.picked_team?.id === game.away_team.id
                ? 'bg-emerald-600 border-emerald-600 text-white'
                : 'bg-transparent border-gray-700 text-gray-400 hover:border-gray-500'
            }`}
          >
            {game.away_team.abbreviation}
          </button>
          <button
            onClick={() => onPick(game, game.home_team)}
            className={`flex-1 text-xs py-1.5 rounded border cursor-pointer transition-colors ${
              userPick?.picked_team?.id === game.home_team.id
                ? 'bg-emerald-600 border-emerald-600 text-white'
                : 'bg-transparent border-gray-700 text-gray-400 hover:border-gray-500'
            }`}
          >
            {game.home_team.abbreviation}
          </button>
        </div>
      )}
    </div>
  );
}
