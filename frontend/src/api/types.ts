export interface User {
  id: number;
  username: string;
  email: string;
  created_at: string;
}

export interface UserCreate {
  username: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  identifier: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface OAuthProviders {
  providers: string[];
}

export interface Post {
  id: number;
  content: string;
  created_at: string;
  author: {
    id: number;
    username: string;
  };
}

export interface PostCreate {
  content: string;
}