"use client";

import Link from "next/link";
import { ArrowLeft, TrendingUp, BarChart3, Users, GraduationCap, DollarSign } from "lucide-react";

export default function BusinessPage() {
  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto p-6">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-blue-600 mb-6">
          <ArrowLeft className="w-4 h-4" /> Back to Home
        </Link>

        {/* Hero */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-3xl p-10 mb-10 text-white">
          <h1 className="text-4xl font-bold mb-4">For L&D Directors</h1>
          <p className="text-lg text-blue-100 max-w-2xl mb-6">
            Justify every training dollar with data. Prove the financial ROI of
            upskilling your workforce with real labor market intelligence.
          </p>
          <Link href="/business"
            className="inline-flex items-center gap-2 px-6 py-3 bg-white text-blue-700 rounded-xl font-semibold hover:bg-blue-50 transition">
            Book a Demo
          </Link>
        </div>

        {/* Feature cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <BarChart3 className="w-8 h-8 text-blue-600 mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Skill Market Intelligence</h3>
            <p className="text-gray-600 text-sm">
              Track in-demand skills across global job markets. Know what skills
              will give your workforce the biggest salary uplift.
            </p>
          </div>
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <DollarSign className="w-8 h-8 text-green-600 mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Training ROI Calculator</h3>
            <p className="text-gray-600 text-sm">
              Calculate the exact salary premium of each skill before you invest
              in training. Compare training costs vs. expected ROI.
            </p>
          </div>
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <Users className="w-8 h-8 text-purple-600 mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Workforce Planning</h3>
            <p className="text-gray-600 text-sm">
              Identify skill gaps in your team and get recommendations for the
              highest-ROI upskilling paths.
            </p>
          </div>
        </div>

        {/* API/Integration section */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 mb-8">
          <div className="flex flex-wrap items-center justify-between gap-6">
            <div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Enterprise API Access</h3>
              <p className="text-gray-600 max-w-xl">
                Integrate {"Lumina's"} market intelligence directly into your LMS,
                skill matrix, or internal analytics dashboards via our API.
              </p>
            </div>
            <Link href="/compare"
              className="px-6 py-3 bg-gray-900 text-white rounded-xl font-semibold hover:bg-gray-800 transition">
              Explore the API
            </Link>
          </div>
        </div>

        {/* Stats */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <h3 className="text-xl font-bold text-gray-900 mb-6">Why Companies Choose Lumina</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
            <div>
              <TrendingUp className="w-8 h-8 text-green-600 mx-auto mb-2" />
              <p className="text-3xl font-bold text-gray-900">+$30K</p>
              <p className="text-sm text-gray-500 mt-1">Average skill premium identified</p>
            </div>
            <div>
              <GraduationCap className="w-8 h-8 text-blue-600 mx-auto mb-2" />
              <p className="text-3xl font-bold text-gray-900">100+</p>
              <p className="text-sm text-gray-500 mt-1">Skills tracked globally</p>
            </div>
            <div>
              <BarChart3 className="w-8 h-8 text-purple-600 mx-auto mb-2" />
              <p className="text-3xl font-bold text-gray-900">8+</p>
              <p className="text-sm text-gray-500 mt-1">Independent data sources</p>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}