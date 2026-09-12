// frontend/src/lib/api.ts
import axios from 'axios';
import type {
  CompareResponse,
  MarketOverviewResponse,
  RelatedSkillsResponse,
  SalaryDistributionResponse,
  SkillDetail,
  SkillOverlapListResponse,
  SkillsListResponse,
} from '@/types/skill';

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const apiClient = axios.create({
  baseURL: apiBaseUrl,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
});

export const fetchAllSkillsROI = async (): Promise<SkillsListResponse> => {
  const response = await apiClient.get<SkillsListResponse>('/skills/roi');
  return response.data;
};

export const fetchSkillDetail = async (skillName: string): Promise<SkillDetail> => {
  const response = await apiClient.get<SkillDetail>(`/skills/${encodeURIComponent(skillName)}`);
  return response.data;
};

export const fetchSkillOverlaps = async (limit = 20): Promise<SkillOverlapListResponse> => {
  const response = await apiClient.get<SkillOverlapListResponse>('/skills/overlap', {
    params: { limit },
  });
  return response.data;
};

export const compareSkills = async (skills: string[]): Promise<CompareResponse> => {
  const response = await apiClient.get<CompareResponse>('/skills/compare', {
    params: { skills: skills.join(',') },
  });
  return response.data;
};

export const fetchMarketOverview = async (): Promise<MarketOverviewResponse> => {
  const response = await apiClient.get<MarketOverviewResponse>('/market/overview');
  return response.data;
};

export const fetchRelatedSkills = async (
  skillName: string,
  limit = 10
): Promise<RelatedSkillsResponse> => {
  const response = await apiClient.get<RelatedSkillsResponse>(
    `/skills/${encodeURIComponent(skillName)}/related`,
    { params: { limit } }
  );
  return response.data;
};

export const fetchSalaryDistribution = async (
  skillName: string
): Promise<SalaryDistributionResponse> => {
  const response = await apiClient.get<SalaryDistributionResponse>(
    `/skills/${encodeURIComponent(skillName)}/salary-distribution`
  );
  return response.data;
};

export const fetchSkillNames = async (): Promise<string[]> => {
  const response = await apiClient.get<{ skills: string[] }>('/skills');
  return response.data.skills;
};