"use client";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import * as React from "react";

import { Tip } from "@/components/ui/overlays";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);
  const dark = mounted && resolvedTheme === "dark";
  return (
    <Tip content={dark ? "Switch to light mode" : "Switch to dark mode"} side="bottom">
      <button onClick={() => setTheme(dark ? "light" : "dark")} aria-label="Toggle colour theme"
        className="inline-flex h-9 w-9 items-center justify-center rounded-full text-ink-2 hover:bg-surface-3 hover:text-ink">
        {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
      </button>
    </Tip>
  );
}
