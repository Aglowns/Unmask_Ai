"use client";

import { useMemo } from "react";
import Link from "next/link";
import InfiniteGallery from "@/components/ui/3d-gallery-photography";
import { ArrowRight } from "lucide-react";

// Images with REAL or FAKE text overlay at the top
const galleryImagesSource = [
  { src: "/images/fake-car-selfie.jpg", alt: "AI - Night street selfie" },
  { src: "/images/fake-counter.jpg", alt: "AI - Cafe counter" },
  { src: "/images/fake-mirror-selfie.jpg", alt: "AI - Mirror selfie" },
  { src: "/images/fake-room.jpg", alt: "AI - Dorm room" },
  { src: "/images/fake-night-selfie.png", alt: "AI - Woman night street selfie" },
  { src: "/images/fake-cafe-man.png", alt: "AI - Cafe with green drink" },
  { src: "/images/fake-sports-bra.png", alt: "AI - Sports bra selfie" },
  { src: "/images/fake-dorm-room.png", alt: "AI - Bedroom scene" },
  { src: "/images/real-mountain.png", alt: "Real - Mountain hike" },
  { src: "/images/real-business.png", alt: "Real - Business outfit" },
  { src: "/images/real-jersey.png", alt: "Real - Jersey selfie" },
  { src: "/images/real-suit.png", alt: "Real - Formal event" },
  { src: "/images/real-group.png", alt: "Real - Group photo" },
];

// Fisher-Yates shuffle for random order on each page load
function shuffleArray<T>(array: T[]): T[] {
  const shuffled = [...array];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

export default function Home() {
  const galleryImages = useMemo(() => shuffleArray(galleryImagesSource), []);
  return (
    <main className="min-h-screen w-full bg-black">
      {/* 3D Gallery Background */}
      <InfiniteGallery
        images={galleryImages}
        speed={1.2}
        zSpacing={3}
        visibleCount={12}
        falloff={{ near: 0.8, far: 14 }}
        className="h-screen w-full rounded-lg overflow-hidden"
      />

      {/* Center overlay text + Get Started button */}
      <div className="h-screen inset-0 pointer-events-none fixed flex flex-col items-center justify-center text-center px-3 mix-blend-exclusion text-white z-10">
        <h1
          className="text-4xl md:text-7xl tracking-tight mb-8"
          style={{ fontFamily: "var(--font-instrument-serif)" }}
        >
          Seeing is no longer believing
        </h1>
        <Link
          href="/analyze"
          className="pointer-events-auto inline-flex items-center gap-2 px-8 py-3 rounded-full bg-white text-black font-semibold text-base hover:bg-white/90 hover:scale-105 active:scale-95 transition-all duration-300 mix-blend-normal cursor-pointer"
        >
          Get Started
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>

      {/* Bottom navigation hint */}
      <div className="text-center fixed bottom-10 left-0 right-0 font-mono uppercase text-[11px] font-semibold text-white/70 z-10">
        <p>Use mouse wheel, arrow keys, or touch to navigate</p>
        <p className="opacity-60">
          Auto-play resumes after 3 seconds of inactivity
        </p>
      </div>
    </main>
  );
}
