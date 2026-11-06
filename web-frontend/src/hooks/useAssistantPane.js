import { useSyncExternalStore } from "react";
import { useAssistantState } from "../state/assistantState";

const wideScreen = window.matchMedia("(min-width: 901px)");

function subscribe(onChange) {
  wideScreen.addEventListener("change", onChange);
  return () => wideScreen.removeEventListener("change", onChange);
}

export default function useAssistantPane(scope, mobileKey) {
  const wide = useSyncExternalStore(subscribe, () => wideScreen.matches);
  const [desktopOpen, setDesktopOpen] = useAssistantState(scope, "desktopPanelOpen", true);
  const [mobileOpen, setMobileOpen] = useAssistantState(scope, mobileKey, false);

  return wide
    ? { wide, paneOpen: desktopOpen, setPaneOpen: setDesktopOpen }
    : { wide, paneOpen: mobileOpen, setPaneOpen: setMobileOpen };
}
