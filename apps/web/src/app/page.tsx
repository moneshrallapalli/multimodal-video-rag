import { SearchView } from "@/components/search/search-view";
import { brand } from "@/lib/brand";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
      <section className="mb-7 max-w-2xl">
        <span className="inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
          Multimodal · timestamped · grounded
        </span>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
          Search inside videos by what was <span className="text-primary">shown</span> and{" "}
          <span className="text-primary">said</span>.
        </h1>
        <p className="mt-3 text-muted-foreground">{brand.description}</p>
      </section>
      <SearchView />
    </div>
  );
}
