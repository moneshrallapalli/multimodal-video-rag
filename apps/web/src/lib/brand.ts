/**
 * Single source of truth for branding. Swap these values to rebrand the whole UI —
 * the wordmark, metadata, nav, and landing copy all read from here.
 */
export const brand = {
  name: "Multimodal Video Search Engine",
  shortMark: "MV",
  logoLead: "Multimodal",
  logoAccent: "Video Search Engine",
  tagline: "Search inside videos by what was shown and what was said.",
  badge: "Multimodal · timestamped · grounded",
  description:
    "Ask questions over long-form talks and jump straight to the timestamped moment — grounded in both the visual frames and the spoken transcript.",
  author: "Monesh Rallapalli",
  portfolioUrl: "https://moneshrallapalli.com",
  githubUrl: "https://github.com/moneshrallapalli/multimodal-video-rag",
  nav: [
    { href: "/", label: "Search" },
    { href: "/admin", label: "Admin" },
    { href: "/eval", label: "Eval" },
    { href: "https://moneshrallapalli.com", label: "Portfolio", external: true },
  ],
} as const;
