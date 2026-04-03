import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import Login from './pages/Login';
import Schedule from './pages/Schedule';
import GameDetail from './pages/GameDetail';
import Picks from './pages/Picks';
import Consensus from './pages/Consensus';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-6 text-gray-500">Loading...</div>;
  return user ? children : <Navigate to="/login" />;
}

function AppRoutes() {
  const { user, loading } = useAuth();

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>;

  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/schedule" /> : <Login />} />
        <Route path="/schedule" element={<ProtectedRoute><Schedule /></ProtectedRoute>} />
        <Route path="/game/:id" element={<ProtectedRoute><GameDetail /></ProtectedRoute>} />
        <Route path="/picks" element={<ProtectedRoute><Picks /></ProtectedRoute>} />
        <Route path="/consensus" element={<ProtectedRoute><Consensus /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/schedule" />} />
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
