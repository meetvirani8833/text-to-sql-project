interface StatusIndicatorProps {
    status: string | null;
}

export function StatusIndicator({ status }: StatusIndicatorProps) {
    if (!status) return null;

    return (
        <div className="flex justify-center my-4 animate-fade-in slide-up">
            <div className="flex items-center space-x-2 bg-[#111]/90 backdrop-blur-md px-4 py-2 rounded-full border border-[#333] shadow-lg text-[#f4f4f2] text-sm">
                <div className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#f4f4f2] opacity-35"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-[#f4f4f2]"></span>
                </div>
                <span className="font-medium animate-pulse">{status}</span>
            </div>
        </div>
    );
}
