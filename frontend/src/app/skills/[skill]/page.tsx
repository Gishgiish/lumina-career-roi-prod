"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { fetchSkillDetail } from "@/lib/api";
import { TrendingUp, TrendingDown, Briefcase, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

export default function SkillDetailPage() {
  const params = useParams();
  const skillName = decodeURIComponent(String(params.skill ?? ""));

  const { data: skill, isLoading, error } = useQuery({
    queryKey: ["skillDetail", skillName],
    queryFn: () => fetchSkillDetail(skillName),
    enabled: !!skillName,
  });

  if (isLoading) return <div className="flex min-h-screen items-center justify-center text-xl text-gray-500">Loading skill data...</div>;
  if (error || !skill) return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-xl text-red-500">
      <p>Skill not found or API unavailable.</p>
      <Link href="/" className="text-blue-600 underline">Back to dashboard</Link>
    </div>
  );

  const chartData = (skill.salary_distribution ?? []).map((b) => ({
    bucket: b.salary_bucket,
    jobs: b.job_count,
  }));

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto p-6">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-blue-600 mb-6">
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </Link>

        {/* Hero */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 mb-8">
          <div className="flex flex-wrap justify-between items-start gap-4">
            <div>
              <h1 className="text-4xl font-bold text-gray-900 capitalize mb-2">{skill.skill}</h1>
              <p className="text-gray-500">Skill ROI & Market Intelligence</p>
            </div>
            <span className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium bg-gray-100 text-gray-700">
              <Briefcase size={14} /> {skill.job_demand_count} jobs
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-8">
            <div className="p-4 rounded-xl bg-gray-50">
              <p className="text-sm text-gray-500 mb-1">Average Salary</p>
              <p className="text-2xl font-bold text-gray-900">${skill.avg_salary.toLocaleString()}</p>
            </div>
            <div className={`p-4 rounded-xl ${skill.salary_premium >= 0 ? "bg-green-50" : "bg-red-50"}`}>
              <p className={`text-sm mb-1 ${skill.salary_premium >= 0 ? "text-green-800" : "text-red-800"}`}>Salary Premium</p>
              <div className="flex items-center gap-2">
                {skill.salary_premium >= 0 ? <TrendingUp className="text-green-600" size={20} /> : <TrendingDown className="text-red-600" size={20} />}
                <p className={`text-2xl font-bold ${skill.salary_premium >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {skill.salary_premium >= 0 ? "+" : ""}${skill.salary_premium.toLocaleString()}
                </p>
              </div>
            </div>
            <div className="p-4 rounded-xl bg-blue-50">
              <p className="text-sm text-blue-800 mb-1">Demand</p>
              <p className="text-2xl font-bold text-blue-700">{skill.job_demand_count} jobs</p>
            </div>
          </div>
        </div>

        {/* Salary distribution */}
        {chartData.length > 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Salary Distribution</h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="bucket" stroke="#9ca3af" angle={-30} textAnchor="end" height={60} />
                  <YAxis stroke="#6b7280" />
                  <Tooltip formatter={(v: number) => [`${v} jobs`, "Job Count"]} contentStyle={{ borderRadius: 8 }} />
                  <Bar dataKey="jobs" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Related skills */}
        {skill.related_skills && skill.related_skills.length > 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Related Skills</h2>
            <div className="flex flex-wrap gap-2">
              {skill.related_skills.map((r) => (
                <Link key={r.skill} href={`/skills/${encodeURIComponent(r.skill)}`}
                  className="px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm font-medium hover:border-blue-400 hover:text-blue-600 transition">
                  {r.skill} <span className="text-gray-400 text-xs ml-1">({r.co_occurrence_count})</span>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}