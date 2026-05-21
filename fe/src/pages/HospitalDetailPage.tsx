import { useParams } from "react-router-dom";

// 병원 상세 페이지 — 데모 핵심 장면
// 9개 영역 매핑: ① 헤드라이너 ② 핵심 진료 정보 ③ 의료진 ④ 신뢰도·근거
// ⑤ 운영 정보 ⑥ 사용자 피드백 ⑦ 분류 변경 이력 ⑧ 관련 병원 ⑨ 메타
export default function HospitalDetailPage() {
  const { hospitalId } = useParams();

  return (
    <section>
      <h1 className="text-2xl font-bold">병원 상세</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        hospital_id: <code className="rounded bg-muted px-1">{hospitalId}</code>
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        9개 영역 컴포넌트로 분리해 Mock 데이터로 골격을 구성할 예정.
      </p>
    </section>
  );
}
