import { Section } from "@/components/common/Section";
import { Badge } from "@/components/ui/badge";
import type { NonPayItem } from "@/types/domain";

interface NonPayItemsSectionProps {
  nonpay_items: NonPayItem[];
}

// 상세 페이지 ② 영역 확장: 심평원 비급여 신고항목
//
// 출처 = 심평원 공공 신고 데이터 (public_data).
// 카피 원칙: "병원이 심평원에 신고한 비급여 항목" — 주체 = 병원, 근거 = 심평원.
// "이 병원은 ○○를 한다/잘한다" 표현 금지.
//
// graceful 처리:
//   - nonpay_items 가 빈 배열이면 이 컴포넌트 자체를 렌더하지 않음 (호출부에서 조건부).
//   - amount 가 null 이면 금액란 표시 안 함 (미신고 항목).
//   - category 가 null 이면 분류 배지 생략.
export function NonPayItemsSection({ nonpay_items }: NonPayItemsSectionProps) {
  // 빈 배열 방어 — 호출부에서 걸러주지만 이중 방어
  if (nonpay_items.length === 0) return null;

  // 카테고리별로 그룹화
  const grouped = groupByCategory(nonpay_items);

  return (
    <Section
      id="section-nonpay"
      title="비급여 신고항목"
      badge="②+"
      subtitle="병원이 심평원에 신고한 비급여 항목"
      action={
        <Badge
          variant="outline"
          className="border-blue-300 bg-blue-50 text-blue-700 text-[10px] px-1.5"
        >
          심평원 신고
        </Badge>
      }
    >
      <div className="space-y-4">
        <p className="text-xs text-muted-foreground">
          아래 항목은 병원이 심평원에 신고한 비급여 진료비 목록입니다. 실제 청구 금액은
          병원 방문 시 달라질 수 있으므로 병원에 직접 확인하세요.
        </p>

        {grouped.map(({ category, items }) => (
          <div key={category ?? "__미분류"}>
            {category && (
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {category}
              </h3>
            )}
            <ul className="divide-y rounded-md border">
              {items.map((item, idx) => (
                <NonPayRow key={`${item.item_name}-${idx}`} item={item} />
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Section>
  );
}

function NonPayRow({ item }: { item: NonPayItem }) {
  return (
    <li className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
      <span className="min-w-0 flex-1 text-foreground">{item.item_name}</span>
      {item.amount !== null ? (
        <span className="shrink-0 font-medium tabular-nums">
          {item.amount.toLocaleString("ko-KR")}원
        </span>
      ) : (
        <span className="shrink-0 text-xs text-muted-foreground">금액 미신고</span>
      )}
    </li>
  );
}

interface CategoryGroup {
  category: string | null;
  items: NonPayItem[];
}

function groupByCategory(items: NonPayItem[]): CategoryGroup[] {
  const map = new Map<string, NonPayItem[]>();
  const NULL_KEY = "__null__";

  for (const item of items) {
    const key = item.category ?? NULL_KEY;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }

  const result: CategoryGroup[] = [];

  // 카테고리 있는 것 먼저, null(미분류) 마지막
  for (const [key, groupItems] of map.entries()) {
    if (key !== NULL_KEY) {
      result.push({ category: key, items: groupItems });
    }
  }
  if (map.has(NULL_KEY)) {
    result.push({ category: null, items: map.get(NULL_KEY)! });
  }

  return result;
}
