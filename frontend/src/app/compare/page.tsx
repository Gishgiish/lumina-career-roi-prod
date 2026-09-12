"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Search, TrendingUp, TrendingDown, Briefcase } from "lucide-react";
import { compareSkills, fetchSkillNames } from "@/lib/api";

export default function ComparePage() {
  const [selected, setSelected] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const { data: skills } = useQuery({ queryKey: ["skillNames"], queryFn: fetchSkillNames });

  const { data: result, isLoading } = useQuery({
    queryKey: ["compare", selected],
    queryFn: () => compareSkills(selected),
    enabled: selected.length >= 2,
  });

  const available = (skills ?? []).filter(
    (s) => !selected.includes(s) && s.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const toggleSkill = (skill: string) => {
    setSelected((prev) =>
      prev.includes(skill) ? prev.filter((s) => s !== skill) : [...prev, skill]
    );
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto p-6">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-blue-600 mb-6">
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </Link>

        <h1 className="text-3xl font-bold text-gray-900 mb-2">Compare Skills</h1>
        <p className="text-gray-600 mb-8">Select 2+ skills to compare their market ROI side-by-side.</p>

        {/* Selected skills */}
        <div className="flex flex-wrap gap-2 mb-6">
          {selected.length === 0 && (
            <p className="text-gray-400 text-sm">No skills selected. Choose from the list below.</p>
          )}
          {selected.map((s) => (
            <button key={s} onClick={() => toggleSkill(s)}
              className="px-3 py-1.5 bg-blue-600 text-white rounded-full text-sm font-medium hover:bg-blue-700">
              {s} ×
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
          <input
            type="text"
            placeholder="Search skills..."
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-200 focus:ring-2 focus:ring-blue-500 outline-none"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        {/* Skill picker */}
        <div className="flex flex-wrap gap-2 mb-8 max-h-40 overflow-y-auto">
          {available.slice(0, 30).map((s) => (
            <button key={s} onClick={() => toggleSkill(s)}
              className="px-3 py-1 bg-white border border-gray-200 rounded-full text-sm hover:border-blue-400 hover:text-blue-600 transition">
              {s}
            </button>
          ))}
        </div>

        {/* Results */}
        {isLoading && <p className="text-gray-500">Loading comparison...</p>}
        {result && result.skills.length > 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700 w-48">Skill</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Avg Salary</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Premium</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Demand</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {result.skills.map((skill) => (
                  <tr key={skill.skill} className="hover:bg-gray-50">
                    <td className="px-6 py-4 font-medium text-gray-900 capitalize">
                      <Link href={`/skills/${encodeURIComponent(skill.skill)}`} className="hover:text-blue-600">
                        {skill.skill}
                      </Link>
                    </td>
                    <td className="px-6 py-4 text-gray-700">${skill.avg_salary.toLocaleString()}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1">
                        {skill.salary_premium >= 0 ?
                          <TrendingUp className="text-green-600 w-4 h-4" /> :
                          <TrendingDown className="text-red-600 w-4 h-4" />}
                        <span className={skill.salary_premium >= 0 ? "text-green-600 font-medium" : "text-red-600 font-medium"}>
                          {skill.salary_premium >= 0 ? "+" : ""}${skill.salary_premium.toLocaleString()}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-gray-700">
                      <div className="flex items-center gap-1">
                        <Briefcase className="w-3 h-3 text-gray-400" /> {skill.job_demand_count}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Ranking bar */}
            <div className="p-6 bg-gray-50 border-t border-gray-100">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Ranking by Salary Premium</h3>
              <div className="flex flex-col gap-2">
                {[...result.skills].sort((a, b) => b.salary_premium - a.salary_premium).map((skill, idx) => (
                  <div key={skill.skill} className="flex items-center gap-3">
                    <span className="w-6 text-sm font-bold text-gray-500">#{idx + 1}</span>
                    <span className="w-32 text-sm font-medium text-gray-800 capitalize">{skill.skill}</span>
                    <div className="flex-1 bg-gray-200 rounded-full h-2.5 overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.max(5, (skill.salary_premium / (result.skills[0]?.salary_premium || 1)) * 100)}%`,
                          backgroundColor: skill.salary_premium >= 0 ? "#3b82f6" : "#ef4444",
                        }}
                      />
                    </div>
                    <span className="text-xs text-gray-500">+${skill.salary_premium.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}