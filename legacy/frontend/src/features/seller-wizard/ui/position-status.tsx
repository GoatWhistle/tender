import type { SessionState } from "../../../api/types";
import { t, type MessageKey } from "../../../shared/i18n";
import { Banner } from "../../../shared/ui/banner/banner";
import { compatibleCandidates } from "../model/steps";

type Tone = "info" | "error" | "warning" | "success";

function describe(state: SessionState): { tone: Tone; title: MessageKey; text: MessageKey } | null {
  if (!state.path)
    return {
      tone: "warning",
      title: "seller:position.notFound",
      text: "seller:position.notFoundText",
    };
  switch (state.status) {
    case "resolved":
      return {
        tone: "success",
        title: "seller:position.resolved",
        text: "seller:position.resolvedText",
      };
    case "ambiguous_in_catalog":
      return {
        tone: "info",
        title: "seller:position.ambiguous",
        text: "seller:position.ambiguousText",
      };
    case "conflict":
      return {
        tone: "error",
        title: "seller:position.conflict",
        text: "seller:position.conflictText",
      };
    case "needs_clarification":
      return {
        tone: "info",
        title: "seller:position.clarify",
        text: "seller:position.clarifyText",
      };
    default:
      return null;
  }
}

export function PositionStatus({ state }: { readonly state: SessionState }) {
  const info = describe(state);
  if (!info) return null;
  const chosen = state.status === "resolved" ? compatibleCandidates(state)[0] : undefined;
  return (
    <Banner
      tone={info.tone}
      title={chosen ? `${t(info.title)}: ${chosen.code}` : t(info.title)}
      live
    >
      <p>{chosen ? chosen.name : t(info.text)}</p>
      {state.unanswered.length > 0 && (
        <p>{t("seller:position.unanswered", { names: state.unanswered.join(", ") })}</p>
      )}
    </Banner>
  );
}
