import { createContext, useContext, useEffect, useState, useCallback } from "react";

const ThemeContext = createContext(null);
const MODES = ["system", "light", "dark"];

function systemPrefersDark() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeProvider({ children }) {
  const [mode, setMode] = useState(() => localStorage.getItem("theme-mode") || "system");

  useEffect(() => {
    const root = document.documentElement;
    const apply = () => {
      const dark = mode === "dark" || (mode === "system" && systemPrefersDark());
      root.classList.toggle("dark", dark);
    };
    apply();
    localStorage.setItem("theme-mode", mode);

    if (mode === "system" && window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      mq.addEventListener("change", apply);
      return () => mq.removeEventListener("change", apply);
    }
  }, [mode]);

  const cycleMode = useCallback(() => {
    setMode((m) => MODES[(MODES.indexOf(m) + 1) % MODES.length]);
  }, []);

  return (
    <ThemeContext.Provider value={{ mode, setMode, cycleMode }}>{children}</ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
