import { ErrorBlock } from "../components/States";
import { NotFound } from "../api";

export function NotFoundPage() {
  return <ErrorBlock error={new NotFound("page")} />;
}
