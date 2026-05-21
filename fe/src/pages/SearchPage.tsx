// 검색 결과 페이지
// API: GET /api/search
// 카드: one_line_summary + 신뢰도 배지 + 표준 진료과목 + 실제 주력 태그
export default function SearchPage() {
  return (
    <section>
      <h1 className="text-2xl font-bold">검색</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        자연어 + 위치 기반 검색 결과 화면. Mock 데이터 단계에서 카드 리스트를 채울 예정.
      </p>
    </section>
  );
}
