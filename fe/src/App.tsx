import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import SearchPage from "@/pages/SearchPage";
import HospitalDetailPage from "@/pages/HospitalDetailPage";
import MapPage from "@/pages/MapPage";
import InsightsPage from "@/pages/InsightsPage";

// 라우팅을 글로벌 셸(AppShell)로 감싼다.
// 셸은 헤더 + sticky 검색바 + 리스트/지도 토글 + 본문 컨테이너를 일괄 제공.
// 페이지 컴포넌트는 제 영역에 집중하면 된다.
export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/search" replace />} />
        <Route path="/search" element={<SearchPage />} />
        <Route
          path="/hospitals/:hospitalId"
          element={<HospitalDetailPage />}
        />
        <Route path="/map" element={<MapPage />} />
        <Route path="/insights" element={<InsightsPage />} />
        <Route
          path="*"
          element={
            <div className="py-20 text-center text-muted-foreground">
              페이지를 찾을 수 없습니다.
            </div>
          }
        />
      </Route>
    </Routes>
  );
}
