// 익명 피드백용 디바이스 식별자
// 같은 디바이스에서 같은 병원에 1회만 피드백 가능 (BE에서 DUPLICATE_FEEDBACK 409 반환)

const DEVICE_ID_KEY = "app_device_id";

function createDeviceId(): string {
  if (globalThis.crypto?.randomUUID) {
    return "d_" + globalThis.crypto.randomUUID();
  }

  return `d_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 12)}`;
}

export function getDeviceId(): string {
  let id = localStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    id = createDeviceId();
    localStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
}
