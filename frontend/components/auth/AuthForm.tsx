"use client";

import { useState, FormEvent } from "react";
import { InputField } from "./InputField";
import { SubmitButton } from "./SubmitButton";
import { SocialButton } from "./SocialButton";
import { Checkbox } from "../../components/ui/Checkbox";
import Link from "next/link";

interface AuthFormProps {
  mode: "login" | "register";
  onSubmit: (data: FormData) => Promise<void>;
  onSocialLogin: (provider: "google" | "apple") => void;
}

interface FormData {
  firstName?: string;
  lastName?: string;
  email: string;
  password: string;
}

interface FormErrors {
  firstName?: string;
  lastName?: string;
  email?: string;
  password?: string;
  terms?: string;
}

export function AuthForm({ mode, onSubmit, onSocialLogin }: AuthFormProps) {
  const [formData, setFormData] = useState<FormData>({
    firstName: "",
    lastName: "",
    email: "",
    password: "",
  });

  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [isLoading, setIsLoading] = useState(false);

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    if (mode === "register") {
      if (!formData.firstName?.trim()) {
        newErrors.firstName = "First name is required";
      }
      if (!formData.lastName?.trim()) {
        newErrors.lastName = "Last name is required";
      }
      if (!acceptedTerms) {
        newErrors.terms = "You must accept the terms and conditions";
      }
    }

    if (!formData.email.trim()) {
      newErrors.email = "Email is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = "Please enter a valid email address";
    }

    if (!formData.password) {
      newErrors.password = "Password is required";
    } else if (mode === "register" && formData.password.length < 8) {
      newErrors.password = "Password must be at least 8 characters";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrors({});

    if (!validateForm()) return;

    setIsLoading(true);

    try {
      await onSubmit(formData);
    } catch (error) {
      console.error("Form submission error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {mode === "register" && (
        <div className="grid grid-cols-2 gap-4">
          <InputField
            type="text"
            placeholder="First name"
            value={formData.firstName || ""}
            onChange={(value) => setFormData({ ...formData, firstName: value })}
            error={errors.firstName}
            name="firstName"
          />
          <InputField
            type="text"
            placeholder="Last name"
            value={formData.lastName || ""}
            onChange={(value) => setFormData({ ...formData, lastName: value })}
            error={errors.lastName}
            name="lastName"
          />
        </div>
      )}

      <InputField
        type="email"
        placeholder="Email address"
        value={formData.email}
        onChange={(value) => setFormData({ ...formData, email: value })}
        error={errors.email}
        name="email"
      />

      <InputField
        type="password"
        placeholder="Password"
        value={formData.password}
        onChange={(value) => setFormData({ ...formData, password: value })}
        error={errors.password}
        name="password"
      />

      {mode === "register" && (
        <div className="flex items-start gap-3 pt-1">
          <Checkbox
            id="terms"
            checked={acceptedTerms}
            onCheckedChange={(checked: boolean | "indeterminate") =>
              setAcceptedTerms(checked === true)
            }
          />
          <label
            htmlFor="terms"
            className="text-sm text-gray-600 leading-relaxed cursor-pointer"
          >
            I agree to the{" "}
            <Link href="/terms" className="text-black font-semibold hover:underline underline-offset-2">
              Terms & Conditions
            </Link>{" "}
            and{" "}
            <Link href="/privacy" className="text-black font-semibold hover:underline underline-offset-2">
              Privacy Policy
            </Link>
          </label>
        </div>
      )}

      {errors.terms && (
        <p className="text-sm text-red-500 font-medium">{errors.terms}</p>
      )}

      {mode === "login" && (
        <div className="flex items-center justify-end">
          <Link 
            href="/auth/forgot-password" 
            className="text-sm text-gray-500 hover:text-black transition-colors underline-offset-2 hover:underline"
          >
            Forgot password?
          </Link>
        </div>
      )}

      <SubmitButton isLoading={isLoading}>
        {mode === "login" ? "Log in" : "Create account"}
      </SubmitButton>

      {/* Divider */}
      <div className="relative py-2">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-200" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-white px-4 text-gray-400 font-medium">
            Or continue with
          </span>
        </div>
      </div>

      {/* Social Buttons */}
      <div className="grid grid-cols-2 gap-4">
        <SocialButton
          provider="google"
          onClick={() => onSocialLogin("google")}
        />
        <SocialButton provider="apple" onClick={() => onSocialLogin("apple")} />
      </div>
    </form>
  );
}
