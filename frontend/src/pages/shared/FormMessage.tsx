import type { ErrorView } from "./apiError";
import { useLang } from "../../i18n/useLang";

/**
 * Inline result of a write: success ("Saved.") or the failure sentence with the
 * server's English detail isolated in a `lang="en"` span. Never toast-only (spec 4.10).
 */
export function FormMessage({
  kind,
  text,
  detail,
}: {
  kind: "success" | "error";
  text: string;
  detail?: string | null;
}) {
  const { lang } = useLang();
  const foreign = lang === "ar" && !!detail;
  return (
    <div
      className={kind === "error" ? "alert alert-error" : "alert alert-success"}
      role={kind === "error" ? "alert" : "status"}
    >
      <p>
        {text}
        {detail ? (
          <>
            {" "}
            <span {...(foreign ? { lang: "en", dir: "ltr" } : {})}>{detail}</span>
          </>
        ) : null}
      </p>
    </div>
  );
}

export function ErrorMessage({ view }: { view: ErrorView }) {
  return <FormMessage kind="error" text={view.text} detail={view.detail} />;
}
