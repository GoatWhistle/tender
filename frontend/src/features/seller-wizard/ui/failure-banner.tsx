import type { Failure } from "../../../lib/sellerSession";
import { Banner } from "../../../shared/ui/banner/banner";

export function FailureBanner({ failure }: { readonly failure: Failure }) {
  return (
    <Banner tone="error" title={failure.title}>
      <p>{failure.text}</p>
      {failure.details.map((d) => (
        <p key={d}>{d}</p>
      ))}
    </Banner>
  );
}
