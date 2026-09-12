"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchAllSkillsROI, fetchMarketOverview } from "@/lib/api";
import { TrendingUp, TrendingDown, Search, Briefcase, ArrowRight } from "lucide-react";
import { useState } from "react";
import Link from "next/link";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from "recharts";

export default function Home() {
  const { data, isLoading, error } = useQuery({ queryKey: ["skillsROI"], queryFn: fetchAllSkillsROI });
  const { data: market } = useQuery({ queryKey: ["marketOverview"], queryFn: fetchMarketOverview });
  const [searchTerm, setSearchTerm] = useState("");

  const filteredSkills = data?.data.filter((s) =>
    s.skill.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (isLoading) return <div className="flex min-h-screen items-center justify-center text-xl text-gray-500">Loading Market Intelligence...</div>;
  if (error) return <div className="flex min-h-screen items-center justify-center text-xl text-red-500">Failed to connect to Lumina API. Is the backend running on port 8000?</div>;

  const chartData = (data?.data ?? []).slice(0, 10).map((s) => ({ name: s.skill, premium: Math.round(s.salary_premium) }));
  const m = market?.metrics ?? {};

  const cards = [
    { label: "Tracked Skills", value: String(m.total_unique_skills ?? data?.total_skills ?? 0) },
    { label: "Jobs Analyzed", value: m.total_jobs ? Math.round(m.total_jobs).toLocaleString() : "—" },
    { label: "Avg Salary", value: m.average_salary_usd ? `$${Math.round(m.average_salary_usd).toLocaleString()}` : "—" },
    { label: "Median Salary", value: m.median_salary_usd ? `$${Math.round(m.median_salary_usd).toLocaleString()}` : "—" },
  ];

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto p-4 md:p-8">
        <header className="mb-8 text-center">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 tracking-tight">
            Lumina Career <span className="text-blue-600">ROI</span>
          </h1>
          <p className="mt-3 text-lg text-gray-600 max-w-2xl mx-auto">
            Calculate the exact financial return on investment of your next technical skill.
          </p>
          <div className="flex justify-center gap-3 mt-6 flex-wrap">
            <Link href="/compare" className="px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm font-medium hover:border-blue-400 hover:text-blue-600 transition">Compare Skills</Link>
            <Link href="/career-paths" className="px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm font-medium hover:border-blue-400 hover:text-blue-600 transition">Career Paths</Link>
          </div>
        </header>

        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
          {cards.map((c) => (
            <div key={c.label} className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <p className="text-sm text-gray-500 font-medium mb-2">{c.label}</p>
              <p className="text-2xl font-bold text-gray-900">{c.value}</p>
            </div>
          ))}
        </div>

        {/* Top 10 chart */}
        {chartData.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Top 10 Skills by Salary Premium</h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis type="number" tickFormatter={(v) => `$${v.toLocaleString()}`} stroke="#9ca3af" />
                  <YAxis type="category" dataKey="name" width={120} stroke="#6b7280" />
                  <Tooltip formatter={(v: number) => [`$${v.toLocaleString()}`, "Premium"]} contentStyle={{ borderRadius: 8 }} />
                  <Bar dataKey="premium" radius={[0, 4, 4, 0]}>
                    {chartData.map((e, i) => <Cell key={i} fill={e.premium >= 0 ? "#3b82f6" : "#ef4444"} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Search */}
        <div className="mb-8 max-w-xl mx-auto relative">
          <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
          <input type="text" placeholder="Search for a skill (e.g., Python, AWS, Docker)..."
            className="w-full pl-12 pr-4 py-4 rounded-xl border border-gray-200 shadow-sm focus:ring-2 focus:ring-blue-500 outline-none text-lg"
            value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} />
        </div>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredSkills?.map((skill) => (
            <Link href={`/skills/${encodeURIComponent(skill.skill)}`} key={skill.skill}
              className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow block">
              <div className="flex justify-between items-start mb-4">
                <h3 className="text-2xl font-bold text-gray-900 capitalize">{skill.skill}</h3>
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                  <Briefcase size={12} /> {skill.job_demand_count} jobs
                </span>
              </div>
              <p className="text-sm text-gray-500 mb-1">Average Salary</p>
              <p className="text-3xl font-semibold text-gray-800 mb-4">${skill.avg_salary.toLocaleString()}</p>
              <div className={`flex items-center gap-2 p-3 rounded-lg ${skill.salary_premium >= 0 ? "bg-green-50" : "bg-red-50"}`}>
                {skill.salary_premium >= 0 ? <TrendingUp className="text-green-600" size={24} /> : <TrendingDown className="text-red-600" size={24} />}
                <div>
                  <p className={`text-xs font-medium ${skill.salary_premium >= 0 ? "text-green-800" : "text-red-800"}`}>Market Premium</p>
                  <p className={`text-xl font-bold ${skill.salary_premium >= 0 ? "text-green-600" : "text-red-600"}`}>
                    {skill.salary_premium >= 0 ? "+" : ""}${skill.salary_premium.toLocaleString()}
                  </p>
                </div>
              </div>
              <p className="mt-4 text-sm text-blue-600 font-medium inline-flex items-center gap-1">
                View details <ArrowRight className="w-3 h-3" />
              </p>
            </Link>
          ))}
        </div>

        {filteredSkills?.length === 0 && (
          <div className="text-center text-gray-500 mt-10 text-lg">No skills found matching `{searchTerm}`.</div>
        )}
      </div>
    </main>
  );
}