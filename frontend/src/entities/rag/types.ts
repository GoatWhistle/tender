export type FixKind = "typo" | "logic" | "unit" | "other";

export interface Fix {
  readonly before: string;
  readonly after: string;
  readonly kind: FixKind | string;
}

export interface SearchCandidate {
  readonly id: string;
  readonly name: string;
  readonly code: string;
  readonly okpd2: string;
  readonly relevance?: number | null;
  readonly reason?: string | null;
  readonly differences: Readonly<Record<string, string>>;
}

export type DiscoveryStage = "review" | "candidates" | "ranked";

export interface Search {
  readonly id: string;
  readonly stage: DiscoveryStage;
  readonly description: string;
  readonly corrected: string;
  readonly fixes: readonly Fix[];
  readonly issues: readonly string[];
  readonly candidates: readonly SearchCandidate[];
  readonly rejected: readonly SearchCandidate[];
  readonly auto_select_code: string | null;
  readonly auto_select_reason: string | null;
}

export type SessionStage = "clarify" | "pick" | "spec" | "done" | "failed";

export interface Group {
  readonly code: string;
  readonly name: string;
  readonly okpd2: string;
  readonly relevance: number;
  readonly reason: string;
}

export interface Candidate {
  readonly code: string;
  readonly name: string;
  readonly differences: Readonly<Record<string, string>>;
}

export interface Question {
  readonly name: string;
  readonly required: boolean;
  readonly multiple: boolean;
  readonly options: readonly string[];
  readonly counts: readonly number[];
}

export type FixedValue = string | readonly string[];

export interface Position {
  readonly code: string;
  readonly name: string;
  readonly okpd2: string;
  readonly okpd2_name: string;
  readonly fixed: Readonly<Record<string, FixedValue>>;
}

export interface Band {
  readonly option: string;
  readonly min: number | null;
  readonly min_inclusive: boolean;
  readonly max: number | null;
  readonly max_inclusive: boolean;
}

export type Origin = "description" | "assistant" | "manual";
export type Doubt = "large" | "small" | "negative";

export interface Characteristic {
  readonly name: string;
  readonly required: boolean;
  readonly multiple: boolean;
  readonly options: readonly string[];
  readonly values: readonly string[];
  readonly origin?: Origin | null;
  readonly unit?: string | null;
  readonly bands?: readonly Band[];
  readonly number?: number | null;
  readonly warning?: Doubt | null;
}

export interface Extra {
  readonly name: string;
  readonly value: string;
  readonly reason?: string;
}

export interface ChatMessage {
  readonly id: string;
  readonly role: string;
  readonly text: string;
}

export interface Session {
  readonly id: string;
  readonly stage: SessionStage;
  readonly description: string;
  readonly corrected: string;
  readonly fixes: readonly Fix[];
  readonly issues: readonly string[];
  readonly groups: readonly Group[];
  readonly group: string;
  readonly answers: Readonly<Record<string, unknown>>;
  readonly candidates: readonly Candidate[];
  readonly question: Question | null;
  readonly position: Position | null;
  readonly characteristics: readonly Characteristic[];
  readonly extras: readonly Extra[];
  readonly extras_allowed: boolean;
  readonly missing: readonly string[];
  readonly message: string | null;
  readonly selection_reason: string | null;
  readonly messages: readonly ChatMessage[];
}

export interface Verdict {
  readonly accepted: boolean;
  readonly problems: readonly string[];
  readonly warnings: readonly string[];
  readonly fixed: Extra | null;
  readonly session: Session;
}

export interface Suggestion {
  readonly name: string;
  readonly unit: string;
  readonly options: readonly string[];
  readonly value: string;
  readonly evidence: string;
  readonly source: string;
  readonly share: number | null;
  readonly why: string;
}

export interface Suggestions {
  readonly code: string;
  readonly items: readonly Suggestion[];
}

export interface Outcome {
  readonly code: string;
  readonly name: string;
  readonly okpd2: string;
  readonly okpd2_name: string;
  readonly fixed: Readonly<Record<string, FixedValue>>;
  readonly chosen: Readonly<Record<string, FixedValue>>;
  readonly entered: Readonly<Record<string, number>>;
  readonly doubts: Readonly<Record<string, string>>;
  readonly extras: readonly Extra[];
}

export interface CatalogFound {
  readonly code: string;
  readonly name: string;
  readonly okpd2: string;
  readonly okpd2_name: string;
}

export interface CatalogCharacteristic {
  readonly code: string;
  readonly name: string;
  readonly kind: string;
  readonly required: boolean;
  readonly values: readonly string[];
}

export interface CatalogPosition extends CatalogFound {
  readonly units: readonly string[];
  readonly rubrics: readonly string[];
  readonly characteristics: readonly CatalogCharacteristic[];
}

export interface ComparisonRow {
  readonly field: "okpd2" | "units" | "characteristic";
  readonly name?: string | null;
  readonly values: readonly unknown[];
  readonly differs: boolean;
}

export interface CatalogComparison {
  readonly positions: readonly CatalogFound[];
  readonly rows: readonly ComparisonRow[];
}
