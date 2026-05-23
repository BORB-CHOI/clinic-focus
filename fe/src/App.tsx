import { Link, Navigate, Route, Routes } from "react-router-dom";

import SearchPage from "@/pages/SearchPage";
import HospitalDetailPage from "@/pages/HospitalDetailPage";
import MapPage from "@/pages/MapPage";

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="container flex h-14 items-center justify-between">
          <Link to="/search" className="text-lg font-semibold">
            clinic-focus
          </Link>
          <nav className="flex gap-4 text-sm text-muted-foreground">
            <Link to="/search" className="hover:text-foreground">
              검색
            </Link>
            <Link to="/map" className="hover:text-foreground">
              지도
            </Link>
          </nav>
        </div>
      </header>

      <main className="container py-6">
        <Routes>
          <Route path="/" element={<Navigate to="/search" replace />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/hospitals/:hospitalId" element={<HospitalDetailPage />} />
          <Route path="/map" element={<MapPage />} />
          <Route
            path="*"
            element={
              <div className="py-20 text-center text-muted-foreground">
                페이지를 찾을 수 없습니다.
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  );
}
