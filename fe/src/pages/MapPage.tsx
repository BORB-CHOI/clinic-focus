// 지도 검색 페이지
// 카카오맵 임베드, GPS 기반, 반경 슬라이더(0.5/1/3/5/10km)
// 마커 색상: 확실=초록 / 추정=노랑 / 정보 부족=회색
export default function MapPage() {
  return (
    <section>
      <h1 className="text-2xl font-bold">지도 검색</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        카카오맵 + 반경 슬라이더 + 신뢰도 등급별 마커 색상으로 구성될 화면.
      </p>
    </section>
  );
}
