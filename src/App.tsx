import { Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Home from './pages/Home';
import Timeline from './pages/Timeline';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import { ToastProvider } from './hooks/useToast';

export default function App() {
  return (
    <ToastProvider>
      <div className="flex h-screen w-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto bg-canvas">
          <Routes>
            <Route path="/" element={<Navigate to="/home" replace />} />
            <Route path="/home" element={<Home />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/home" replace />} />
          </Routes>
        </main>
      </div>
    </ToastProvider>
  );
}
