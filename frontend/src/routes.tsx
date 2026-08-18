import { Navigate, Route, Routes } from 'react-router-dom';

import FeedPage from './pages/FeedPage';
import LoginPage from './pages/LoginPage';

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/feed" element={<FeedPage />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}