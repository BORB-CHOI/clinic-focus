import { useState } from "react";
import { X, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  type AgeBucket,
  type BmiBucket,
  type GenderBucket,
  type HealthProfile,
  calcBmiBucket,
  clearHealthProfile,
  getHealthProfile,
  saveHealthProfile,
} from "@/lib/healthProfile";
import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  onClose: () => void;
}

// ── 선택 버튼 그룹 ──────────────────────────────────────────────────────────

function Chip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1 text-sm transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-input bg-background text-muted-foreground hover:border-primary/50 hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}

// ── 모달 본체 ───────────────────────────────────────────────────────────────

export function HealthProfileModal({ open, onClose }: Props) {
  const saved = getHealthProfile();

  const [gender, setGender] = useState<GenderBucket>(saved.genderBucket);
  const [age, setAge]       = useState<AgeBucket>(saved.ageBucket);
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");
  const [saving, setSaving] = useState(false);

  if (!open) return null;

  const bmi: BmiBucket = calcBmiBucket(Number(height), Number(weight));

  async function handleSave() {
    setSaving(true);
    const profile: HealthProfile = {
      genderBucket: gender,
      ageBucket:    age,
      bmiBucket:    bmi,
    };
    await saveHealthProfile(profile);
    setSaving(false);
    onClose();
  }

  function handleClear() {
    clearHealthProfile();
    setGender("unknown");
    setAge("unknown");
    setHeight("");
    setWeight("");
    onClose();
  }

  return (
    // 오버레이
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-sm rounded-xl border bg-card shadow-xl">
        {/* 헤더 */}
        <div className="flex items-center justify-between border-b px-5 py-4">
          <div>
            <p className="font-semibold">내 정보 (선택)</p>
            <p className="text-xs text-muted-foreground">검색 패턴 분석에만 사용됩니다</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 hover:bg-accent">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* 입력 영역 */}
        <div className="space-y-5 px-5 py-5">
          {/* 성별 */}
          <div className="space-y-2">
            <p className="text-sm font-medium">성별</p>
            <div className="flex flex-wrap gap-2">
              {(["male", "female", "other", "unknown"] as GenderBucket[]).map((v) => (
                <Chip
                  key={v}
                  label={{ male: "남성", female: "여성", other: "기타", unknown: "비공개" }[v]}
                  active={gender === v}
                  onClick={() => setGender(v)}
                />
              ))}
            </div>
          </div>

          {/* 연령대 */}
          <div className="space-y-2">
            <p className="text-sm font-medium">연령대</p>
            <div className="flex flex-wrap gap-2">
              {(["teens", "20s", "30s", "40s", "50plus", "unknown"] as AgeBucket[]).map((v) => (
                <Chip
                  key={v}
                  label={{ teens: "10대", "20s": "20대", "30s": "30대", "40s": "40대", "50plus": "50대+", unknown: "비공개" }[v]}
                  active={age === v}
                  onClick={() => setAge(v)}
                />
              ))}
            </div>
          </div>

          {/* 키·몸무게 (선택) */}
          <div className="space-y-2">
            <p className="text-sm font-medium">
              키 · 몸무게{" "}
              <span className="font-normal text-muted-foreground">(선택)</span>
            </p>
            <div className="flex gap-3">
              <div className="relative flex-1">
                <input
                  type="number"
                  value={height}
                  onChange={(e) => setHeight(e.target.value)}
                  placeholder="키"
                  min={100}
                  max={250}
                  className="h-9 w-full rounded-md border border-input bg-background px-3 pr-8 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">cm</span>
              </div>
              <div className="relative flex-1">
                <input
                  type="number"
                  value={weight}
                  onChange={(e) => setWeight(e.target.value)}
                  placeholder="몸무게"
                  min={20}
                  max={300}
                  className="h-9 w-full rounded-md border border-input bg-background px-3 pr-8 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">kg</span>
              </div>
            </div>
            {bmi !== "unknown" && (
              <p className="text-xs text-muted-foreground">
                BMI 범주:{" "}
                <span className="font-medium text-foreground">
                  {{ underweight: "저체중", normal: "정상", overweight: "과체중", obese: "비만" }[bmi]}
                </span>
                {" "}— 이 범주만 저장됩니다
              </p>
            )}
          </div>

          {/* 개인정보 안내 */}
          <div className="flex items-start gap-2 rounded-lg bg-muted/60 px-3 py-2.5">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <p className="text-xs leading-relaxed text-muted-foreground">
              키·몸무게 원본은 서버로 전송되지 않습니다.
              성별·연령대·BMI 범주만 익명으로 저장되며, 병원 검색 패턴 통계에만 사용됩니다.
            </p>
          </div>
        </div>

        {/* 하단 버튼 */}
        <div className="flex items-center justify-between border-t px-5 py-4">
          <button
            type="button"
            onClick={handleClear}
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            입력 정보 삭제
          </button>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={onClose}>나중에</Button>
            <Button size="sm" onClick={handleSave} disabled={saving}>
              {saving ? "저장 중…" : "저장하기"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
