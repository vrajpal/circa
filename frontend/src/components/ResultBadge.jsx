// Small W/L/P pill for a graded pick. Renders nothing while the pick is still
// "pending" (the game hasn't been graded yet).
const STYLES = {
  win: 'bg-emerald-900/50 text-emerald-400',
  loss: 'bg-red-900/50 text-red-400',
  push: 'bg-gray-700 text-gray-300',
};

const LABELS = { win: 'W', loss: 'L', push: 'P' };

export default function ResultBadge({ result }) {
  if (!result || result === 'pending') return null;
  const style = STYLES[result] || 'bg-gray-700 text-gray-300';
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${style}`}>
      {LABELS[result] || result}
    </span>
  );
}
