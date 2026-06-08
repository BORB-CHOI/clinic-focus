import { Outlet, useLocation } from "react-router-dom";

import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { StickySearchBar } from "@/components/layout/StickySearchBar";
import { ViewModeToggle } from "@/components/layout/ViewModeToggle";
import { BackHeader } from "@/components/layout/BackHeader";

// 글로벌 셸 — (b) 패턴.
//
// 검색·지도 페이지에는 sticky 검색바 + 토글이 떠있고,
// 상세 페이지(/hospitals/:id)는 검색바·토글 자리를 ← 뒤로가기 헤더로 교체한다.
// 한 곳(이 병원)에 집중해야 하는 화면이라 검색 동선은 의도적으로 한 단계 뒤로 둠.
//
// 본문 컨테이너는 가독성 위주 max-w-screen-md (검색·상세), 지도는 풀폭.
export function AppShell() {
  const location = useLocation();
  const isDetail = location.pathname.startsWith("/hospitals/");
  const isMap = location.pathname.startsWith("/map");

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Header />

      {isDetail ? (
        <BackHeader title="병원 상세" />
      ) : (
        <>
          <div className="sticky top-14 z-30 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75">
            <div className="container flex items-center justify-between py-2">
              <ViewModeToggle />
            </div>
          </div>
          <StickySearchBar />
        </>
      )}

      <main className={isMap ? "flex-1 py-4" : "flex-1 container py-6"}>
        {isMap ? (
          <div className="container">
            <Outlet />
          </div>
        ) : (
          <div className="mx-auto max-w-screen-md">
            <Outlet />
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}
