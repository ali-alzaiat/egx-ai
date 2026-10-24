import { useEffect, useId, useMemo, useState, type KeyboardEvent, type Ref } from "react";
import { useNavigate } from "react-router-dom";
import { useCompanies } from "../../api/client";
import { useLang } from "../../i18n/useLang";
import { useDebouncedValue } from "../../lib/useDebouncedValue";
import type { Company } from "../../types";
import { CompanyName, companyNameText } from "./CompanyName";
import { CloseIcon, SearchIcon } from "./icons";

interface BaseProps {
  inputRef?: Ref<HTMLInputElement>;
  autoFocus?: boolean;
  /** Called after a selection or Esc, e.g. to close the mobile overlay. */
  onDone?: () => void;
}

type CompanySearchProps =
  | (BaseProps & { mode: "search" })
  | (BaseProps & {
      mode: "picker";
      value: Company | null;
      onSelect: (company: Company) => void;
      onClear: () => void;
    });

/** Exact ticker match first, then the API order. */
export function sortCompanyResults(items: readonly Company[], q: string): Company[] {
  const needle = q.trim().toUpperCase();
  return [...items].sort((a, b) => {
    const ax = a.ticker.toUpperCase() === needle ? 0 : 1;
    const bx = b.ticker.toUpperCase() === needle ? 0 : 1;
    return ax - bx;
  });
}

interface ResultsProps {
  q: string;
  listId: string;
  active: number;
  onResults: (items: Company[]) => void;
  onPick: (company: Company) => void;
  onHover: (index: number) => void;
}

/** Mounted only while there is a query, so no request fires for an empty box. */
function Results({ q, listId, active, onResults, onPick, onHover }: ResultsProps) {
  const { t, lang } = useLang();
  const { data, isError, isFetching, refetch } = useCompanies({ search: q, page_size: 8 });
  const items = useMemo(() => sortCompanyResults(data?.items ?? [], q), [data, q]);

  useEffect(() => {
    onResults(items);
  }, [items, onResults]);

  if (isError) {
    return (
      <div className="combobox-list combobox-status" role="alert">
        <span>{t("search_error")}</span>
        <button type="button" className="link-btn" onMouseDown={(e) => e.preventDefault()} onClick={() => void refetch()}>
          {t("search_retry")}
        </button>
      </div>
    );
  }
  if (!data && isFetching) {
    return (
      <div className="combobox-list combobox-status" role="status">
        {t("search_searching")}
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div className="combobox-list combobox-status" role="status">
        {t("search_no_results", { q })}
      </div>
    );
  }
  return (
    <ul className="combobox-list" id={listId} role="listbox">
      {items.map((c, i) => (
        <li
          key={c.id}
          id={`${listId}-${i}`}
          role="option"
          aria-selected={i === active}
          className="combobox-option"
          onMouseDown={(e) => e.preventDefault()}
          onMouseEnter={() => onHover(i)}
          onClick={() => onPick(c)}
        >
          <span className="combobox-ticker" dir="ltr">
            {c.ticker}
          </span>
          <span className="combobox-name" title={companyNameText(lang, c.name, c.name_ar)}>
            <CompanyName name={c.name} nameAr={c.name_ar} />
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * One combobox, two modes (spec 3.3): "search" navigates to the company hub on
 * select; "picker" reports the choice, shows "TICKER — Name" and can be cleared.
 * ARIA 1.2 combobox pattern: role=combobox, aria-expanded, aria-activedescendant.
 */
export default function CompanySearch(props: CompanySearchProps) {
  const { t, lang } = useLang();
  const navigate = useNavigate();
  const listId = useId();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [results, setResults] = useState<Company[]>([]);
  const debounced = useDebouncedValue(q.trim(), 150);

  const pick = (company: Company): void => {
    setQ("");
    setOpen(false);
    if (props.mode === "picker") props.onSelect(company);
    else navigate(`/companies/${encodeURIComponent(company.ticker)}`);
    props.onDone?.();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => (results.length === 0 ? 0 : (i + 1) % results.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (results.length === 0 ? 0 : (i - 1 + results.length) % results.length));
    } else if (e.key === "Enter") {
      const chosen = results[active] ?? results[0];
      if (open && chosen) {
        e.preventDefault();
        pick(chosen);
      }
    } else if (e.key === "Escape") {
      setQ("");
      setOpen(false);
      props.onDone?.();
    }
  };

  if (props.mode === "picker" && props.value) {
    const c = props.value;
    return (
      <div className="combobox">
        <div className="combobox-field">
          <span className="combobox-value">
            <span dir="ltr">{c.ticker}</span> — <CompanyName name={c.name} nameAr={c.name_ar} />
          </span>
          <button type="button" className="combobox-clear" aria-label={t("picker_clear")} onClick={props.onClear}>
            <CloseIcon />
          </button>
        </div>
      </div>
    );
  }

  const showList = open && debounced.length > 0;
  return (
    <div className="combobox">
      <div className="combobox-field">
        <SearchIcon />
        <input
          ref={props.inputRef}
          className="combobox-input"
          type="text"
          role="combobox"
          aria-label={t("search_placeholder")}
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && results.length > 0 ? `${listId}-${active}` : undefined}
          placeholder={t("search_placeholder")}
          autoComplete="off"
          autoFocus={props.autoFocus}
          lang={lang}
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
            setActive(0);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
        {q === "" && props.mode === "search" && (
          <span className="combobox-hint" dir="ltr" aria-hidden="true">
            Ctrl K
          </span>
        )}
      </div>
      {showList && (
        <Results
          q={debounced}
          listId={listId}
          active={active}
          onResults={setResults}
          onPick={pick}
          onHover={setActive}
        />
      )}
    </div>
  );
}
