"use client";

import { Suspense, useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import {
  initializeTelemetry,
  track,
} from "../lib/telemetry";

const APP_VERSION = "0.1.0";

function getPageSection(pathname: string): string {
  const segments = pathname.split("/").filter(Boolean);
  return segments[0] || "home";
}

function TelemetryTracker() {
  const pathname = usePathname();
  const previousPath = useRef<string | null>(null);

  useEffect(() => {
    if (!pathname) return;

    if (previousPath.current !== pathname) {
      const pageId = pathname === "/"
        ? "home"
        : pathname.split("/").filter(Boolean).join("_");

      track("page_viewed", {
        page_id: pageId,
        page_section: getPageSection(pathname),
      });

      previousPath.current = pathname;
    }
  }, [pathname]);

  return null;
}

export default function TelemetryProvider() {
  useEffect(() => {
    const startedAt = performance.now();
    const cleanup = initializeTelemetry();

    const reportPageLoad = () => {
      track("page_load_completed", {
        load_time_ms: Math.max(0, performance.now() - startedAt),
        page_id: window.location.pathname === "/"
          ? "home"
          : window.location.pathname.split("/").filter(Boolean).join("_"),
        result: "success",
      });
    };

    if (document.readyState === "complete") {
      reportPageLoad();
    } else {
      window.addEventListener("load", reportPageLoad, { once: true });
    }

    const handleError = () => {
      track("frontend_error_captured", {
        error_id: "window_error",
        error_category: "javascript",
        app_version: APP_VERSION,
      });
    };

    const handleUnhandledRejection = () => {
      track("frontend_error_captured", {
        error_id: "unhandled_rejection",
        error_category: "promise_rejection",
        app_version: APP_VERSION,
      });
    };

    window.addEventListener("error", handleError);
    window.addEventListener("unhandledrejection", handleUnhandledRejection);

    return () => {
      window.removeEventListener("load", reportPageLoad);
      window.removeEventListener("error", handleError);
      window.removeEventListener("unhandledrejection", handleUnhandledRejection);
      cleanup();
    };
  }, []);

  return (
    <Suspense fallback={null}>
      <TelemetryTracker />
    </Suspense>
  );
}
