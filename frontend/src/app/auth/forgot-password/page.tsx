"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "../../../../components/ui/Button";

export default function ForgotPasswordPage() {
  const [emailSent, setEmailSent] = useState(false);
  const [email, setEmail] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Password reset requested for:", email);
    setEmailSent(true);
  };

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
          Forgot password?
        </h1>
        <p className="text-gray-500">
          No worries, we'll send you reset instructions.
        </p>
      </div>

      {/* Form or Success Message */}
      {!emailSent ? (
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <label 
              htmlFor="email" 
              className="text-sm font-semibold text-gray-700"
            >
              Email address
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              required
              className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-black/5 focus:border-black transition-all placeholder:text-gray-400"
            />
          </div>
          
          <Button 
            type="submit" 
            className="w-full py-3.5 text-base font-semibold rounded-xl bg-black hover:bg-zinc-800 transition-all"
          >
            Reset Password
          </Button>
        </form>
      ) : (
        <div className="p-6 bg-green-50 border border-green-100 rounded-2xl text-center space-y-4">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto">
            <svg 
              className="w-8 h-8 text-green-600" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" 
              />
            </svg>
          </div>
          <div>
            <h3 className="text-lg font-bold text-green-800 mb-1">Check your email!</h3>
            <p className="text-green-700 text-sm">
              We sent a password reset link to <span className="font-semibold">{email}</span>
            </p>
          </div>
          <Button
            variant="ghost"
            onClick={() => setEmailSent(false)}
            className="text-green-700 hover:bg-green-100 hover:text-green-800 text-sm font-medium"
          >
            Didn't receive the email? Try again
          </Button>
        </div>
      )}

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
