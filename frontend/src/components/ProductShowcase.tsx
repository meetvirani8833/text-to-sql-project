import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, ChevronLeft, ChevronRight, Pause } from 'lucide-react';

/* ──────────────────────────────────────────────────────────────
   BEAT DEFINITIONS — the cinematic script
   Each beat can have:
     - text lines (animated typography)
     - a video clip (auto-plays when the beat is active)
     - a hold duration before auto-advancing
   ────────────────────────────────────────────────────────────── */

interface Beat {
    id: string;
    /** Main large text line */
    headline: string;
    /** Optional smaller text below the headline */
    subtext?: string;
    /** Path to a demo video clip (relative to /public) */
    video?: string;
    /** How long to hold this beat in ms (after video ends or if no video) */
    holdMs: number;
    /** Dark background instead of default light */
    dark?: boolean;
}

const BEATS: Beat[] = [
    {
        id: 'hook',
        headline: 'Ask your data anything.',
        subtext: 'Your team waits hours for reports. What if they didn\'t have to?',
        holdMs: 4000,
        dark: true,
    },
    {
        id: 'first-demo',
        headline: 'Plain language. Instant answers.',
        video: '/demo/clip1.mp4',
        holdMs: 2000,
    },
    {
        id: 'visualization',
        headline: 'One click. Instant visualization.',
        video: '/demo/clip2.mp4',
        holdMs: 2000,
    },
    {
        id: 'memory',
        headline: 'It remembers context.',
        subtext: 'Just like talking to a person.',
        video: '/demo/clip3.mp4',
        holdMs: 2000,
    },
    {
        id: 'entity',
        headline: 'Real names. No exact matches needed.',
        video: '/demo/clip4.mp4',
        holdMs: 2000,
    },
    {
        id: 'clarification',
        headline: 'Smart enough to ask when unsure.',
        video: '/demo/clip5.mp4',
        holdMs: 2000,
    },
    {
        id: 'cta',
        headline: 'Have custom requirements?',
        subtext: 'We will build it for you.',
        holdMs: 5000,
        dark: true,
    },
];

/* Indices of beats that have videos */
const VIDEO_BEATS = BEATS
    .map((b, i) => ({ index: i, video: b.video }))
    .filter((x): x is { index: number; video: string } => !!x.video);

/* ──────────────────────────────────────────────────────────────
   ANIMATION VARIANTS
   ────────────────────────────────────────────────────────────── */

const textVariants = {
    initial: { opacity: 0, y: 30, filter: 'blur(8px)' },
    animate: {
        opacity: 1,
        y: 0,
        filter: 'blur(0px)',
        transition: { duration: 0.7, ease: [0.22, 1, 0.36, 1] as const },
    },
    exit: {
        opacity: 0,
        y: -20,
        filter: 'blur(6px)',
        transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] as const },
    },
};

const subtextVariants = {
    initial: { opacity: 0, y: 20 },
    animate: {
        opacity: 1,
        y: 0,
        transition: { duration: 0.6, delay: 0.25, ease: [0.22, 1, 0.36, 1] as const },
    },
    exit: {
        opacity: 0,
        y: -12,
        transition: { duration: 0.3 },
    },
};

/* ──────────────────────────────────────────────────────────────
   COMPONENT
   ────────────────────────────────────────────────────────────── */

export function ProductShowcase() {
    const [currentBeat, setCurrentBeat] = useState(-1); // -1 = not started
    const [isPlaying, setIsPlaying] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const sectionRef = useRef<HTMLDivElement | null>(null);

    /* One ref per video — keyed by beat index */
    const videoRefs = useRef<Record<number, HTMLVideoElement | null>>({});

    const beat = currentBeat >= 0 && currentBeat < BEATS.length ? BEATS[currentBeat] : null;

    const clearTimer = useCallback(() => {
        if (timerRef.current) {
            clearTimeout(timerRef.current);
            timerRef.current = null;
        }
    }, []);

    /* Advance to the next beat */
    const goNext = useCallback(() => {
        clearTimer();
        setCurrentBeat((prev) => {
            const next = prev + 1;
            if (next >= BEATS.length) {
                setIsPlaying(false);
                return prev; // stay on last beat
            }
            return next;
        });
    }, [clearTimer]);

    const goPrev = useCallback(() => {
        clearTimer();
        setCurrentBeat((prev) => Math.max(0, prev - 1));
    }, [clearTimer]);

    /* Schedule auto-advance when beat changes */
    useEffect(() => {
        if (!isPlaying || isPaused || !beat) return;

        // If beat has a video, wait for it to end (handled in onEnded)
        // Otherwise, hold for holdMs then advance
        if (!beat.video) {
            timerRef.current = setTimeout(goNext, beat.holdMs);
        }

        return clearTimer;
    }, [currentBeat, isPlaying, isPaused, beat, goNext, clearTimer]);

    /* Video ended handler */
    const handleVideoEnded = useCallback(() => {
        if (!isPlaying || isPaused) return;
        goNext();
    }, [isPlaying, isPaused, goNext]);

    /*
     * CORE FIX: When the beat changes, play the active video and
     * pause + reset all others. Videos are ALWAYS mounted so they
     * never need to re-buffer.
     */
    useEffect(() => {
        VIDEO_BEATS.forEach(({ index }) => {
            const el = videoRefs.current[index];
            if (!el) return;
            if (index === currentBeat) {
                el.currentTime = 0;
                el.play().catch(() => {/* autoplay may be blocked */});
            } else {
                el.pause();
                el.currentTime = 0;
            }
        });
    }, [currentBeat]);

    /* Handle pause / resume for the active video */
    useEffect(() => {
        const el = videoRefs.current[currentBeat];
        if (!el) return;
        if (isPaused) {
            el.pause();
        } else {
            el.play().catch(() => {});
        }
    }, [isPaused, currentBeat]);

    /* Start the showcase */
    const handleStart = () => {
        setCurrentBeat(0);
        setIsPlaying(true);
        setIsPaused(false);
        // Smooth scroll the showcase to center of viewport
        setTimeout(() => {
            sectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 50);
    };

    const togglePause = () => {
        if (isPaused) {
            setIsPaused(false);
        } else {
            setIsPaused(true);
            clearTimer();
        }
    };

    const isDark = beat?.dark ?? false;

    /* ── Idle state: attractive play button ── */
    if (currentBeat < 0) {
        return (
            <section className="relative w-full min-h-[70vh] md:h-screen flex items-center justify-center">
                <div className="max-w-6xl mx-auto px-6 py-16 md:py-24 flex flex-col items-center text-center">
                    <motion.p
                        initial={{ opacity: 0, y: 12 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="text-xs font-bold uppercase tracking-widest text-[#666] mb-6"
                    >
                        Product Walkthrough
                    </motion.p>

                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6, delay: 0.1 }}
                        className="text-3xl md:text-4xl font-bold tracking-tight"
                    >
                        See what Dfuse actually does
                    </motion.h2>

                    <motion.p
                        initial={{ opacity: 0 }}
                        whileInView={{ opacity: 1 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.25 }}
                        className="mt-4 text-[#555] font-medium max-w-md"
                    >
                        A 60-second walkthrough of the key capabilities — from question to insight.
                    </motion.p>

                    <motion.button
                        type="button"
                        onClick={handleStart}
                        initial={{ opacity: 0, scale: 0.9 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.35, type: 'spring', stiffness: 200 }}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.97 }}
                        className="mt-10 w-20 h-20 rounded-full bg-[#111] text-[#f4f4f2] flex items-center justify-center shadow-xl hover:bg-[#333] transition-colors"
                    >
                        <Play size={28} className="ml-1" />
                    </motion.button>
                    <p className="mt-4 text-xs font-bold uppercase tracking-widest text-[#999]">
                        Watch the walkthrough
                    </p>
                </div>
            </section>
        );
    }

    /* ── Active showcase ── */
    return (
        <section
            ref={sectionRef}
            className={`relative w-full overflow-hidden transition-colors duration-700 ${
                isDark ? 'bg-[#111] text-[#f4f4f2]' : 'bg-[#f4f4f2] text-[#111]'
            }`}
        >
            <div className="max-w-6xl mx-auto px-6 py-16 md:py-24 flex flex-col items-center justify-center min-h-[70vh] md:h-screen">
                {/* ── Text area: animated in/out per beat ── */}
                <AnimatePresence mode="wait">
                    <motion.div
                        key={beat?.id}
                        className="flex flex-col items-center text-center w-full"
                        initial="initial"
                        animate="animate"
                        exit="exit"
                    >
                        {/* Headline */}
                        <motion.h2
                            variants={textVariants}
                            className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight leading-[1.05] max-w-4xl"
                        >
                            {beat?.headline}
                        </motion.h2>

                        {/* Subtext */}
                        {beat?.subtext && (
                            <motion.p
                                variants={subtextVariants}
                                className={`mt-5 text-lg md:text-xl font-medium max-w-xl ${
                                    isDark ? 'text-[#aaa]' : 'text-[#555]'
                                }`}
                            >
                                {beat.subtext}
                            </motion.p>
                        )}

                        {/* CTA button on last beat */}
                        {beat?.id === 'cta' && (
                            <motion.a
                                href="#contact"
                                initial={{ opacity: 0, y: 16 }}
                                animate={{ opacity: 1, y: 0, transition: { delay: 0.6, duration: 0.5 } }}
                                whileHover={{ scale: 1.03 }}
                                whileTap={{ scale: 0.97 }}
                                className="mt-10 inline-block bg-[#f4f4f2] text-[#111] px-10 py-4 rounded-full text-sm font-bold tracking-widest uppercase hover:bg-white transition-colors"
                            >
                                Contact Us
                            </motion.a>
                        )}
                    </motion.div>
                </AnimatePresence>

                {/* ── Persistent video layer: ALL videos always mounted ── */}
                {VIDEO_BEATS.map(({ index, video }) => (
                    <div
                        key={video}
                        className={`mt-10 w-full max-w-4xl transition-opacity duration-500 ${
                            index === currentBeat ? 'opacity-100' : 'opacity-0 pointer-events-none absolute'
                        }`}
                        style={index !== currentBeat ? { position: 'absolute', width: 0, height: 0, overflow: 'hidden' } : undefined}
                    >
                        <div className="relative rounded-xl overflow-hidden border border-[#e0e0de] shadow-2xl bg-[#1a1a1a]">
                            {/* Browser-like top bar */}
                            <div className="flex items-center gap-2 px-4 py-3 bg-[#2a2a2a] border-b border-[#333]">
                                <span className="w-3 h-3 rounded-full bg-[#ff5f57]" />
                                <span className="w-3 h-3 rounded-full bg-[#febc2e]" />
                                <span className="w-3 h-3 rounded-full bg-[#28c840]" />
                                <span className="flex-1 mx-3 h-6 rounded-md bg-[#3a3a3a] flex items-center justify-center">
                                    <span className="text-[11px] text-[#888] font-mono">
                                        dfuse.site
                                    </span>
                                </span>
                            </div>
                            <video
                                ref={(el) => { videoRefs.current[index] = el; }}
                                src={video}
                                muted
                                playsInline
                                preload="auto"
                                onEnded={handleVideoEnded}
                                className="w-full block"
                            />
                        </div>
                    </div>
                ))}
            </div>

            {/* ── Bottom controls bar ── */}
            <div
                className={`absolute bottom-0 left-0 right-0 px-6 py-4 flex items-center justify-between ${
                    isDark ? 'text-[#666]' : 'text-[#999]'
                }`}
            >
                {/* Progress indicator */}
                <div className="flex items-center gap-1.5">
                    {BEATS.map((b, i) => (
                        <button
                            key={b.id}
                            type="button"
                            onClick={() => {
                                clearTimer();
                                setCurrentBeat(i);
                            }}
                            className={`h-1 rounded-full transition-all duration-500 ${
                                i === currentBeat
                                    ? `w-8 ${isDark ? 'bg-[#f4f4f2]' : 'bg-[#111]'}`
                                    : i < currentBeat
                                    ? `w-4 ${isDark ? 'bg-[#555]' : 'bg-[#aaa]'}`
                                    : `w-4 ${isDark ? 'bg-[#333]' : 'bg-[#ddd]'}`
                            }`}
                            aria-label={`Go to step ${i + 1}`}
                        />
                    ))}
                </div>

                {/* Navigation buttons */}
                <div className="flex items-center gap-3">
                    <button
                        type="button"
                        onClick={goPrev}
                        disabled={currentBeat <= 0}
                        className={`p-1.5 rounded-full transition-opacity ${
                            currentBeat <= 0 ? 'opacity-20 cursor-not-allowed' : 'hover:opacity-60'
                        }`}
                        aria-label="Previous"
                    >
                        <ChevronLeft size={18} />
                    </button>

                    <button
                        type="button"
                        onClick={togglePause}
                        className="p-1.5 rounded-full hover:opacity-60 transition-opacity"
                        aria-label={isPaused ? 'Resume' : 'Pause'}
                    >
                        {isPaused ? <Play size={16} /> : <Pause size={16} />}
                    </button>

                    <button
                        type="button"
                        onClick={goNext}
                        disabled={currentBeat >= BEATS.length - 1}
                        className={`p-1.5 rounded-full transition-opacity ${
                            currentBeat >= BEATS.length - 1 ? 'opacity-20 cursor-not-allowed' : 'hover:opacity-60'
                        }`}
                        aria-label="Next"
                    >
                        <ChevronRight size={18} />
                    </button>

                    <span className="text-xs font-bold tracking-widest uppercase ml-2">
                        {currentBeat + 1}/{BEATS.length}
                    </span>
                </div>
            </div>

            {/* ── Progress bar (top edge) ── */}
            <div className="absolute top-0 left-0 right-0 h-[2px]">
                <motion.div
                    className={isDark ? 'bg-[#f4f4f2] h-full' : 'bg-[#111] h-full'}
                    initial={{ width: '0%' }}
                    animate={{
                        width: `${((currentBeat + 1) / BEATS.length) * 100}%`,
                    }}
                    transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] as const }}
                />
            </div>
        </section>
    );
}
