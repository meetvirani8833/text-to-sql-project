import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface DynamicChartProps {
    config: {
        chart_type: string;
        x_axis_key: string;
        y_axis_keys: string[];
    };
    data: any[];
}

const COLORS = ['#111111', '#555555', '#a0a0a0', '#cccccc'];

export function DynamicChart({ config, data }: DynamicChartProps) {
    if (!data || data.length === 0 || !config) return null;

    const { chart_type, x_axis_key, y_axis_keys } = config;

    // Safety fallback
    if (!x_axis_key || !y_axis_keys || y_axis_keys.length === 0) return <div className="p-4 text-xs text-red-500">Invalid chart configuration.</div>;

    const renderBarChart = () => (
        <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
                <XAxis dataKey={x_axis_key} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#666' }} interval={0} angle={-25} textAnchor="end" height={50} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#666' }} />
                <Tooltip cursor={{ fill: '#f4f4f2' }} contentStyle={{ borderRadius: '8px', border: '1px solid #ddd', fontSize: '12px' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: '20px' }} />
                {y_axis_keys.map((key, idx) => (
                    <Bar key={key} dataKey={key} fill={COLORS[idx % COLORS.length]} radius={[4, 4, 0, 0]} maxBarSize={60} />
                ))}
            </BarChart>
        </ResponsiveContainer>
    );

    const renderLineChart = () => (
        <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
                <XAxis dataKey={x_axis_key} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#666' }} interval={0} angle={-25} textAnchor="end" height={50} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#666' }} />
                <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #ddd', fontSize: '12px' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: '20px' }} />
                {y_axis_keys.map((key, idx) => (
                    <Line key={key} type="monotone" dataKey={key} stroke={COLORS[idx % COLORS.length]} strokeWidth={3} activeDot={{ r: 6 }} />
                ))}
            </LineChart>
        </ResponsiveContainer>
    );

    const renderPieChart = () => {
        const yKey = y_axis_keys[0]; // Pie charts naturally take one value key
        return (
            <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                    <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #ddd', fontSize: '12px' }} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                    <Pie
                        data={data}
                        dataKey={yKey}
                        nameKey={x_axis_key}
                        cx="50%"
                        cy="50%"
                        outerRadius={100}
                        innerRadius={60}
                        paddingAngle={5}
                        fill="#111"
                        labelLine={false}
                    >
                        {data.map((_, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                    </Pie>
                </PieChart>
            </ResponsiveContainer>
        );
    };

    return (
        <div className="w-full bg-[#fcfcfc] p-6 rounded-xl border border-[#ebebeb] mt-6 shadow-sm animate-fade-in group hover:border-[#ddd] transition-colors">
            <h3 className="text-xs font-bold uppercase tracking-widest text-[#888] mb-6 text-center select-none">
                Data Visualization - {chart_type}
            </h3>
            {chart_type === 'bar' && renderBarChart()}
            {chart_type === 'line' && renderLineChart()}
            {chart_type === 'pie' && renderPieChart()}
            {['bar', 'line', 'pie'].indexOf(chart_type) === -1 && (
                <div className="text-center py-10 text-xs text-[#888]">Unsupported chart type: {chart_type}</div>
            )}
        </div>
    );
}
