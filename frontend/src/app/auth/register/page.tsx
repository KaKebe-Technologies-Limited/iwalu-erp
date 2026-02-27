"use client";

import { AuthForm } from "../../../../components/auth/AuthForm";
import Link from "next/link";

export default function RegisterPage() {
  const handleRegister = async (data: any) => {
    // Backend dev will implement this
    console.log("Register data:", data);
  };

  const handleSocialLogin = (provider: "google" | "apple") => {
    // Backend dev will implement this
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
          Create your account
        </h1>
        <p className="text-gray-500">
          Already have an account?{" "}
          <Link 
            href="/auth/login" 
            className="text-black font-semibold hover:underline underline-offset-4 transition-all"
          >
            Log in
          </Link>
        </p>
      </div>

      {/* Register Form */}
      <AuthForm
        mode="register"
        onSubmit={handleRegister}
        onSocialLogin={handleSocialLogin}
      />

      {/* Divider */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-200" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-white px-4 text-gray-400 font-medium">
            Quick signup
          </span>
        </div>
      </div>

      {/* Terms */}
      <p className="text-center text-xs text-gray-400 leading-relaxed">
        By creating an account, you agree to our{" "}
        <a href="#" className="underline hover:text-gray-600">Terms of Service</a>{" "}
        and{" "}
        <a href="#" className="underline hover:text-gray-600">Privacy Policy</a>.
      </p>
    </div>
  );
}
