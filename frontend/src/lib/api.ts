import { useAuthStore } from "@/lib/store/auth";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export async function apiClient(
  endpoint: string,
  options: RequestInit = {}
): Promise<any> {
  const { accessToken, refreshToken, setTokens, clearAuth } =
    useAuthStore.getState();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  let response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // If 401 and we have a refresh token, try refreshing
  if (response.status === 401 && refreshToken) {
    const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: refreshToken }),
    });

    if (refreshResponse.ok) {
      const { access } = await refreshResponse.json();
      setTokens(access, refreshToken);
      headers["Authorization"] = `Bearer ${access}`;

      // Retry the original request with the new token
      response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers,
      });
    } else {
      clearAuth();
      window.location.href = "/auth/login";
      throw new Error("Session expired");
    }
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || error.error || response.statusText);
  }

  return response.json();
}
