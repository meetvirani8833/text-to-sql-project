import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import emailjs from '@emailjs/browser';
import { Send, CheckCircle2, RotateCcw, Loader2 } from 'lucide-react';

export function ContactForm() {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [message, setMessage] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isSubmitted, setIsSubmitted] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (localStorage.getItem('dfuse_contact_submitted') === 'true') {
            setIsSubmitted(true);
        }
    }, []);

    const resetForm = () => {
        localStorage.removeItem('dfuse_contact_submitted');
        setIsSubmitted(false);
        setName('');
        setEmail('');
        setMessage('');
        setError('');
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setIsSubmitting(true);

        const serviceId = import.meta.env.VITE_EMAILJS_SERVICE_ID;
        const templateId = import.meta.env.VITE_EMAILJS_TEMPLATE_ID;
        const publicKey = import.meta.env.VITE_EMAILJS_PUBLIC_KEY;

        if (!serviceId || !templateId || !publicKey) {
            setError('Contact service is not configured yet. Please email us directly.');
            setIsSubmitting(false);
            return;
        }

        try {
            await emailjs.send(
                serviceId,
                templateId,
                {
                    from_name: name,
                    from_email: email,
                    message: message,
                },
                publicKey
            );
            localStorage.setItem('dfuse_contact_submitted', 'true');
            setIsSubmitted(true);
        } catch (err) {
            console.error('EmailJS error:', err);
            setError('Failed to send request. Please try again or email us directly.');
        } finally {
            setIsSubmitting(false);
        }
    };

    if (isSubmitted) {
        return (
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="w-full h-full min-h-[400px] flex flex-col items-center justify-center text-center p-6 md:p-8 bg-[#1a1a1a] rounded-xl border border-[#333]"
            >
                <div className="w-16 h-16 bg-[#28c840]/20 text-[#28c840] rounded-full flex items-center justify-center mb-6">
                    <CheckCircle2 size={32} />
                </div>
                <h3 className="text-2xl font-bold tracking-tight text-[#f4f4f2] mb-3">
                    Request Received
                </h3>
                <p className="text-[#ccc] font-medium leading-relaxed max-w-sm mb-8">
                    Your inquiry has been successfully sent. We will get back to you within 24 hours.
                </p>
                <button
                    type="button"
                    onClick={resetForm}
                    className="flex items-center gap-2 text-sm font-semibold tracking-widest uppercase text-[#888] hover:text-[#f4f4f2] transition-colors"
                >
                    <RotateCcw size={14} />
                    Submit another request
                </button>
            </motion.div>
        );
    }

    return (
        <form onSubmit={handleSubmit} className="flex flex-col w-full h-full min-h-[400px] p-6 md:p-8 bg-[#1a1a1a] rounded-xl text-[#f4f4f2] border border-[#333]">
            <h3 className="text-xl font-bold tracking-tight mb-6">Send us a message</h3>
            
            {error && (
                <div className="text-sm font-medium text-[#ff5f57] bg-[#ff5f57]/10 px-4 py-3 rounded-md border border-[#ff5f57]/20 mb-6">
                    {error}
                </div>
            )}
            
            <div className="flex flex-col gap-4 mb-6">
                <div>
                    <label htmlFor="name" className="sr-only">Name</label>
                    <input
                        type="text"
                        id="name"
                        required
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Your Name"
                        className="w-full bg-[#111] border border-[#333] text-[#f4f4f2] px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#f4f4f2] focus:border-transparent transition-all font-medium placeholder-[#555]"
                    />
                </div>
                <div>
                    <label htmlFor="email" className="sr-only">Work Email</label>
                    <input
                        type="email"
                        id="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="Work Email"
                        className="w-full bg-[#111] border border-[#333] text-[#f4f4f2] px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#f4f4f2] focus:border-transparent transition-all font-medium placeholder-[#555]"
                    />
                </div>
                <div>
                    <label htmlFor="message" className="sr-only">Inquiry</label>
                    <textarea
                        id="message"
                        required
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        placeholder="Tell us about your requirements..."
                        rows={4}
                        className="w-full bg-[#111] border border-[#333] text-[#f4f4f2] px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#f4f4f2] focus:border-transparent transition-all font-medium placeholder-[#555] resize-none"
                    />
                </div>
            </div>

            <button
                type="submit"
                disabled={isSubmitting}
                className="mt-auto w-full flex items-center justify-center gap-2 bg-[#f4f4f2] text-[#111] px-6 py-4 rounded-full text-sm font-bold tracking-widest uppercase hover:bg-white hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 disabled:pointer-events-none"
            >
                {isSubmitting ? (
                    <>
                        <Loader2 size={18} className="animate-spin" />
                        Sending...
                    </>
                ) : (
                    <>
                        <Send size={18} />
                        Send Message
                    </>
                )}
            </button>
        </form>
    );
}
