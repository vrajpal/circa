function fmt(val, decimals = 1) {
  if (val == null) return '—';
  return Number(val).toFixed(decimals);
}

function record(standing) {
  if (!standing) return '—';
  const { wins = 0, losses = 0, ties = 0 } = standing;
  return ties > 0 ? `${wins}-${losses}-${ties}` : `${wins}-${losses}`;
}

function StatRow({ label, away, home, inverse = false }) {
  const awayVal = parseFloat(away);
  const homeVal = parseFloat(home);
  const bothValid = !isNaN(awayVal) && !isNaN(homeVal) && awayVal !== homeVal;

  let awayHighlight = '';
  let homeHighlight = '';
  if (bothValid) {
    const awayBetter = inverse ? awayVal < homeVal : awayVal > homeVal;
    awayHighlight = awayBetter ? 'text-emerald-400' : '';
    homeHighlight = awayBetter ? '' : 'text-emerald-400';
  }

  return (
    <div className="grid grid-cols-3 py-1.5 text-sm border-b border-gray-800/50 last:border-0">
      <span className={`text-right pr-4 ${awayHighlight}`}>{away}</span>
      <span className="text-center text-gray-500 text-xs">{label}</span>
      <span className={`text-left pl-4 ${homeHighlight}`}>{home}</span>
    </div>
  );
}

export default function MatchupStats({ matchup }) {
  if (!matchup) return null;

  const { away_team, home_team, away_stats, home_stats, away_standing, home_standing } = matchup;
  const noStats = !away_stats && !home_stats;

  if (noStats) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mt-4">
        <p className="text-sm text-gray-500 text-center">No team stats available yet.</p>
      </div>
    );
  }

  const a = away_stats || {};
  const h = home_stats || {};

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mt-4">
      {/* Header */}
      <div className="grid grid-cols-3 mb-4">
        <div className="text-right pr-4">
          <span className="font-bold text-lg">{away_team.abbreviation}</span>
          <p className="text-xs text-gray-500">{record(away_standing)}</p>
        </div>
        <div className="text-center text-xs text-gray-500 self-center">
          Week {matchup.week} Stats
        </div>
        <div className="text-left pl-4">
          <span className="font-bold text-lg">{home_team.abbreviation}</span>
          <p className="text-xs text-gray-500">{record(home_standing)}</p>
        </div>
      </div>

      {/* Offense */}
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1 mt-2">Offense</p>
      <StatRow label="PPG" away={fmt(a.points_per_game)} home={fmt(h.points_per_game)} />
      <StatRow label="YPG" away={fmt(a.total_yards_per_game)} home={fmt(h.total_yards_per_game)} />
      <StatRow label="Pass YPG" away={fmt(a.passing_yards_per_game)} home={fmt(h.passing_yards_per_game)} />
      <StatRow label="Rush YPG" away={fmt(a.rushing_yards_per_game)} home={fmt(h.rushing_yards_per_game)} />
      <StatRow label="TO/G" away={fmt(a.turnovers_per_game)} home={fmt(h.turnovers_per_game)} inverse />
      <StatRow label="RZ TD%" away={fmt(a.red_zone_td_pct)} home={fmt(h.red_zone_td_pct)} />
      <StatRow label="3rd Down%" away={fmt(a.third_down_pct)} home={fmt(h.third_down_pct)} />

      {/* Defense */}
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1 mt-4">Defense</p>
      <StatRow label="PPG Allowed" away={fmt(a.points_allowed_per_game)} home={fmt(h.points_allowed_per_game)} inverse />
      <StatRow label="YPG Allowed" away={fmt(a.yards_allowed_per_game)} home={fmt(h.yards_allowed_per_game)} inverse />
      <StatRow label="Pass YPG Allowed" away={fmt(a.passing_yards_allowed_per_game)} home={fmt(h.passing_yards_allowed_per_game)} inverse />
      <StatRow label="Rush YPG Allowed" away={fmt(a.rushing_yards_allowed_per_game)} home={fmt(h.rushing_yards_allowed_per_game)} inverse />
      <StatRow label="Sacks/G" away={fmt(a.sacks_per_game)} home={fmt(h.sacks_per_game)} />
      <StatRow label="Takeaways/G" away={fmt(a.takeaways_per_game)} home={fmt(h.takeaways_per_game)} />

      {/* Situational */}
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1 mt-4">Situational</p>
      <StatRow label="Pt Diff/G" away={fmt(a.point_differential_per_game)} home={fmt(h.point_differential_per_game)} />

      {/* Standings detail */}
      {(away_standing || home_standing) && (
        <>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1 mt-4">Standings</p>
          <StatRow label="Home" away={away_standing ? `${away_standing.away_wins ?? 0}-${away_standing.away_losses ?? 0}` : '—'} home={home_standing ? `${home_standing.home_wins ?? 0}-${home_standing.home_losses ?? 0}` : '—'} />
          <StatRow label="Div Rank" away={away_standing?.division_rank ?? '—'} home={home_standing?.division_rank ?? '—'} inverse />
          <StatRow label="SOS" away={fmt(away_standing?.strength_of_schedule, 3)} home={fmt(home_standing?.strength_of_schedule, 3)} />
        </>
      )}
    </div>
  );
}
