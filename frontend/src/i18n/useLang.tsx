import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { t, type CopyKey, type CopyParams, type Lang } from "./dict";

type LangContextValue = {
  lang: Lang;
  setLang: (l: Lang) => void;
  /** Translate a copy key into the current language. */
  t: (key: CopyKey, params?: CopyParams) => string;
  /** HTML locale string for Intl formatting ("ar-EG" or "en"), always Latin digits. */
  locale: string;
};

const LangContext = createContext<LangContextValue | null>(null);

function readStoredLang(): Lang {
  try {
    return localStorage.getItem("egx-lang") === "ar" ? "ar" : "en";
  } catch {
    return "en";
  }
}

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readStoredLang);

  useEffect(() => {
    try {
      localStorage.setItem("egx-lang", lang);
    } catch {
      // private mode: setting is ephemeral, layout still switches
    }
    const root = document.documentElement;
    root.dir = lang === "ar" ? "rtl" : "ltr";
    root.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => setLangState(l), []);

  const value = useMemo<LangContextValue>(
    () => ({
      lang,
      setLang,
      t: (key: CopyKey, params?: CopyParams) => t(key, lang, params),
      // Latin digits in Arabic: EGX figures are conventionally Western digits,
      // and mixing Arabic-Indic digits with API "1234.56" strings would be chaos.
      locale: lang === "ar" ? "ar-EG-u-nu-latn" : "en",
    }),
    [lang, setLang],
  );

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang(): LangContextValue {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used inside <LangProvider>");
  return ctx;
}
