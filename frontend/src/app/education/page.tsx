"use client";

import Link from "next/link";
import { ArrowLeft, BookOpen, TrendingUp, Users, Award, DollarSign } from "lucide-react";

export default function EducationPage() {
  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto p-6">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-blue-600 mb-6">
          <ArrowLeft className="w-4 h-4" /> Back to Home
        </Link>

        {/* Hero */}
        <div className="bg-gradient-to-r from-emerald-600 to-teal-700 rounded-3xl p-10 mb-10 text-white">
          <h1 className="text-4xl font-bold mb-4">For Bootcamps & Educators</h1>
          <p className="text-lg text-emerald-100 max-w-2xl mb-6">
            Design curricula that guarantee job placement and salary bumps
            for your graduates — backed by real labor market data.
          </p>
          <Link href="/education"
            className="inline-flex items-center gap-2 px-6 py-3 bg-white text-emerald-700 rounded-xl font-semibold hover:bg-emerald-50 transition">
            Get Curriculum Insights
          </Link>
        </div>

        {/* Feature cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <BookOpen className="w-8 h-8 text-emerald-600 mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Data-Driven Curriculum</h3>
            <p className="text-gray-600 text-sm">
              Know which skills to teach next. Design programs around skills
              with guaranteed market demand and highest salary premiums.
            </p>
          </div>
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <Award className="w-8 h-8 text-amber-600 mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Outcome Guarantees</h3>
            <p className="text-gray-600 text-sm">
              Back your job placement promises with data. Show prospective
              students the exact salary uplift your program delivers.
            </p>
          </div>
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <DollarSign className="w-8 h-8 text-blue-600 mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Salary Projections</h3>
            <p className="text-gray-600 text-sm">
              Project realistic graduate salaries based on the skills you teach
              and current market conditions.
            </p>
          </div>
        </div>

        {/* Stats */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <h3 className="text-xl font-bold text-gray-900 mb-6">Why Educators Choose Lumina</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
            <div>
              <Users className="w-8 h-8 text-blue-600 mx-auto mb-2" />
              <p className="text-3xl font-bold text-gray-900">10k+</p>
              <p className="text-sm text-gray-500 mt-1">Jobs analyzed daily</p>
            </div>
            <div>
              <TrendingUp className="w-8 h-8 text-green-600 mx-auto mb-2" />
              <p className="text-3xl font-bold text-gray-900">+35%</p>
              <p className="text-sm text-gray-500 mt-1">Average graduate salary uplift</p>
            </div>
            <div>
              <Award className="w-8 h-8 text-amber-600 mx-auto mb-2" />
              <p className="text-3xl font-bold text-gray-900">92%</p>
              <p className="text-sm text-gray-500 mt-1">Student satisfaction with career outcomes</p>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}