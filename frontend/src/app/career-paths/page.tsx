"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, TrendingUp } from "lucide-react";
import { fetchSkillOverlaps } from "@/lib/api";

export default function CareerPathsPage() {
  const { data: overlaps, isLoading, error } = useQuery({
    queryKey: ["skillOverlaps", 50],
    queryFn: () => fetchSkillOverlaps(50),
  });

  const [searchTerm, setSearchTerm] = useState("");

  const filtered = (overlaps?.data ?? []).filter((o) =>
    o.skill_combo.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto p-6">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-blue-600 mb-6">
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </Link>

        <h1 className="text-3xl font-bold text-gray-900 mb-2">Career Paths & Skill Combinations</h1>
        <p className="text-gray-600 mb-6">
          Discover which skill combinations deliver the highest ROI. Combine your skills
          strategically to maximize earning potential.
        </p>

        {/* Search */}
        <input
          type="text"
          placeholder="Search skill combos (e.g., Python, AWS)..."
          className="w-full px-4 py-3 mb-8 rounded-xl border border-gray-200 shadow-sm focus:ring-2 focus:ring-blue-500 outline-none"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />

        {isLoading && <p className="text-gray-500 text-center py-12">Loading career path data...</p>}

        {error && (
          <div className="text-center py-12">
            <p className="text-red-500 mb-4">Failed to load career path data. Is the backend running?</p>
            <Link href="/" className="text-blue-600 underline">Back to dashboard</Link>
          </div>
        )}

        {filtered.length === 0 && !isLoading && !error && (
          <p className="text-gray-500 text-center py-12">No skill combinations found.</p>
        )}

        {/* Combo cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {filtered.slice(0, 30).map((combo) => {
            const skills = combo.skill_combo.split(", ");
            return (
              <div key={combo.skill_combo} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow">
                <div className="flex flex-wrap gap-2 mb-4">
                  {skills.map((s) => (
                    <Link key={s} href={`/skills/${encodeURIComponent(s)}`}
                      className="px-2.5 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-medium hover:bg-blue-100 transition">
                      {s}
                    </Link>
                  ))}
                </div>
                <div className="flex flex-wrap justify-between items-end gap-4">
                  <div>
                    <p className="text-sm text-gray-500 mb-1">Combined Avg Salary</p>
                    <p className="text-2xl font-bold text-gray-900">
                      ${combo.combo_avg_salary.toLocaleString()}
                    </p>
                  </div>
                  <div className={`flex items-center gap-1 px-3 py-1.5 rounded-lg ${combo.combo_premium >= 0 ? "bg-green-50" : "bg-red-50"}`}>
                    <TrendingUp className={`w-4 h-4 ${combo.combo_premium >= 0 ? "text-green-600" : "text-red-600"}`} />
                    <span className={`text-sm font-bold ${combo.combo_premium >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {combo.combo_premium >= 0 ? "+" : ""}${combo.combo_premium.toLocaleString()}
                    </span>
                  </div>
                </div>
                <div className="mt-4 flex justify-between items-center">
                  <p className="text-xs text-gray-400">{combo.combo_demand_count} jobs require this combo</p>
                  <p className="text-xs text-gray-400">Premium vs market</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </main>
  );
}