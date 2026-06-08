// 글로벌 푸터 — 의료법 고지.
//
// 의료법 §56 주체 명시 원칙(overview.md §6)을 화면 하단에 항상 노출.
// "우리는 평가하지 않고, 병원이 자기 자신을 어떻게 표현했는지를 보여줄 뿐"이라는
// 정체성을 작은 글씨로 명문화한다. 데이터 출처 고지(§9-⑨)도 함께.
export function Footer() {
  return (
    <footer className="mt-12 border-t bg-muted/30">
      <div className="container py-6">
        <div className="mx-auto max-w-screen-md space-y-2 text-[11px] leading-relaxed text-muted-foreground">
          <p>
            본 서비스는 병원 홈페이지·공공 데이터·사용자 후기에서 자동 수집한 정보를
            AI가 정리한 결과를 제공합니다. 특정 의료기관을 추천·평가하거나 광고하지
            않으며, <strong className="font-medium text-foreground">병원이 자기 자신을
            어떻게 표현했는지</strong>를 출처와 함께 보여줄 뿐입니다.
          </p>
          <p>
            표시된 분류·주력 분야는 자동 분석에 따른 참고 정보이며 실제 진료 내용과
            다를 수 있습니다. 정확한 진료 가능 여부는 해당 병원에 직접 확인하시기
            바랍니다. 응급 상황에서는 즉시 119 또는 가까운 응급실을 이용하세요.
          </p>
          <p className="pt-1 text-muted-foreground/70">
            의료법 제56조에 따른 정보 제공 서비스 · © {new Date().getFullYear()} clinic-focus · PoC
          </p>
        </div>
      </div>
    </footer>
  );
}
