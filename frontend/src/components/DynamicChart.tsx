import {
    BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
    XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

interface DynamicChartProps {
    config: {
        chart_type: string;
        x_axis_key: string;
        y_axis_keys: string[];
    };
    data: any[];
}

/* Refined palette — harmonious, modern, accessible */
const PALETTE = [
    '#111111',
    '#6366f1',  // indigo
    '#f59e0b',  // amber
    '#10b981',  // emerald
    '#ef4444',  // red
    '#8b5cf6',  // violet
    '#ec4899',  // pink
    '#06b6d4',  // cyan
];

const tooltipStyle = {
    borderRadius: '10px',
    border: '1px solid #e5e5e5',
    fontSize: '12px',
    padding: '8px 12px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
    background: '#fff',
};

const axisTickStyle = { fontSize: 11, fill: '#888' };

/* Beautify raw keys: total_revenue → Total Revenue */
function formatLabel(key: string): string {
    return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function DynamicChart({ config, data }: DynamicChartProps) {
    if (!data || data.length === 0 || !config) return null;

    const { chart_type, x_axis_key, y_axis_keys } = config;
    if (!x_axis_key || !y_axis_keys || y_axis_keys.length === 0) {
        return <div className="p-4 text-xs text-red-500">Invalid chart configuration.</div>;
    }

    const chartHeight = 280;

    /* Truncate labels longer than 14 chars */
    const truncateLabel = (label: string) => {
        const s = String(label);
        return s.length > 14 ? s.slice(0, 12) + '…' : s;
    };

    const needsRotation = data.length > 4;

    const sharedCartesian = (
        <>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
            <XAxis
                dataKey={x_axis_key}
                axisLine={false}
                tickLine={false}
                tick={axisTickStyle}
                tickFormatter={truncateLabel}
                interval={0}
                angle={needsRotation ? -35 : 0}
                textAnchor={needsRotation ? 'end' : 'middle'}
                height={needsRotation ? 70 : 40}
            />
            <YAxis axisLine={false} tickLine={false} tick={axisTickStyle} width={55} />
            <Tooltip cursor={{ fill: 'rgba(0,0,0,0.03)' }} contentStyle={tooltipStyle} />
            <Legend
                iconType="circle"
                iconSize={8}
                wrapperStyle={{ fontSize: 12, paddingTop: '12px' }}
                formatter={(value: string) => formatLabel(value)}
            />
        </>
    );

    const renderBarChart = () => (
        <ResponsiveContainer width="100%" height={chartHeight}>
            <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                {sharedCartesian}
                {y_axis_keys.map((key, idx) => (
                    <Bar
                        key={key}
                        dataKey={key}
                        name={formatLabel(key)}
                        fill={PALETTE[idx % PALETTE.length]}
                        radius={[4, 4, 0, 0]}
                        maxBarSize={48}
                    />
                ))}
            </BarChart>
        </ResponsiveContainer>
    );

    const renderLineChart = () => (
        <ResponsiveContainer width="100%" height={chartHeight}>
            <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                {sharedCartesian}
                {y_axis_keys.map((key, idx) => (
                    <Line
                        key={key}
                        type="monotone"
                        dataKey={key}
                        name={formatLabel(key)}
                        stroke={PALETTE[idx % PALETTE.length]}
                        strokeWidth={2.5}
                        dot={{ r: 3, strokeWidth: 2 }}
                        activeDot={{ r: 5 }}
                    />
                ))}
            </LineChart>
        </ResponsiveContainer>
    );

    const renderPieChart = () => {
        const yKey = y_axis_keys[0];
        return (
            <ResponsiveContainer width="100%" height={chartHeight}>
                <PieChart>
                    <Tooltip contentStyle={tooltipStyle} />
                    <Legend
                        iconType="circle"
                        iconSize={8}
                        wrapperStyle={{ fontSize: 11 }}
                        formatter={(value: string) => formatLabel(value)}
                    />
                    <Pie
                        data={data}
                        dataKey={yKey}
                        nameKey={x_axis_key}
                        cx="50%"
                        cy="50%"
                        outerRadius="75%"
                        innerRadius="50%"
                        paddingAngle={3}
                        strokeWidth={0}
                    >
                        {data.map((_, index) => (
                            <Cell key={`cell-${index}`} fill={PALETTE[index % PALETTE.length]} />
                        ))}
                    </Pie>
                </PieChart>
            </ResponsiveContainer>
        );
    };

    return (
        <div className="w-full bg-white p-4 sm:p-6 rounded-lg border border-[#e5e5e5] mt-3 shadow-sm">
            <div className="text-[10px] font-bold uppercase tracking-widest text-[#bbb] mb-4">
                {formatLabel(chart_type)} Chart
            </div>
            {chart_type === 'bar' && renderBarChart()}
            {chart_type === 'line' && renderLineChart()}
            {chart_type === 'pie' && renderPieChart()}
            {!['bar', 'line', 'pie'].includes(chart_type) && (
                <div className="text-center py-8 text-xs text-[#999]">
                    Unsupported chart type: {chart_type}
                </div>
            )}
        </div>
    );
}
