import { brand } from "@/lib/brand";

export function SiteFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-border/70 bg-background">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-6 sm:px-6">
        <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
          <div className="space-y-1 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">{brand.name}</p>
            <p>
              Portfolio demo by{" "}
              <a
                href={brand.portfolioUrl}
                target="_blank"
                rel="noreferrer"
                className="text-foreground underline-offset-4 hover:text-primary hover:underline"
              >
                {brand.author}
              </a>
              {" · "}
              deployed seed index
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
            <a
              href={brand.portfolioUrl}
              target="_blank"
              rel="noreferrer"
              className="text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            >
              Portfolio ↗
            </a>
            <a
              href={brand.githubUrl}
              target="_blank"
              rel="noreferrer"
              className="text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            >
              GitHub ↗
            </a>
          </div>
        </div>
        <p className="text-[11px] text-muted-foreground/80">© {year} {brand.author}</p>
      </div>
    </footer>
  );
}
