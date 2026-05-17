export type UserRole = 'admin' | 'operator' | 'viewer';

export type AuthUser = {
  id: string;
  email: string;
  username: string;
  role: UserRole;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string;
  last_login_at?: string | null;
};

export type LoginRequest = {
  username_or_email: string;
  password: string;
};

export type AuthTokens = {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
};

export type LoginResponse = AuthTokens & {
  user: AuthUser;
};
