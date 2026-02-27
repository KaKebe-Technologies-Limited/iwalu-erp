"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "../../../../components/ui/Button";

export default function ResetPasswordPage() {
  const [passwords, setPasswords] = useState({
    password: "",
    confirmPassword: ""
  });
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (passwords.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    if (passwords.password !== passwords.confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    console.log("Password reset confirmed:", passwords.password);
    setIsSuccess(true);
  };

  if (isSuccess) {
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

        {/* Success State */}
        <div className="space-y-6 text-center py-8">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto">
            <svg 
              className="w-10 h-10 text-green-600" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M5 13l4 4L19 7" 
              />
            </svg>
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
              Password reset!
            </h1>
            <p className="text-gray-500 max-w-sm mx-auto">
              Your password has been successfully reset. You can now log in with your new password.
            </p>
          </div>
          
          <Link href="/auth/login">
            <Button 
              className="w-full py-3.5 text-base font-semibold rounded-xl bg-black hover:bg-zinc-800 transition-all"
            >
              Continue to Login
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Top Navigation */}
      <div className="flex justify-between items-center">
        <Link
          href="/auth/login"
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
          <span>Back to login</span>
        </Link>
        
        {/* Mobile logo */}
        <div className="lg:hidden flex items-center gap-2">
          <div className="w-8 h-8 bg-black rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">N</span>
          </div>
          <span className="font-bold text-lg">Nexus</span>
        </div>
      </div>

      {/* Header */}
      <div className="space-y-3">
        <div className="w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center mb-2">
          <svg 
            className="w-6 h-6 text-gray-600" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={1.5} 
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" 
            />
          </svg>
        </div>
        <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
          Set new password
        </h1>
        <p className="text-gray-500">
          Your new password must be different from previously used passwords.
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="space-y-2">
          <label 
            htmlFor="password" 
            className="text-sm font-semibold text-gray-700"
          >
            New password
          </label>
          <input
            id="password"
            type="password"
            value={passwords.password}
            onChange={(e) => setPasswords({ ...passwords, password: e.target.value })}
            placeholder="At least 8 characters"
            required
            className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-black/5 focus:border-black transition-all placeholder:text-gray-400"
          />
        </div>

        <div className="space-y-2">
          <label 
            htmlFor="confirmPassword" 
            className="text-sm font-semibold text-gray-700"
          >
            Confirm password
          </label>
          <input
            id="confirmPassword"
            type="password"
            value={passwords.confirmPassword}
            onChange={(e) => setPasswords({ ...passwords, confirmPassword: e.target.value })}
            placeholder="Re-enter your password"
            required
            className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-black/5 focus:border-black transition-all placeholder:text-gray-400"
          />
        </div>

        {error && (
          <div className="p-3 bg-red-50 border border-red-100 rounded-lg">
            <p className="text-red-600 text-sm font-medium">{error}</p>
          </div>
        )}

        {/* Password requirements */}
        <div className="bg-gray-50 rounded-xl p-4 space-y-2">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Password must:</p>
          <ul className="space-y-1">
            <li className={`flex items-center gap-2 text-sm ${passwords.password.length >= 8 ? 'text-green-600' : 'text-gray-400'}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${passwords.password.length >= 8 ? 'bg-green-500' : 'bg-gray-300'}`} />
              Be at least 8 characters
            </li>
            <li className={`flex items-center gap-2 text-sm ${passwords.password === passwords.confirmPassword && passwords.password.length > 0 ? 'text-green-600' : 'text-gray-400'}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${passwords.password === passwords.confirmPassword && passwords.password.length > 0 ? 'bg-green-500' : 'bg-gray-300'}`} />
              Match confirmation
            </li>
          </ul>
        </div>
        
        <Button 
          type="submit" 
          className="w-full py-3.5 text-base font-semibold rounded-xl bg-black hover:bg-zinc-800 transition-all"
        >
          Reset Password
        </Button>
      </form>

      {/* Back to login link */}
      <div className="text-center pt-4">
        <Link
          href="/auth/login"
          className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-black transition-colors"
        >
          <svg
            className="w-4 h-4"
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
          Back to login
        </Link>
      </div>
    </div>
  );
}
