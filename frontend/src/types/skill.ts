// src/types/skill.ts

export interface SkillROI {
  skill: string;
  avg_salary: number;
  job_demand_count: number;
  salary_premium: number;
}

export interface SkillsListResponse {
  total_skills: number;
  data: SkillROI[];
}

export interface SkillOverlap {
  skill_combo: string;
  combo_avg_salary: number;
  combo_demand_count: number;
  combo_premium: number;
}

export interface SkillOverlapListResponse {
  total_combos: number;
  data: SkillOverlap[];
}

export interface RelatedSkill {
  skill: string;
  co_occurrence_count: number;
}

export interface SalaryBucket {
  skill: string;
  salary_bucket: string;
  job_count: number;
}

export interface SkillDetail extends SkillROI {
  related_skills: RelatedSkill[];
  salary_distribution: SalaryBucket[];
}

export interface MarketOverviewResponse {
  metrics: Record<string, number>;
  top_skills: SkillROI[];
}

export interface CompareResponse {
  skills: SkillROI[];
  total: number;
}

export interface RelatedSkillsResponse {
  skill: string;
  related: RelatedSkill[];
}

export interface SalaryDistributionResponse {
  skill: string | null;
  distribution: SalaryBucket[];
}