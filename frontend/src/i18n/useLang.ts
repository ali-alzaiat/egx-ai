import { useEffect, useState } from "react";
import { t } from "./dict";

export function useLang() {
  const [lang, setLangState] = useState<"en" | "ar">(() => {
    const stored = localStorage.getItem("egx-lang");
    return stored === "ar" ? "ar" : "en";
  });

  useEffect(() => {
    localStorage.setItem("egx-lang", lang);
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = (l: "en" | "ar") => setLangState(l);

  return { lang, setLang, t: (key: string) => t(key, lang) };
}
