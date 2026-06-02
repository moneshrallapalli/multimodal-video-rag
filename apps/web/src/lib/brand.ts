/**
 * Single source of truth for branding. Swap these values to rebrand the whole UI —
 * the wordmark, metadata, nav, and landing copy all read from here.
 */
export const brand = {
  name: "VideoRAG",
  fullName: "Multimodal Video RAG",
  tagline: "Search inside videos by what was shown and what was said.",
  description:
    "Ask questions over long-form talks and jump straight to the timestamped moment — grounded in both the visual frames and the spoken transcript.",
  nav: [
    { href: "/", label: "Search" },
    { href: "/admin", label: "Admin" },
    { href: "/eval", label: "Eval" },
  ],
  githubUrl: "https://github.com/moneshrallapalli/multimodal-video-rag",
} as const;
