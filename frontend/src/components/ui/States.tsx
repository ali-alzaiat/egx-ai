import { Button } from "@/components/shadcn/button";
import { Skeleton } from "@/components/shadcn/skeleton";
import { useLang } from "../../i18n/useLang";

/** Empty: one sentence on why the area is empty and what fills it. No buttons (spec 3.9). */
export function EmptyState({ children }: { children: string }) {
  return <p className="empty">{children}</p>;
}

/** NoMatch: the filters hide everything. */
export function NoMatch({ things, onClear }: { things: string; onClear?: () => void }) {
  const { t } = useLang();
  return (
    <div className="state">
      <p>{t("no_match_things", { things })}</p>
      {onClear && (
        <Button variant="link" onClick={onClear}>
          {t("clear_filters")}
        </Button>
      )}
    </div>
  );
}

/** Error inside the widget that failed, never full page. */
export function ErrorState({ thing, onRetry }: { thing: string; onRetry: () => void }) {
  const { t } = useLang();
  return (
    <div className="state state-error" role="alert">
      <p>{t("load_error_thing", { thing })}</p>
      <Button variant="outline" onClick={onRetry}>
        {t("retry")}
      </Button>
    </div>
  );
}

/** Plain loading line with a status role. */
export function LoadingState({ thing }: { thing?: string }) {
  const { t } = useLang();
  return (
    <p className="loading" role="status">
      {thing ? t("loading_thing", { thing }) : t("loading")}
    </p>
  );
}

/** Placeholder for a single value that is still loading (about six characters wide). */
export function ValueSkeleton() {
  return <Skeleton className="w-[6ch]" />;
}
