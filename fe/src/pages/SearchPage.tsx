import { Link } from "react-router-dom";

import { mockHospital } from "@/mocks/hospital";

// 검색 결과 페이지 (다음 단계에서 본격 구현)
// 지금은 Mock 병원 상세 페이지로 들어가는 임시 링크만 노출
export default function SearchPage() {
  return (
    <section>
      <h1 className="text-2xl font-bold">검색</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        자연어 + 위치 기반 검색 결과 화면. 다음 단계에서 카드 리스트를 채울 예정.
      </p>

      <div className="mt-6 rounded-md border bg-muted/40 p-4 text-sm">
        <p className="mb-2 text-muted-foreground">
          데모용 임시 진입점 — 상세 페이지 9영역 골격 보기
        </p>
        <Link
          to={`/hospitals/${mockHospital.hospital_id}`}
          className="text-primary underline-offset-2 hover:underline"
        >
          {mockHospital.name} 상세 페이지로 →
        </Link>
      </div>
    </section>
  );
}
