import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Button } from "@/components/shadcn/button";
import { useLang } from "../../i18n/useLang";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { SparkleIcon } from "../ui/icons";
import { useAssistantPanel } from "./assistantContext";

// The chat UI loads on first open; the button itself is a few bytes.
const AssistantPanel = lazy(() => import("./AssistantPanel"));

/** Floating button (inline-end corner) and its side panel. Hidden on /assistant, which has the full chat. */
export function AssistantLauncher() {
  const { t } = useLang();
  const { pathname } = useLocation();
  const { open, setOpen } = useAssistantPanel();
  const phone = useMediaQuery("(max-width: 767px)");
  const buttonRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  const [loaded, setLoaded] = useState(false);
  const onPage = pathname === "/assistant";

  // Mount the panel on first open, then keep it mounted so a closed panel keeps its draft and a running answer.
  if (open && !loaded) setLoaded(true);

  useEffect(() => {
    if (onPage) setOpen(false);
  }, [onPage, setOpen]);

  // Focus returns to the button when the panel closes.
  useEffect(() => {
    if (wasOpen.current && !open) buttonRef.current?.focus();
    wasOpen.current = open;
  }, [open]);

  // A full-screen panel on a phone locks the page behind it, like the menu drawer.
  useEffect(() => {
    if (!open || !phone || onPage) return;
    document.body.classList.add("scroll-locked");
    return () => document.body.classList.remove("scroll-locked");
  }, [open, phone, onPage]);

  if (onPage) return null;

  return (
    <>
      {!open && (
        <Button
          ref={buttonRef}
          className="fixed end-4 bottom-[max(1rem,env(safe-area-inset-bottom))] z-30 size-12 rounded-full p-0 shadow-pop sm:w-auto sm:px-5"
          aria-label={t("assistant_open")}
          aria-haspopup="dialog"
          onClick={() => setOpen(true)}
        >
          <SparkleIcon size={20} />
          <span className="hidden sm:inline">{t("assistant_title")}</span>
        </Button>
      )}
      {loaded && (
        <Suspense fallback={null}>
          <AssistantPanel visible={open} onClose={() => setOpen(false)} />
        </Suspense>
      )}
    </>
  );
}
