"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { brand } from "@/lib/brand";
import { cn } from "@/lib/utils";

export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" className="flex min-w-0 items-center gap-2.5">
          <span
            className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-xs font-bold tracking-tight text-primary-foreground"
            aria-hidden
          >
            {brand.shortMark}
          </span>
          <span className="min-w-0 leading-tight">
            <span className="block truncate text-[10px] font-medium tracking-[0.14em] text-muted-foreground uppercase">
              {brand.logoLead}
            </span>
            <span className="block truncate text-sm font-semibold tracking-tight text-foreground sm:text-[0.95rem]">
              {brand.logoAccent}
            </span>
          </span>
        </Link>
        <nav className="flex shrink-0 items-center gap-0.5 text-sm">
          {brand.nav.map((item) => {
            const isExternal = "external" in item && item.external;
            const active =
              !isExternal &&
              (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href));
            const className = cn(
              "rounded-md px-2.5 py-1.5 transition-colors sm:px-3",
              active
                ? "bg-secondary font-medium text-secondary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            );
            if (isExternal) {
              return (
                <a
                  key={item.href}
                  href={item.href}
                  target="_blank"
                  rel="noreferrer"
                  className={className}
                >
                  {item.label}
                  <span className="sr-only"> (opens in new tab)</span>
                </a>
              );
            }
            return (
              <Link key={item.href} href={item.href} className={className}>
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
