import { SearchView } from "@/components/search/search-view";
import { brand } from "@/lib/brand";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
      <section className="animate-in fade-in slide-in-from-bottom-2 mb-8 rounded-2xl border border-border/80 bg-card/70 p-6 shadow-sm backdrop-blur-sm duration-500 ease-out sm:p-8">
        <span className="inline-flex items-center rounded-full border border-primary/25 bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
          {brand.badge}
        </span>
        <h1 className="mt-3 max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">
          Search inside videos by what was <span className="text-primary">shown</span> and{" "}
          <span className="text-primary">said</span>.
        </h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">{brand.description}</p>
      </section>
      <SearchView />
    </div>
  );
}
