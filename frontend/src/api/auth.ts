import { apiClient } from './client';
import type { LoginRequest, OAuthProviders, TokenResponse, User, UserCreate } from './types';

export async function signup(data: UserCreate): Promise<User> {
  const { data: user } = await apiClient.post<User>('/auth/signup', data);
  return user;
}

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const { data: token } = await apiClient.post<TokenResponse>('/auth/login', data);
  return token;
}

export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<User>('/auth/me');
  return data;
}

export async function getOAuthProviders(): Promise<OAuthProviders> {
  const { data } = await apiClient.get<OAuthProviders>('/auth/oauth/providers');
  return data;
}