import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import TitleBar from './components/TitleBar';
import Sidebar from './components/Sidebar';
import Home from './pages/Home';
import Timeline from './pages/Timeline';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import { ToastProvider } from './hooks/useToast';

export default function App() {
  return (
    <ToastProvider>
      <div className="flex flex-col h-screen w-screen overflow-hidden bg-bg">
        <TitleBar />
        <div className="flex flex-1 min-h-0">
          <Sidebar />
          <main className="flex-1 overflow-y-auto bg-bg">
            <RoutesWithFade />
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}

/** 路由切换时整页 fade-in */
function RoutesWithFade() {
  const loc = useLocation();
  return (
    <div key={loc.pathname} className="animate-fadein h-full">
      <Routes location={loc}>
        <Route path="/" element={<Navigate to="/home" replace />} />
        <Route path="/home" element={<Home />} />
        <Route path="/timeline" element={<Timeline />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/home" replace />} />
      </Routes>
    </div>
  );
}
