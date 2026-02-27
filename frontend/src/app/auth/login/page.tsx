"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AuthForm } from "@/components/auth/AuthForm";
import { apiClient } from "@/lib/api";
import { useAuthStore } from "@/lib/store/auth";

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const handleLogin = async (data: { email: string; password: string }) => {
    setIsLoading(true);
    setError("");
    try {
      const tokens = await apiClient("/auth/login/", {
        method: "POST",
        body: JSON.stringify(data),
      });
      useAuthStore.getState().setTokens(tokens.access, tokens.refresh);

      const user = await apiClient("/auth/me/");
      useAuthStore.getState().setUser(user);

      router.push("/dashboard");
    } catch {
      setError("Invalid email or password. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSocialLogin = (provider: "google" | "apple") => {
    // TODO: implement social login
    console.log("Social login:", provider);
  };

  return (
    <div className="space-y-8">
      {/* Top Navigation */}
      <div className="flex justify-between items-center">
        <Link
          href="/"
          className="group flex items-center gap-2 text-sm text-gray-500 hover:text-black transition-colors"
        >
          <svg
            className="w-4 h-4 transition-transform group-hover:-translate-x-1"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 19l-7-7m0 0l7-7m-7 7h18"
            />
          </svg>
          <span>Back to website</span>
        </Link>
        
        {/* Mobile logo */}
        <div className="lg:hidden flex items-center gap-2">
          <div className="w-8 h-8 bg-black rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">N</span>
          </div>
          <span className="font-bold text-lg">Nexus</span>
        </div>
      </div>

      {/* Header Section */}
      <div className="space-y-2">
        <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
          Welcome back
        </h1>
        <p className="text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link href="/auth/register" className="text-primary hover:underline">
            Sign up
          </Link>
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Login Form */}
      <AuthForm
        mode="login"
        onSubmit={handleLogin}
        onSocialLogin={handleSocialLogin}
        isLoading={isLoading}
      />

      {/* Divider */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-200" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-white px-4 text-gray-400 font-medium">
            Secure login
          </span>
        </div>
      </div>

      {/* Forgot Password Link */}
      <div className="text-center pt-2">
        <Link
          href="/auth/forgot-password"
          className="text-sm text-gray-500 hover:text-black transition-colors underline-offset-4 hover:underline"
        >
          Forgot your password?
        </Link>
      </div>
    </div>
  );
}
