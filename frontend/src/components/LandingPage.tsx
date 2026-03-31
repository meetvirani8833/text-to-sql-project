import { motion } from 'framer-motion';
import {
    ArrowRight,
    Database,
    Shield,
    Zap,
    MessagesSquare,
    Route,
    BadgeCheck,
    HelpCircle,
    Building2,
    Mail,
} from 'lucide-react';

interface LandingPageProps {
    onStartDemo: () => void;
}

const fadeUp = {
    initial: { opacity: 0, y: 24 },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true, margin: '-40px' },
    transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] as const },
};

export function LandingPage({ onStartDemo }: LandingPageProps) {
    return (
        <div className="min-h-screen bg-[#f4f4f2] text-[#111111] font-sans selection:bg-[#111] selection:text-[#f4f4f2] flex flex-col overflow-x-hidden">
            <nav className="sticky top-0 z-50 flex items-center justify-between px-6 py-6 border-b border-[#ddddda] bg-[#f4f4f2]/95 backdrop-blur-sm">
                <a href="#" className="flex items-center space-x-2 font-bold text-2xl tracking-tighter">
                    <span>Dfuse</span>
                    <span className="text-[10px] uppercase tracking-widest bg-[#111] text-[#f4f4f2] px-1.5 py-0.5 rounded-sm">
                        Data
                    </span>
                </a>

                <div className="hidden md:flex items-center space-x-10 text-sm font-medium tracking-tight">
                    <a href="#product" className="hover:opacity-60 transition-opacity">
                        Product
                    </a>
                    <a href="#method" className="hover:opacity-60 transition-opacity">
                        Approach
                    </a>
                    <a href="#who" className="hover:opacity-60 transition-opacity">
                        Who it&apos;s for
                    </a>
                    <a href="#contact" className="hover:opacity-60 transition-opacity">
                        Contact
                    </a>
                </div>

                <button
                    type="button"
                    onClick={onStartDemo}
                    className="text-sm font-semibold border-b-[1.5px] border-[#111] pb-0.5 hover:opacity-60 transition-opacity flex items-center space-x-1"
                >
                    <span>Try demo</span>
                    <ArrowRight size={14} />
                </button>
            </nav>

            <main className="flex-1 w-full">
                {/* Hero - subhead in normal flow so it never overlaps the headline */}
                <section className="px-6 pt-16 pb-20 md:pt-20 md:pb-24 max-w-7xl mx-auto">
                    <div className="max-w-5xl">
                        <motion.h1
                            initial={{ opacity: 0, y: 32 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.75, ease: [0.22, 1, 0.36, 1] }}
                            className="text-[2.75rem] sm:text-[4.5rem] md:text-[6rem] lg:text-[7.25rem] font-bold leading-[0.92] tracking-tighter uppercase"
                        >
                            <span className="block">
                                Talk to your
                            </span>
                            <span className="block mt-1 md:mt-2">
                                database
                            </span>
                        </motion.h1>

                        <motion.p
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.65, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
                            className="mt-10 md:mt-12 text-lg md:text-xl max-w-2xl font-medium tracking-tight leading-snug text-[#333]"
                        >
                            Turn large, connected operational databases into a simple question-and-answer experience.
                            Leaders and teams get trustworthy answers in seconds-without learning new tools or waiting
                            on a report queue.
                        </motion.p>

                        <motion.div
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.6, delay: 0.35 }}
                            className="mt-12 flex flex-col sm:flex-row sm:items-center gap-6 sm:gap-10"
                        >
                            <button
                                type="button"
                                onClick={onStartDemo}
                                className="bg-[#111] text-[#f4f4f2] px-8 py-4 rounded-full text-sm font-bold tracking-widest uppercase hover:bg-[#333] hover:scale-[1.02] active:scale-[0.98] transition-all w-full sm:w-auto text-center"
                            >
                                Start live demo
                            </button>
                            <div className="flex flex-wrap items-center gap-x-8 gap-y-3 text-xs font-bold uppercase tracking-widest text-[#111]">
                                <span className="flex items-center gap-2">
                                    <Database size={16} strokeWidth={1.75} />
                                    Your DATA
                                </span>
                                <span className="flex items-center gap-2">
                                    <Zap size={16} strokeWidth={1.75} />
                                    Answers in seconds
                                </span>
                                <span className="flex items-center gap-2">
                                    <Shield size={16} strokeWidth={1.75} />
                                    Governed access
                                </span>
                            </div>
                        </motion.div>
                    </div>
                </section>

                <div className="border-t border-[#111] mx-6 max-w-7xl xl:mx-auto" />

                {/* Product - benefits mapped from architecture, plain language */}
                <section id="product" className="px-6 py-20 md:py-28 max-w-7xl mx-auto scroll-mt-24">
                    <motion.div {...fadeUp} className="max-w-2xl">
                        <p className="text-xs font-bold uppercase tracking-widest text-[#666] mb-4">Product</p>
                        <h2 className="text-3xl md:text-4xl font-bold tracking-tight leading-tight">
                            Answers from the data you already trust-not a duplicate warehouse.
                        </h2>
                        <p className="mt-5 text-[#444] text-lg leading-relaxed font-medium">
                            Dfuse connects to your existing relational database, understands how tables relate, and
                            responds in everyday language. Built for organizations where one wrong number is one wrong
                            decision.
                        </p>
                    </motion.div>

                    <div className="mt-16 grid gap-px bg-[#111] border border-[#111] rounded-sm overflow-hidden md:grid-cols-2 lg:grid-cols-3">
                        {[
                            {
                                icon: MessagesSquare,
                                title: 'Plain-English questions',
                                body: 'Ask the way you would ask an analyst. The system translates intent into precise requests against your live database.',
                            },
                            {
                                icon: Route,
                                title: 'Complex relationships, handled',
                                body: 'Large schemas with many linked tables are mapped automatically so answers can span finance, operations, people, and more-without manual join diagrams.',
                            },
                            {
                                icon: Database,
                                title: 'Names that match how people talk',
                                body: 'Entity names like product lines, regions, and codes are matched to what stakeholders casually say-eliminating the need of typing exact names like "ZARA-W-JMP-SlimFit-Velvet-Blazer".',
                            },
                            {
                                icon: HelpCircle,
                                title: 'Clarification when it matters',
                                body: 'When a question could mean more than one thing, the experience pauses and asks you to choose-so you are not surprised by silent assumptions.',
                            },
                            {
                                icon: BadgeCheck,
                                title: 'Checked before it runs',
                                body: 'Requests are reviewed and validated against your structure before execution, so broken or unsafe pulls are caught early-not after the fact.',
                            },
                            {
                                icon: Shield,
                                title: 'Built for responsible use',
                                body: 'Designed around your access model and sensible safeguards, so exploration stays aligned with how your organization wants data used.',
                            },
                        ].map(({ icon: Icon, title, body }) => (
                            <motion.article
                                key={title}
                                {...fadeUp}
                                className="bg-[#f4f4f2] p-8 md:p-10 flex flex-col gap-4"
                            >
                                <Icon className="w-6 h-6 shrink-0" strokeWidth={1.75} />
                                <h3 className="text-lg font-bold tracking-tight">{title}</h3>
                                <p className="text-[#555] text-sm md:text-base leading-relaxed font-medium">{body}</p>
                            </motion.article>
                        ))}
                    </div>
                </section>

                {/* Method */}
                <section
                    id="method"
                    className="px-6 py-20 md:py-28 bg-[#eaeae8] border-y border-[#dcdcd8] scroll-mt-24"
                >
                    <div className="max-w-7xl mx-auto">
                        <motion.div {...fadeUp} className="max-w-2xl">
                            <p className="text-xs font-bold uppercase tracking-widest text-[#666] mb-4">Approach</p>
                            <h2 className="text-3xl md:text-4xl font-bold tracking-tight leading-tight">
                                From question to table, in a controlled loop you can stand behind.
                            </h2>
                        </motion.div>

                        <ol className="mt-16 grid gap-10 md:grid-cols-3 md:gap-12">
                            {[
                                {
                                    step: '01',
                                    title: 'Understand the ask',
                                    text: 'Your question is normalized and any fuzzy names are resolved against what really exists in your data.',
                                },
                                {
                                    step: '02',
                                    title: 'Gather the right context',
                                    text: 'Only the relevant parts of your schema are brought in, along with the right links between tables for that specific question.',
                                },
                                {
                                    step: '03',
                                    title: 'Answer with oversight',
                                    text: 'A draft path is checked, corrected if needed, then run-so stakeholders see both the narrative answer and the supporting figures.',
                                },
                            ].map(({ step, title, text }) => (
                                <motion.li key={step} {...fadeUp} className="relative pl-0 md:pl-0">
                                    <span className="text-xs font-bold uppercase tracking-widest text-[#888]">{step}</span>
                                    <h3 className="mt-3 text-xl font-bold tracking-tight">{title}</h3>
                                    <p className="mt-3 text-[#444] leading-relaxed font-medium">{text}</p>
                                </motion.li>
                            ))}
                        </ol>
                    </div>
                </section>

                {/* Who */}
                <section id="who" className="px-6 py-20 md:py-28 max-w-7xl mx-auto scroll-mt-24">
                    <motion.div
                        {...fadeUp}
                        className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-10 border-b border-[#111] pb-16"
                    >
                        <div className="max-w-2xl">
                            <p className="text-xs font-bold uppercase tracking-widest text-[#666] mb-4">
                                Who it&apos;s for
                            </p>
                            <h2 className="text-3xl md:text-4xl font-bold tracking-tight leading-tight">
                                We will fine-tune according to your requirements.
                            </h2>
                            <p className="mt-5 text-[#444] text-lg leading-relaxed font-medium">
                                The same underlying idea powers curriculum operations, supply chains, healthcare
                                administration, retail networks, and any environment where the truth lives in a big,
                                relational core system.
                            </p>
                        </div>
                        <div className="flex items-start gap-3 text-[#333] max-w-md">
                            <Building2 className="w-8 h-8 shrink-0" strokeWidth={1.5} />
                            <p className="text-sm md:text-base font-medium leading-relaxed">
                                Whether you say “students,” “members,” “SKUs,” or “policies,” Dfuse is about getting
                                consistent answers from the system of record-not maintaining yet another dashboard
                                forest.
                            </p>
                        </div>
                    </motion.div>
                </section>

                {/* Contact / CTA */}
                <section
                    id="contact"
                    className="px-6 py-20 md:py-24 max-w-7xl mx-auto scroll-mt-24 pb-28"
                >
                    <motion.div
                        {...fadeUp}
                        className="rounded-sm border border-[#111] bg-[#111] text-[#f4f4f2] p-10 md:p-14 flex flex-col md:flex-row md:items-center md:justify-between gap-10"
                    >
                        <div>
                            <p className="text-xs font-bold uppercase tracking-widest text-[#aaa] mb-3">Contact</p>
                            <h2 className="text-2xl md:text-3xl font-bold tracking-tight">
                                Contact us to see Dfuse on your schema and your toughest questions.
                            </h2>
                            <p className="mt-4 text-[#ccc] font-medium max-w-xl leading-relaxed">
                                Try the live demo on a sales database, then talk with us about pilot scope, access controls, and rollout
                                with your team.
                            </p>
                        </div>
                        <div className="flex flex-col sm:flex-row gap-4 shrink-0">
                            <button
                                type="button"
                                onClick={onStartDemo}
                                className="bg-[#f4f4f2] text-[#111] px-8 py-4 rounded-full text-sm font-bold tracking-widest uppercase hover:bg-white transition-colors"
                            >
                                Start live demo
                            </button>
                            <a
                                href="mailto:vmeet062@gmail.com"
                                className="inline-flex items-center justify-center gap-2 border border-[#555] text-[#f4f4f2] px-8 py-4 rounded-full text-sm font-bold tracking-widest uppercase hover:border-[#888] transition-colors"
                            >
                                <Mail size={16} />
                                Email us
                            </a>
                        </div>
                    </motion.div>

                    <footer className="mt-16 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 text-xs font-bold uppercase tracking-widest text-[#888]">
                        <span>© {new Date().getFullYear()} Dfuse Data</span>
                        <span className="text-[#aaa] normal-case font-medium tracking-tight">
                            Natural language over the database you already run.
                        </span>
                    </footer>
                </section>
            </main>
        </div>
    );
}
