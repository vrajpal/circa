import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  { path: '/schedule', label: 'Schedule' },
  { path: '/picks', label: 'Picks' },
  { path: '/consensus', label: 'Consensus' },
  { path: '/logs', label: 'Logs' },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const location = useLocation();

  return (
    <nav className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <Link to="/" className="text-xl font-bold text-emerald-400 no-underline">
          CIRCA
        </Link>
        {user && NAV_ITEMS.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`text-sm no-underline ${
              location.pathname === item.path
                ? 'text-emerald-400 font-medium'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            {item.label}
          </Link>
        ))}
      </div>
      {user && (
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-400">{user.username}</span>
          <button
            onClick={logout}
            className="text-sm text-gray-500 hover:text-gray-300 bg-transparent border-0 cursor-pointer"
          >
            Logout
          </button>
        </div>
      )}
    </nav>
  );
}
