import { brand } from "@/lib/brand";

export function SiteFooter() {
  return (
    <footer className="border-t border-border/70 bg-background">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-6 text-xs text-muted-foreground sm:flex-row sm:px-6">
        <p>{brand.fullName} — portfolio project · Phase 1 skeleton, mocked data.</p>
        <a
          href={brand.githubUrl}
          target="_blank"
          rel="noreferrer"
          className="hover:text-foreground"
        >
          GitHub ↗
        </a>
      </div>
    </footer>
  );
}
