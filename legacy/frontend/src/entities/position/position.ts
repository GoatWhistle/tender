export interface PositionValue {
  readonly code: string;
  readonly label: string;
  readonly text: string | null;
  readonly unit: string | null;
  readonly min: number | null;
  readonly max: number | null;
}

export interface PositionCharacteristic {
  readonly code: string;
  readonly name: string;
  readonly quantitative: boolean;
  readonly required: boolean;
  readonly kind: string;
  readonly multi: boolean;
  readonly values: readonly PositionValue[];
}

export interface PositionDetail {
  readonly code: string;
  readonly name: string;
  readonly category: string;
  readonly okpd2: string;
  readonly okpd2_name: string;
  readonly characteristics: readonly PositionCharacteristic[];
}

export async function fetchPosition(code: string, signal?: AbortSignal): Promise<PositionDetail> {
  const res = await fetch(`/api/v1/positions/${encodeURIComponent(code)}`, { signal });
  if (!res.ok) throw new Error(`position ${code}: ${res.status}`);
  return (await res.json()) as PositionDetail;
}

export function unitOf(c: PositionCharacteristic): string | null {
  return c.values.find((v) => v.unit)?.unit ?? null;
}
